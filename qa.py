# -*- coding: utf-8 -*-
"""门户问答域（R5 自 app.py 拆出）：公开上传、WeKnora 会话映射、问答共享内核。

一个变更理由：访客怎么把知识进来（上传）、怎么把答案问出去（ask/feedback）。
kb_ask_core 是 /api/kb/ask 视图与 kb-assistant 智能体共用的链路（A3）——
app.py 装配时把它注入 agents.runtime。
"""
import re
import time
import secrets
import threading
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from core import limiter
from kb_admin import ALLOWED_KB_EXTS, MAX_KB_SIZE, RETRIEVAL_OPTIONS, clean_choice
from rag.ingest import extract_pdf_text
from rag import engine as wk_engine
from rag.intents import classify_intent

bp = Blueprint("qa", __name__)

_kb = None  # rag.store.KnowledgeStore（app.py 装配注入）


def init(kb):
    global _kb
    _kb = kb


@bp.route("/api/kb/upload", methods=["POST"])
@limiter(6, 300, message="上传太频繁，请稍后再试")
def api_kb_upload():
    """公开上传：TXT/MD/PDF，进入待审核状态。"""
    if "file" not in request.files:
        return jsonify({"error": "没有收到文件"}), 400
    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"error": "文件为空"}), 400
    ext = secure_filename(file.filename).rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_KB_EXTS:
        return jsonify({"error": "仅支持 TXT / Markdown / PDF 文件"}), 400
    blob = file.read()
    if len(blob) > MAX_KB_SIZE:
        return jsonify({"error": "文件超过 10MB 限制"}), 400
    if len(blob) == 0:
        return jsonify({"error": "文件内容为空"}), 400

    raw_name = file.filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    try:
        if ext == "pdf":
            import io
            text = extract_pdf_text(io.BytesIO(blob))
        else:
            text = blob.decode("utf-8", errors="ignore")
        doc = _kb.add_text(text, title=raw_name, doc_type="upload", status="pending")
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "文件解析失败：%s" % str(e)[:120]}), 400
    return jsonify({"id": doc["id"], "status": doc["status"],
                    "message": "上传成功，等待管理员审核后进入知识库"})


# ── W3：WeKnora 会话映射（conversation_id -> weknora session_id）─────────────
# 门户保管映射：同一前台会话的多轮提问复用同一个 WeKnora session，由 WeKnora
# 侧维护上下文。映射只存内存（重启丢失 = 自动新建会话，无感）；超量淘汰最旧。
_WK_SESSION_TTL = 3600          # 1 小时不说话即弃
_WK_SESSION_MAX = 300
_wk_sessions = {}               # {conversation_id: [session_id, last_ts]}
_wk_sessions_lock = threading.Lock()
# WeKnora 回答里的内联引用标记（<kb doc=".." chunk_id=".."/>），前台来源列表
# 已单独展示，这里清掉避免以原始标签形式混进正文
_WK_CITE_RE = re.compile(r"<kb\b[^>]*/>|<kb\b[^>]*>.*?</kb>", re.S)


def _wk_session_get(conversation_id):
    if not conversation_id:
        return None
    with _wk_sessions_lock:
        entry = _wk_sessions.get(conversation_id)
        if entry and time.time() - entry[1] < _WK_SESSION_TTL:
            return entry[0]
        if entry:
            _wk_sessions.pop(conversation_id, None)
    return None


def _wk_session_save(conversation_id, session_id):
    if not conversation_id or not session_id:
        return
    with _wk_sessions_lock:
        _wk_sessions[conversation_id] = [session_id, time.time()]
        if len(_wk_sessions) > _WK_SESSION_MAX:
            oldest = min(_wk_sessions, key=lambda k: _wk_sessions[k][1])
            _wk_sessions.pop(oldest, None)


def _ask_weknora(question, history, conversation_id):
    """W3：知识问答转发 WeKnora（意图已判定为 knowledge）。
    A3 起返回与旧链路同构的 dict；引擎故障抛 RuntimeError（端点映射 502）。"""
    t0 = time.perf_counter()
    ask_id = secrets.token_hex(8)
    session_id = _wk_session_get(conversation_id)
    try:
        answer, refs, session_id = wk_engine.chat(question, session_id=session_id)
    except wk_engine.EngineError as e:
        # 映射的会话可能已失效（WeKnora 重启/过期）：丢弃映射重试一次
        if not session_id:
            raise RuntimeError("WeKnora 问答失败：%s" % str(e)[:120])
        try:
            answer, refs, session_id = wk_engine.chat(question, session_id=None)
        except wk_engine.EngineError as e2:
            raise RuntimeError("WeKnora 问答失败：%s" % str(e2)[:120])
    _wk_session_save(conversation_id, session_id)
    answer = _WK_CITE_RE.sub("", answer or "").strip()
    sources = [{"title": r.get("title") or "(未命名)", "snippet": r.get("snippet") or ""}
               for r in refs]
    hits = len(sources)
    # 无引用 = 答案无据可依（WeKnora 的拒绝式回答），遥测按 refused 记
    _kb.log_weknora_ask(ask_id, question, hits, refused=hits == 0, answer=answer,
                        t0=t0, turns=len(history or []))
    return {
        "answer": answer, "sources": sources, "retrieval": "weknora",
        "intent": "knowledge", "ask_id": ask_id, "engine": "weknora",
    }


def kb_ask_core(question, history=None, retrieval=None, conversation_id=""):
    """问答共享内核（A3）：/api/kb/ask 视图与 kb-assistant 智能体共用同一条链路。

    入参问题抛 ValueError；引擎故障抛 RuntimeError；其余异常向上传播。
    返回结果 dict（answer/sources/retrieval/intent/ask_id/engine）。
    """
    question = (question or "").strip()
    if not question:
        raise ValueError("请输入问题")
    if len(question) > 500:
        raise ValueError("问题太长（最多 500 字）")
    history = history if isinstance(history, list) else None
    if wk_engine.is_enabled():
        try:
            intent = classify_intent(question, has_history=bool(history))
        except Exception:
            intent = "knowledge"  # 路由器自身异常时按知识问答兜底
        if intent == "knowledge":
            return _ask_weknora(question, history or [], conversation_id)
    return _kb.ask(question, history=history,
                   retrieval=clean_choice(retrieval, RETRIEVAL_OPTIONS))


@bp.route("/api/kb/ask", methods=["POST"])
@limiter(10, 60, message="提问太频繁，请稍后再试")
def api_kb_ask():
    """知识库问答：意图路由（知识/闲聊/超范围）+ 多轮上下文 + 可插拔检索 + LLM 生成。
    W3：引擎开启时 knowledge 意图转发 WeKnora chat；问候/闲聊/知识外仍走原意图链路；
    WEKNORA_ENABLED=false 一键回到全旧链路（回滚网）。
    A3：核心逻辑抽到 kb_ask_core，智能体与视图共用。"""
    payload = request.get_json(force=True, silent=True) or {}
    try:
        result = kb_ask_core(payload.get("question"), history=payload.get("history"),
                             retrieval=payload.get("retrieval"),
                             conversation_id=(payload.get("conversation_id") or "").strip()[:64])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "问答失败：%s" % str(e)[:120]}), 500
    return jsonify(result)


@bp.route("/api/kb/feedback", methods=["POST"])
@limiter(30, 60, message="操作太频繁，请稍后再试")
def api_kb_feedback():
    """前台对某次回答点 👍/👎，写回对应问答遥测（Slice 4）。公开接口，仅需合法 ask_id。"""
    payload = request.get_json(force=True, silent=True) or {}
    ask_id = (payload.get("ask_id") or "").strip()
    raw = (payload.get("rating") or "").strip().lower()
    # 宽容接收多种写法，最终归一到 up/down
    if raw in ("up", "1", "like", "good", "thumb_up", "thumbup"):
        rating = "up"
    elif raw in ("down", "0", "-1", "dislike", "bad", "thumb_down", "thumbdown"):
        rating = "down"
    else:
        return jsonify({"error": "反馈参数不合法"}), 400
    if not ask_id:
        return jsonify({"error": "缺少问答标识"}), 400
    try:
        ok = _kb.telemetry.set_feedback(ask_id, rating)
    except Exception as e:
        return jsonify({"error": "反馈失败：%s" % str(e)[:120]}), 500
    if not ok:
        return jsonify({"error": "问答记录不存在或已过期"}), 404
    return jsonify({"ok": True})
