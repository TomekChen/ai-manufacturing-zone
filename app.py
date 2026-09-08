import os
import re
import json
import time
import threading
import secrets
import hashlib
from functools import wraps
from datetime import datetime
from urllib.parse import urlparse
from flask import Flask, send_from_directory, request, jsonify
from werkzeug.utils import secure_filename
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

import kb
import notify
from rag import evaluate as kb_eval
from rag import prd as kb_prd
from rag import engine as wk_engine
from rag.intents import classify_intent
import agents  # import 即注册（agents/registry.py 底部挂载所有智能体实现）

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 全局上传上限 20MB（知识库文档放宽到 10MB）

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DIST_DIR = os.path.join(BASE_DIR, "dist")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")

# 外观配置内置默认值（唯一真源）：get_config 兜底 & "恢复默认" 都用它
DEFAULT_CONFIG = {"title": "智能制造专区", "accent": "#3b82f6", "canvas": "#0b0b0f"}

ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_KB_EXTS = {"txt", "md", "pdf"}
MAX_KB_SIZE = 10 * 1024 * 1024  # 知识库文档 10MB

ADMIN_ACCOUNT = os.environ.get("ADMIN_ACCOUNT", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.environ.get("SECRET_KEY", "ai-manufacturing-zone-secret")


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def get_config():
    return load_json(CONFIG_FILE, dict(DEFAULT_CONFIG))


def get_projects():
    return load_json(PROJECTS_FILE, [])


def hash_password(pwd):
    return hashlib.sha256((pwd + SECRET_KEY).encode("utf-8")).hexdigest()


def verify_token(token):
    if not token or not token.startswith("Bearer "):
        return False
    t = token.split(" ", 1)[1]
    expected = hash_password(ADMIN_ACCOUNT + ADMIN_PASSWORD + SECRET_KEY)
    # 简单 token：sha256(account+pwd+secret) 的前 32 位
    return t == expected[:32]


def require_admin(fn):
    """视图装饰器：统一后台鉴权。放在 @app.route 之下，替代各路由重复的 verify_token 样板。"""
    @wraps(fn)  # 保留原函数名，避免 Flask endpoint 全部塌成 wrapper 而冲突
    def wrapper(*args, **kwargs):
        if not verify_token(request.headers.get("Authorization", "")):
            return jsonify({"error": "Unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


def _clean_choice(raw, options):
    """可选入参清洗：空 / 非法值 -> None（交回后端默认），合法值 -> 原样返回。
    在信任边界挡住未知策略名，避免注入注册表里没有的 key。"""
    v = (raw or "").strip()
    return v if v in options else None


def check_alive(url, timeout=15):
    """宽松心跳检测：服务只要能建立连接并返回非 5xx 状态即视为在线。"""
    if not url:
        return False

    def try_request(method):
        try:
            r = requests.request(
                method, url,
                timeout=(5, timeout),  # (connect, read)
                headers={"User-Agent": "Heartbeat/1.0"},
                verify=False,
                allow_redirects=True,
            )
            # 2xx/3xx/4xx 都表示服务在运行；5xx 表示服务异常
            return r.status_code < 500
        except requests.exceptions.SSLError:
            # SSL 证书问题但服务在运行
            return True
        except requests.exceptions.ConnectionError:
            return False
        except requests.exceptions.Timeout:
            return False
        except Exception:
            return False

    # 先尝试 HEAD（轻量），失败再回退 GET
    if try_request("HEAD"):
        return True
    return try_request("GET")


def heartbeat_all():
    projects = get_projects()
    changed = False
    for p in projects:
        was_alive = p.get("alive", False)
        # 优先使用独立的心跳检测地址，回退到访问地址
        check_url = p.get("heartbeatUrl") or p.get("url") or ""
        is_alive = check_alive(check_url)
        p["alive"] = is_alive
        p["last_check"] = datetime.now().isoformat()
        if was_alive != is_alive:
            changed = True
    save_json(PROJECTS_FILE, projects)
    return changed


def heartbeat_loop():
    while True:
        try:
            heartbeat_all()
        except Exception as e:
            print("heartbeat error:", e)
        time.sleep(60)


# 启动后台心跳线程
threading.Thread(target=heartbeat_loop, daemon=True).start()


@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify(get_config())


@app.route("/api/admin/config", methods=["POST"])
@require_admin
def api_admin_config():
    payload = request.get_json(force=True) or {}
    cfg = get_config()
    cfg.update({k: v for k, v in payload.items() if k in ("title", "accent", "canvas")})
    save_json(CONFIG_FILE, cfg)
    return jsonify(cfg)


@app.route("/api/admin/config/reset", methods=["POST"])
@require_admin
def api_admin_config_reset():
    """恢复默认外观配置（把标题/主色/背景重置回内置默认值），供管理员改坏外观时一键救急。"""
    cfg = dict(DEFAULT_CONFIG)
    save_json(CONFIG_FILE, cfg)
    return jsonify(cfg)


@app.route("/api/projects", methods=["GET"])
def api_projects():
    return jsonify(get_projects())


@app.route("/api/admin/projects", methods=["GET", "POST"])
@require_admin
def api_admin_projects():
    if request.method == "GET":
        return jsonify(get_projects())

    payload = request.get_json(force=True) or {}
    projects = get_projects()

    proj = {
        "id": payload.get("id") or secrets.token_hex(8),
        "name": (payload.get("name") or "").strip(),
        "role": (payload.get("role") or "").strip(),
        "desc": (payload.get("desc") or "").strip(),
        "url": (payload.get("url") or "").strip(),
        "heartbeatUrl": (payload.get("heartbeatUrl") or "").strip(),
        "image": (payload.get("image") or "").strip(),
        "caps": [c.strip() for c in payload.get("caps", []) if c.strip()],
        "color": (payload.get("color") or "blue").strip(),
        "alive": False,
        "last_check": datetime.now().isoformat(),
    }
    if not proj["name"] or not proj["url"]:
        return jsonify({"error": "name and url are required"}), 400

    # 验证 URL 基本格式
    try:
        parsed = urlparse(proj["url"])
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("invalid url")
    except Exception:
        return jsonify({"error": "invalid url"}), 400

    # 保存时不阻塞等待心跳，返回后由后台异步检测
    proj["alive"] = False

    existing_ids = {p["id"] for p in projects}
    if payload.get("id") in existing_ids:
        projects = [p if p["id"] != payload["id"] else {**p, **proj} for p in projects]
    else:
        projects.append(proj)

    save_json(PROJECTS_FILE, projects)
    # 异步触发一次心跳检测，让前端尽快看到最新状态，但不阻塞保存响应
    threading.Thread(target=lambda: (time.sleep(1), heartbeat_all()), daemon=True).start()
    return jsonify(projects)


@app.route("/api/admin/projects/<pid>", methods=["DELETE"])
@require_admin
def api_admin_delete_project(pid):
    projects = [p for p in get_projects() if p["id"] != pid]
    save_json(PROJECTS_FILE, projects)
    return jsonify(projects)


@app.route("/api/admin/heartbeat", methods=["POST"])
@require_admin
def api_admin_heartbeat():
    heartbeat_all()
    return jsonify(get_projects())


def probe_url(url, timeout=15):
    """详细探测：返回 {alive, status, error}，供后台\"测试连接\"按钮实时反馈。"""
    if not url:
        return {"alive": False, "status": None, "error": "地址为空"}
    last_err = None
    for method in ("HEAD", "GET"):
        try:
            r = requests.request(
                method, url,
                timeout=(5, timeout),
                headers={"User-Agent": "Heartbeat/1.0"},
                verify=False,
                allow_redirects=True,
            )
            alive = r.status_code < 500
            return {
                "alive": alive,
                "status": r.status_code,
                "error": None if alive else f"服务返回 {r.status_code}（5xx 视为异常）",
            }
        except requests.exceptions.SSLError:
            return {"alive": True, "status": None, "error": "SSL 证书告警，但服务可达"}
        except requests.exceptions.ConnectionError:
            last_err = "无法建立连接（地址不可达 / 端口未监听 / 服务器无法回环访问本机公网地址）"
        except requests.exceptions.Timeout:
            last_err = "连接超时（服务器在该地址上无响应）"
        except Exception as e:
            last_err = str(e)[:160]
    return {"alive": False, "status": None, "error": last_err or "未知错误"}


@app.route("/api/admin/probe", methods=["POST"])
@require_admin
def api_admin_probe():
    payload = request.get_json(force=True) or {}
    url = (payload.get("url") or "").strip()
    return jsonify(probe_url(url))


@app.route("/api/admin/upload", methods=["POST"])
@require_admin
def api_admin_upload():
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400
    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"error": "empty file"}), 400
    ext = secure_filename(file.filename).rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        return jsonify({"error": f"only {', '.join(ALLOWED_IMAGE_EXTS)} allowed"}), 400
    filename = f"{secrets.token_hex(8)}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)
    return jsonify({"url": f"/uploads/{filename}"})


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    payload = request.get_json(force=True) or {}
    account = payload.get("account", "")
    password = payload.get("password", "")
    if account == ADMIN_ACCOUNT and password == ADMIN_PASSWORD:
        token = hash_password(account + password + SECRET_KEY)[:32]
        return jsonify({"token": token})
    return jsonify({"error": "invalid account or password"}), 401


# ===================== 知识库（RAG）=====================

# 全局知识库存储（数据文件在 data/ 挂载卷内，容器重建不丢）
KB = kb.KnowledgeStore(DATA_DIR)
# 智能体运行时注入：WeKnora 关闭时 PRD 回退检索用（agents 包不反向依赖 app）
agents.runtime.store = KB

# 公开问答的简单内存限流：每 IP 每分钟最多 10 次
# bucket 隔离各端点额度（A1 起公开 PRD 每小时 5 次，若与问答共用一个桶会被高频问答吃掉额度）
_ask_limits = {}
_ask_limit_lock = threading.Lock()


def rate_limited(ip, limit=10, window=60, bucket="default"):
    now = time.time()
    with _ask_limit_lock:
        store = _ask_limits.setdefault(bucket, {})
        lst = [t for t in store.get(ip, []) if now - t < window]
        if len(lst) >= limit:
            store[ip] = lst
            return True
        lst.append(now)
        store[ip] = lst
        return False


@app.route("/api/kb/stats", methods=["GET"])
def api_kb_stats():
    return jsonify(KB.stats())


@app.route("/api/links", methods=["GET"])
def api_links():
    return jsonify(KB.list_links())


@app.route("/api/kb/upload", methods=["POST"])
def api_kb_upload():
    """公开上传：TXT/MD/PDF，进入待审核状态。"""
    if rate_limited(request.remote_addr, limit=6, window=300):
        return jsonify({"error": "上传太频繁，请稍后再试"}), 429
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
            text = kb.extract_pdf_text(io.BytesIO(blob))
        else:
            text = blob.decode("utf-8", errors="ignore")
        doc = KB.add_text(text, title=raw_name, doc_type="upload", status="pending")
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
    KB.log_weknora_ask(ask_id, question, hits, refused=hits == 0, answer=answer,
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
    return KB.ask(question, history=history,
                  retrieval=_clean_choice(retrieval, kb.RETRIEVAL_OPTIONS))


# 智能体运行时注入（A3）：知识管家与公开问答视图共用此内核
agents.runtime.kb_ask = kb_ask_core


@app.route("/api/kb/ask", methods=["POST"])
def api_kb_ask():
    """知识库问答：意图路由（知识/闲聊/超范围）+ 多轮上下文 + 可插拔检索 + LLM 生成。
    W3：引擎开启时 knowledge 意图转发 WeKnora chat；问候/闲聊/知识外仍走原意图链路；
    WEKNORA_ENABLED=false 一键回到全旧链路（回滚网）。
    A3：核心逻辑抽到 kb_ask_core，智能体与视图共用。"""
    if rate_limited(request.remote_addr, limit=10, window=60):
        return jsonify({"error": "提问太频繁，请稍后再试"}), 429
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


@app.route("/api/kb/feedback", methods=["POST"])
def api_kb_feedback():
    """前台对某次回答点 👍/👎，写回对应问答遥测（Slice 4）。公开接口，仅需合法 ask_id。"""
    if rate_limited(request.remote_addr, limit=30, window=60):
        return jsonify({"error": "操作太频繁，请稍后再试"}), 429
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
        ok = KB.telemetry.set_feedback(ask_id, rating)
    except Exception as e:
        return jsonify({"error": "反馈失败：%s" % str(e)[:120]}), 500
    if not ok:
        return jsonify({"error": "问答记录不存在或已过期"}), 404
    return jsonify({"ok": True})


@app.route("/api/admin/kb/docs", methods=["GET"])
@require_admin
def api_admin_kb_docs():
    return jsonify({"docs": KB.list_docs(), "stats": KB.stats()})


@app.route("/api/admin/kb/docs/<doc_id>", methods=["GET"])
@require_admin
def api_admin_kb_doc_detail(doc_id):
    """管理员预览单条文档及分块内容。"""
    try:
        detail = KB.get_doc_detail(doc_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "加载失败：%s" % str(e)[:120]}), 500
    return jsonify(detail)


@app.route("/api/admin/kb/docs/<doc_id>/approve", methods=["POST"])
@require_admin
def api_admin_kb_approve(doc_id):
    try:
        doc = KB.approve(doc_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "入库失败：%s" % str(e)[:120]}), 502
    return jsonify({"doc": doc, "stats": KB.stats()})


@app.route("/api/admin/kb/docs/<doc_id>/reject", methods=["POST"])
@require_admin
def api_admin_kb_reject(doc_id):
    try:
        doc = KB.reject(doc_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"doc": doc, "stats": KB.stats()})


@app.route("/api/admin/kb/docs/<doc_id>", methods=["DELETE"])
@require_admin
def api_admin_kb_delete(doc_id):
    try:
        KB.delete(doc_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"docs": KB.list_docs(), "stats": KB.stats()})


def _crawl_to_kb(url, doc_type="url", chunking=None):
    """抓取 URL 并直接以 approved 状态入库（管理员操作，视为已审核）。"""
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("地址必须以 http:// 或 https:// 开头")
    title, text = kb.fetch_url_text(url)
    if not text or len(text.strip()) < 30:
        raise RuntimeError("页面正文内容太少，无法入库")
    if kb.looks_like_nav_page(text):
        raise RuntimeError("抓到的内容像是网站首页/栏目列表（全是标题、没有正文），请粘贴具体文章的详情页地址")
    doc = KB.add_text(text, title=title or url, url=url,
                      doc_type=doc_type, status="approved", chunking=chunking)
    return doc


@app.route("/api/admin/kb/crawl", methods=["POST"])
@require_admin
def api_admin_kb_crawl():
    payload = request.get_json(force=True, silent=True) or {}
    url = (payload.get("url") or "").strip()
    # WeKnora 引擎开启时采集走 WeKnora（异步解析，入库即 approved，无审核流）
    if wk_engine.is_enabled():
        if not url.startswith(("http://", "https://")):
            return jsonify({"error": "地址必须以 http:// 或 https:// 开头"}), 400
        try:
            doc = wk_engine.upload_url(url)
        except wk_engine.EngineError as e:
            return jsonify({"error": str(e)}), 502
        return jsonify({
            "doc": {"id": doc.get("id"), "title": doc.get("title") or url,
                    "parse_status": doc.get("parse_status") or "pending"},
            "message": "已提交 WeKnora 解析（异步），状态稍后自动刷新",
        })
    chunking = _clean_choice(payload.get("chunking"), kb.CHUNKING_OPTIONS)
    try:
        doc = _crawl_to_kb(url, chunking=chunking)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "采集失败：%s" % str(e)[:160]}), 502
    return jsonify({"doc": doc, "message": "采集成功，已入库"})


@app.route("/api/admin/kb/options", methods=["GET"])
@require_admin
def api_admin_kb_options():
    """后台下拉框数据源：可选的分块/检索策略及默认值（单一事实来源=注册表，前端不再硬编码）。
    engine 字段供前端判定走 WeKnora 模式还是旧模式（WEKNORA_ENABLED 回退开关）。"""
    return jsonify({
        "chunking": kb.CHUNKING_OPTIONS,
        "default_chunking": kb.DEFAULT_CHUNKING,
        "retrieval": kb.RETRIEVAL_OPTIONS,
        "default_retrieval": kb.DEFAULT_RETRIEVAL,
        "engine": wk_engine.status(),
    })


@app.route("/api/admin/kb/rebuild", methods=["POST"])
@require_admin
def api_admin_kb_rebuild_all():
    """全库重建：按各文档记录的分块策略重新切块 + 重嵌入（会重花 embedding 额度）。"""
    try:
        result = KB.rebuild_all()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "重建失败：%s" % str(e)[:160]}), 502
    return jsonify({
        "result": result, "stats": KB.stats(),
        "message": "全库重建完成（共 %d 篇 / %d 块）" % (result["docs"], result["chunks"]),
    })


@app.route("/api/admin/kb/docs/<doc_id>/rebuild", methods=["POST"])
@require_admin
def api_admin_kb_rebuild_doc(doc_id):
    """单篇重建：可选换分块策略后重新切块 + 重嵌入。"""
    payload = request.get_json(force=True, silent=True) or {}
    chunking = _clean_choice(payload.get("chunking"), kb.CHUNKING_OPTIONS)
    try:
        result = KB.rebuild_doc(doc_id, chunking=chunking)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except KeyError as e:
        return jsonify({"error": "未知分块策略：%s" % str(e)[:80]}), 400
    except Exception as e:
        return jsonify({"error": "重建失败：%s" % str(e)[:160]}), 502
    return jsonify({
        "doc": result["doc"], "stats": KB.stats(), "re_sharded": result["re_sharded"],
        "message": "单篇重建完成：%d 块" % result["chunks"],
    })


# ── WeKnora 引擎转发（W2）：管理界面在引擎开启时改走这组端点 ─────────────────
# SPEC：所有 WeKnora 调用收口在 rag/engine.py；WEKNORA_ENABLED=false 时前端
# 自动回退旧界面（下方旧端点原样保留，就是回滚网本身）。

@app.route("/api/admin/kb/weknora/status", methods=["GET"])
@require_admin
def api_admin_kb_weknora_status():
    """引擎概览：是否启用/是否已配置/健康检查。"""
    st = wk_engine.status()
    st["healthy"] = wk_engine.health() if st["configured"] else None
    return jsonify(st)


@app.route("/api/admin/kb/weknora/docs", methods=["GET"])
@require_admin
def api_admin_kb_weknora_docs():
    """WeKnora 文档列表（含解析状态）。"""
    if not wk_engine.is_enabled():
        return jsonify({"error": "WeKnora 引擎未启用"}), 409
    try:
        return jsonify(wk_engine.list_docs())
    except wk_engine.EngineError as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/admin/kb/weknora/upload", methods=["POST"])
@require_admin
def api_admin_kb_weknora_upload():
    """上传文档到 WeKnora（解析异步，前端轮询刷新状态）。"""
    if not wk_engine.is_enabled():
        return jsonify({"error": "WeKnora 引擎未启用"}), 409
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "没有收到文件"}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_KB_EXTS:
        return jsonify({"error": "仅支持 TXT / Markdown / PDF 文件"}), 400
    blob = file.read()
    if len(blob) > MAX_KB_SIZE:
        return jsonify({"error": "文件超过 10MB 限制"}), 400
    if len(blob) == 0:
        return jsonify({"error": "文件内容为空"}), 400
    try:
        doc_id = wk_engine.upload_file(file.filename, blob)
    except wk_engine.EngineError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"id": doc_id, "parse_status": "pending",
                    "message": "已提交 WeKnora 解析，稍后自动刷新状态"})


@app.route("/api/admin/kb/weknora/docs/<kid>", methods=["GET"])
@require_admin
def api_admin_kb_weknora_doc(kid):
    """单文档：解析状态 + 分块预览。"""
    if not wk_engine.is_enabled():
        return jsonify({"error": "WeKnora 引擎未启用"}), 409
    try:
        detail = wk_engine.doc_detail(kid)
        chunks = wk_engine.doc_chunks(kid)
    except wk_engine.EngineError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"doc": detail, "chunks": chunks})


@app.route("/api/admin/kb/weknora/docs/<kid>", methods=["DELETE"])
@require_admin
def api_admin_kb_weknora_delete(kid):
    if not wk_engine.is_enabled():
        return jsonify({"error": "WeKnora 引擎未启用"}), 409
    try:
        wk_engine.delete_doc(kid)
    except wk_engine.EngineError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"ok": True})


@app.route("/api/admin/kb/weknora/search", methods=["POST"])
@require_admin
def api_admin_kb_weknora_search():
    """检索调试：直查 WeKnora knowledge-search（分数尺度与问答链路不可混比）。"""
    if not wk_engine.is_enabled():
        return jsonify({"error": "WeKnora 引擎未启用"}), 409
    payload = request.get_json(force=True, silent=True) or {}
    q = (payload.get("query") or "").strip()
    if not q:
        return jsonify({"error": "请输入检索词"}), 400
    try:
        hits = wk_engine.search(q, top_k=8)
    except wk_engine.EngineError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"hits": hits})


@app.route("/api/admin/kb/analytics", methods=["GET"])
@require_admin
def api_admin_kb_analytics():
    """问答看板聚合（Slice 4）：总量/拒绝率/各策略对比/时间趋势/👍👎/未命中清单。"""
    try:
        days = int(request.args.get("days") or kb.TELEM_TREND_DAYS)
    except (TypeError, ValueError):
        days = kb.TELEM_TREND_DAYS
    days = max(1, min(90, days))
    try:
        data = KB.telemetry.aggregate(days=days)
    except Exception as e:
        return jsonify({"error": "统计失败：%s" % str(e)[:120]}), 500
    return jsonify(data)


# ── Slice 6：离线 RAGAS-lite 评测（管理员手动触发才花额度） ──────────────────
@app.route("/api/admin/kb/eval/run", methods=["POST"])
@require_admin
def api_admin_kb_eval_run():
    """启动一次后台评测。已跑→409；无 API Key→400；正常→202 带启动快照。"""
    try:
        info = kb_eval.start(KB, DATA_DIR)
    except RuntimeError as e:
        msg = str(e)
        if "正在" in msg or "running" in msg.lower():
            return jsonify({"error": msg, "state": kb_eval.get_state()}), 409
        if "DASHSCOPE_API_KEY" in msg or "未配置" in msg:
            return jsonify({"error": msg}), 400
        return jsonify({"error": msg}), 400
    except FileNotFoundError as e:
        return jsonify({"error": "评测题集缺失：%s" % str(e)[:120]}), 500
    return jsonify(info), 202


@app.route("/api/admin/kb/eval/status", methods=["GET"])
@require_admin
def api_admin_kb_eval_status():
    """轮询用：返回当前进度与最近一次已完成结果的摘要。"""
    return jsonify(kb_eval.get_state())


@app.route("/api/admin/kb/eval/results", methods=["GET"])
@require_admin
def api_admin_kb_eval_results():
    """评测历史：滚动上限由 config.EVAL_MAX_RESULTS 控制；支持 ?limit=N 只取最近几条。"""
    try:
        limit = int(request.args.get("limit") or kb_eval.config.EVAL_MAX_RESULTS)
    except (TypeError, ValueError):
        limit = kb_eval.config.EVAL_MAX_RESULTS
    limit = max(1, min(kb_eval.config.EVAL_MAX_RESULTS, limit))
    try:
        history = kb_eval.EvalStore(DATA_DIR).load()
    except Exception as e:
        return jsonify({"error": "读取评测历史失败：%s" % str(e)[:120]}), 500
    return jsonify({
        "metrics": list(kb_eval.config.EVAL_METRICS),
        "labels": kb_eval.METRIC_LABELS,
        "history": history[-limit:],
    })


# ── PRD 生成器（对齐老板新方向：AI 智能体平台转型售前工具） ──────────────────
@app.route("/api/admin/prd/generate", methods=["POST"])
@require_admin
def api_admin_prd_generate():
    """填「公司 + 业务介绍」→ 生成一份面向该客户的《AI 智能体平台功能需求 PRD》。

    mode=guide 引导（客户不懂，先给草稿+澄清问题）；mode=normalize 规范化（整理客户原始需求）。
    生成前会用知识库检索做行业接地（空库自动降级）。LLM 调用较慢，前端需 loading。
    """
    if rate_limited(request.remote_addr, limit=6, window=60):
        return jsonify({"error": "生成太频繁，请稍后再试"}), 429
    if not kb_prd.has_api_key():
        return jsonify({"error": "未配置 DASHSCOPE_API_KEY 环境变量，无法生成 PRD"}), 400
    payload = request.get_json(force=True, silent=True) or {}
    try:
        result = kb_prd.generate_prd(KB, payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": "生成失败：%s" % str(e)[:160]}), 502
    except Exception as e:
        return jsonify({"error": "生成失败：%s" % str(e)[:160]}), 500
    return jsonify(result)


# ── 平台智能体（A2：注册表框架 + planner 派发，实现在 agents/ 包） ───────────
@app.route("/api/agents", methods=["GET"])
def api_agents():
    """公开智能体注册表：status=live 的会被首页渲染成可体验入口。"""
    return jsonify(agents.list_agents(only_live=True))


@app.route("/api/agents/dispatch", methods=["POST"])
def api_agents_dispatch():
    """planner 派发：任务文本 → triggers 关键词路由到 live 智能体。

    body: {task, auto_run?, payload?}；auto_run=true 时代为执行并带回结果。
    """
    if rate_limited(request.remote_addr, limit=5, window=3600, bucket="agent_dispatch"):
        return jsonify({"error": "请求太频繁，请稍后再试"}), 429
    payload = request.get_json(force=True, silent=True) or {}
    task = (payload.get("task") or "").strip()
    if not task:
        return jsonify({"error": "task 不能为空"}), 400
    agent = agents.route_task(task)
    if agent is None:
        return jsonify({"ok": False, "matched": None,
                        "message": "暂无可处理该任务的智能体"}), 404
    out = {"ok": True, "matched": agent.id, "agent": agent.meta()}
    if payload.get("auto_run"):
        # 代跑结果作为子对象内嵌（代跑失败时 run 里是 {"error": ...}，外层仍 200）
        out["run"] = _run_agent(agent, payload.get("payload") or {}).get_json()
    return jsonify(out), 200


def _run_agent(agent, payload):
    """执行智能体并把异常收敛为带状态码的 Response，公开运行端点共用。

    注意：必须把状态码写回 Response 本体再返回——调用方若只拿 Response，
    元组里的 400/502/500 会被吞成 200（测试抓到过）。
    """
    try:
        out, status = jsonify(agent.run(payload)), 200
    except ValueError as e:
        out, status = jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        out, status = jsonify({"error": "执行失败：%s" % str(e)[:160]}), 502
    except Exception as e:
        out, status = jsonify({"error": "执行失败：%s" % str(e)[:160]}), 500
    out.status_code = status
    return out


@app.route("/api/agents/<agent_id>/run", methods=["POST"])
def api_agent_run(agent_id):
    """通用公开运行端点：注册表里 status=live 的智能体均可经此调用，按 agent 限流。"""
    agent = agents.get_agent(agent_id)
    if agent is None or agent.status != "live":
        return jsonify({"error": "智能体不存在或未上线"}), 404
    if rate_limited(request.remote_addr, limit=5, window=3600,
                    bucket="agent_%s" % agent_id):
        return jsonify({"error": "体验次数已达上限（每 IP 每小时 5 次），请稍后再试"}), 429
    if not agent.available():
        return jsonify({"error": "智能体暂不可用，请稍后再试"}), 503
    payload = request.get_json(force=True, silent=True) or {}
    return _run_agent(agent, payload)


@app.route("/api/agents/prd/run", methods=["POST"])
def api_agents_prd_run_legacy():
    """A1 兼容路径：旧前端包硬编码此地址；返回 A1 的扁平结果形状。"""
    agent = agents.get_agent("prd-advisor")
    if agent is None or agent.status != "live":
        return jsonify({"error": "智能体不存在或未上线"}), 404
    if rate_limited(request.remote_addr, limit=5, window=3600, bucket="agent_prd"):
        return jsonify({"error": "体验次数已达上限（每 IP 每小时 5 次），请稍后再试"}), 429
    if not agent.available():
        return jsonify({"error": "智能体暂不可用，请稍后再试"}), 503
    payload = request.get_json(force=True, silent=True) or {}
    res = _run_agent(agent, payload)
    flat = res.get_json()
    if res.status_code == 200 and isinstance(flat, dict) and "result" in flat:
        flat = dict(flat["result"]) if isinstance(flat["result"], dict) else flat["result"]
    return jsonify(flat), res.status_code


# ── 预约演示（离线项目卡的转化入口） ─────────────────────────────────────────
DEMO_BOOKINGS_FILE = os.path.join(DATA_DIR, "demo_bookings.json")


@app.route("/api/demo/booking", methods=["POST"])
def api_demo_booking():
    """公开预约：称呼+联系方式必填；落盘后尝试邮件通知（发送失败不影响受理）。"""
    if rate_limited(request.remote_addr, limit=3, window=3600, bucket="demo_booking"):
        return jsonify({"error": "提交太频繁，请稍后再试"}), 429
    p = request.get_json(force=True, silent=True) or {}
    name = (p.get("name") or "").strip()[:40]
    contact = (p.get("contact") or "").strip()[:80]
    project = (p.get("project") or "").strip()[:60]
    note = (p.get("note") or "").strip()[:500]
    if not name:
        return jsonify({"error": "请填写称呼"}), 400
    if len(contact) < 5:
        return jsonify({"error": "请填写有效联系方式（电话/微信/邮箱）"}), 400
    record = {
        "id": secrets.token_hex(8),
        "name": name, "contact": contact, "project": project, "note": note,
        "ip": request.remote_addr,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "notified": False,
    }
    ok, _detail = notify.send_email(
        "【预约演示】%s 想看 %s" % (name, project or "某个项目"),
        "新预约演示\n时间：%s\n称呼：%s\n联系方式：%s\n想看项目：%s\n备注：%s\nIP：%s\n"
        % (record["ts"], name, contact, project or "-", note or "-", record["ip"]))
    record["notified"] = ok
    bookings = load_json(DEMO_BOOKINGS_FILE, [])
    bookings.append(record)
    save_json(DEMO_BOOKINGS_FILE, bookings[-200:])
    return jsonify({"ok": True, "notified": ok, "message": "已收到您的预约，我们会尽快与您联系"})


@app.route("/api/admin/demo/bookings", methods=["GET"])
@require_admin
def api_admin_demo_bookings():
    """后台预约列表（新→旧），供管理端「预约」页签查看。"""
    return jsonify(list(reversed(load_json(DEMO_BOOKINGS_FILE, []))))


@app.route("/api/admin/links", methods=["GET", "POST"])
@require_admin
def api_admin_links():
    if request.method == "GET":
        return jsonify(KB.list_links())
    payload = request.get_json(force=True, silent=True) or {}
    try:
        links = KB.save_link(payload)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(links)


@app.route("/api/admin/links/<link_id>", methods=["DELETE"])
@require_admin
def api_admin_links_delete(link_id):
    return jsonify(KB.delete_link(link_id))


@app.route("/api/admin/links/<link_id>/crawl", methods=["POST"])
@require_admin
def api_admin_links_crawl(link_id):
    """从友情链接一键采集入库。"""
    link = next((l for l in KB.list_links() if l["id"] == link_id), None)
    if not link:
        return jsonify({"error": "链接不存在"}), 404
    try:
        doc = _crawl_to_kb(link["url"], doc_type="link")
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "采集失败：%s" % str(e)[:160]}), 502
    return jsonify({"doc": doc, "message": "「%s」采集成功，已入库" % link["name"]})


# 静态文件服务（处理 SPA 路由）
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path and os.path.exists(os.path.join(DIST_DIR, path)):
        return send_from_directory(DIST_DIR, path)
    return send_from_directory(DIST_DIR, "index.html")


if __name__ == "__main__":
    import sys
    port = int(os.environ.get("PORT", "8804"))
    app.run(host="0.0.0.0", port=port, threaded=True)
