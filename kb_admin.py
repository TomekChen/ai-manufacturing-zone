# -*- coding: utf-8 -*-
"""知识库管理域（R4 自 app.py 拆出）：文档审核/采集/重建、WeKnora 引擎转发、
问答遥测看板、离线评测、友情链接。

Blueprint + 依赖注入（同 prd_sessions 模式）：本模块不 import app，app.py 装配时
调用 init(kb, require_admin_dec, data_dir) 注入共享设施后 register_blueprint。
对外的 HTTP 路由与数据形状与拆分前完全一致。

公开路由直接 @bp.route；admin 路由在 init() 里统一挂 require_admin 后注册
（require_admin 到装配时才可用）。
"""
from flask import Blueprint, request, jsonify

bp = Blueprint("kb_admin", __name__)

_kb = None       # app.KB（rag.store.KnowledgeStore）
_data_dir = None

# 知识库文档约束（公开上传与管理端上传共用；app.py 也从这里取）
ALLOWED_KB_EXTS = {"txt", "md", "pdf"}
MAX_KB_SIZE = 10 * 1024 * 1024  # 知识库文档 10MB

from rag import config as rag_config  # noqa: E402
from rag import engine as wk_engine   # noqa: E402
from rag import evaluate as kb_eval   # noqa: E402
from rag.ingest import fetch_url_text, looks_like_nav_page  # noqa: E402
from rag.chunkers import CHUNKERS as _CHUNKERS  # noqa: E402
from rag.retrievers import RETRIEVERS as _RETRIEVERS  # noqa: E402

CHUNKING_OPTIONS = _CHUNKERS.names()
DEFAULT_CHUNKING = rag_config.DEFAULT_CHUNKING
RETRIEVAL_OPTIONS = _RETRIEVERS.names()
DEFAULT_RETRIEVAL = rag_config.DEFAULT_RETRIEVAL
TELEM_TREND_DAYS = rag_config.TELEM_TREND_DAYS


def clean_choice(raw, options):
    """可选入参清洗：空 / 非法值 -> None（交回后端默认），合法值 -> 原样返回。
    在信任边界挡住未知策略名，避免注入注册表里没有的 key。"""
    v = (raw or "").strip()
    return v if v in options else None


def init(kb, require_admin_dec, data_dir):
    """装配注入：知识库实例、管理员鉴权装饰器、数据目录（评测历史用）。"""
    global _kb, _data_dir
    _kb = kb
    _data_dir = data_dir
    for rule, endpoint, fn, methods in _ADMIN_ROUTES:
        bp.add_url_rule(rule, endpoint,
                        view_func=require_admin_dec(fn), methods=methods)


def _crawl_to_kb(url, doc_type="url", chunking=None):
    """抓取 URL 并直接以 approved 状态入库（管理员操作，视为已审核）。"""
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("地址必须以 http:// 或 https:// 开头")
    title, text = fetch_url_text(url)
    if not text or len(text.strip()) < 30:
        raise RuntimeError("页面正文内容太少，无法入库")
    if looks_like_nav_page(text):
        raise RuntimeError("抓到的内容像是网站首页/栏目列表（全是标题、没有正文），请粘贴具体文章的详情页地址")
    doc = _kb.add_text(text, title=title or url, url=url,
                       doc_type=doc_type, status="approved", chunking=chunking)
    return doc


# ── 公开路由 ────────────────────────────────────────────────────────────────
@bp.route("/api/kb/stats", methods=["GET"])
def api_kb_stats():
    return jsonify(_kb.stats())


@bp.route("/api/links", methods=["GET"])
def api_links():
    return jsonify(_kb.list_links())


# ── 文档审核（公开上传后管理员把关） ────────────────────────────────────────
def _admin_kb_docs():
    return jsonify({"docs": _kb.list_docs(), "stats": _kb.stats()})


def _admin_kb_doc_detail(doc_id):
    """管理员预览单条文档及分块内容。"""
    try:
        detail = _kb.get_doc_detail(doc_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "加载失败：%s" % str(e)[:120]}), 500
    return jsonify(detail)


def _admin_kb_approve(doc_id):
    try:
        doc = _kb.approve(doc_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "入库失败：%s" % str(e)[:120]}), 502
    return jsonify({"doc": doc, "stats": _kb.stats()})


def _admin_kb_reject(doc_id):
    try:
        doc = _kb.reject(doc_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"doc": doc, "stats": _kb.stats()})


def _admin_kb_delete(doc_id):
    try:
        _kb.delete(doc_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"docs": _kb.list_docs(), "stats": _kb.stats()})


# ── 采集 / 重建 / 下拉数据源 ────────────────────────────────────────────────
def _admin_kb_crawl():
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
    chunking = clean_choice(payload.get("chunking"), CHUNKING_OPTIONS)
    try:
        doc = _crawl_to_kb(url, chunking=chunking)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "采集失败：%s" % str(e)[:160]}), 502
    return jsonify({"doc": doc, "message": "采集成功，已入库"})


def _admin_kb_options():
    """后台下拉框数据源：可选的分块/检索策略及默认值（单一事实来源=注册表，前端不再硬编码）。
    engine 字段供前端判定走 WeKnora 模式还是旧模式（WEKNORA_ENABLED 回退开关）。"""
    return jsonify({
        "chunking": CHUNKING_OPTIONS,
        "default_chunking": DEFAULT_CHUNKING,
        "retrieval": RETRIEVAL_OPTIONS,
        "default_retrieval": DEFAULT_RETRIEVAL,
        "engine": wk_engine.status(),
    })


def _admin_kb_rebuild_all():
    """全库重建：按各文档记录的分块策略重新切块 + 重嵌入（会重花 embedding 额度）。"""
    try:
        result = _kb.rebuild_all()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "重建失败：%s" % str(e)[:160]}), 502
    return jsonify({
        "result": result, "stats": _kb.stats(),
        "message": "全库重建完成（共 %d 篇 / %d 块）" % (result["docs"], result["chunks"]),
    })


def _admin_kb_rebuild_doc(doc_id):
    """单篇重建：可选换分块策略后重新切块 + 重嵌入。"""
    payload = request.get_json(force=True, silent=True) or {}
    chunking = clean_choice(payload.get("chunking"), CHUNKING_OPTIONS)
    try:
        result = _kb.rebuild_doc(doc_id, chunking=chunking)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except KeyError as e:
        return jsonify({"error": "未知分块策略：%s" % str(e)[:80]}), 400
    except Exception as e:
        return jsonify({"error": "重建失败：%s" % str(e)[:160]}), 502
    return jsonify({
        "doc": result["doc"], "stats": _kb.stats(), "re_sharded": result["re_sharded"],
        "message": "单篇重建完成：%d 块" % result["chunks"],
    })


# ── WeKnora 引擎转发（W2）：管理界面在引擎开启时改走这组端点 ────────────────
# SPEC：所有 WeKnora 调用收口在 rag/engine.py；WEKNORA_ENABLED=false 时前端
# 自动回退旧界面（下方旧端点原样保留，就是回滚网本身）。

def _admin_kb_weknora_status():
    """引擎概览：是否启用/是否已配置/健康检查。"""
    st = wk_engine.status()
    st["healthy"] = wk_engine.health() if st["configured"] else None
    return jsonify(st)


def _admin_kb_weknora_docs():
    """WeKnora 文档列表（含解析状态）。"""
    if not wk_engine.is_enabled():
        return jsonify({"error": "WeKnora 引擎未启用"}), 409
    try:
        return jsonify(wk_engine.list_docs())
    except wk_engine.EngineError as e:
        return jsonify({"error": str(e)}), 502


def _admin_kb_weknora_upload():
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


def _admin_kb_weknora_doc(kid):
    """单文档：解析状态 + 分块预览。"""
    if not wk_engine.is_enabled():
        return jsonify({"error": "WeKnora 引擎未启用"}), 409
    try:
        detail = wk_engine.doc_detail(kid)
        chunks = wk_engine.doc_chunks(kid)
    except wk_engine.EngineError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"doc": detail, "chunks": chunks})


def _admin_kb_weknora_delete(kid):
    if not wk_engine.is_enabled():
        return jsonify({"error": "WeKnora 引擎未启用"}), 409
    try:
        wk_engine.delete_doc(kid)
    except wk_engine.EngineError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"ok": True})


def _admin_kb_weknora_search():
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


# ── 遥测看板 / 离线评测 ─────────────────────────────────────────────────────
def _admin_kb_analytics():
    """问答看板聚合（Slice 4）：总量/拒绝率/各策略对比/时间趋势/👍👎/未命中清单。"""
    try:
        days = int(request.args.get("days") or TELEM_TREND_DAYS)
    except (TypeError, ValueError):
        days = TELEM_TREND_DAYS
    days = max(1, min(90, days))
    try:
        data = _kb.telemetry.aggregate(days=days)
    except Exception as e:
        return jsonify({"error": "统计失败：%s" % str(e)[:120]}), 500
    return jsonify(data)


def _admin_kb_eval_run():
    """启动一次后台评测（Slice 6，管理员手动触发才花额度）。已跑→409；无 API Key→400；正常→202 带启动快照。"""
    try:
        info = kb_eval.start(_kb, _data_dir)
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


def _admin_kb_eval_status():
    """轮询用：返回当前进度与最近一次已完成结果的摘要。"""
    return jsonify(kb_eval.get_state())


def _admin_kb_eval_results():
    """评测历史：滚动上限由 config.EVAL_MAX_RESULTS 控制；支持 ?limit=N 只取最近几条。"""
    try:
        limit = int(request.args.get("limit") or kb_eval.config.EVAL_MAX_RESULTS)
    except (TypeError, ValueError):
        limit = kb_eval.config.EVAL_MAX_RESULTS
    limit = max(1, min(kb_eval.config.EVAL_MAX_RESULTS, limit))
    try:
        history = kb_eval.EvalStore(_data_dir).load()
    except Exception as e:
        return jsonify({"error": "读取评测历史失败：%s" % str(e)[:120]}), 500
    return jsonify({
        "metrics": list(kb_eval.config.EVAL_METRICS),
        "labels": kb_eval.METRIC_LABELS,
        "history": history[-limit:],
    })


# ── 友情链接（门户展示 + 一键采集入库） ─────────────────────────────────────
def _admin_links():
    if request.method == "GET":
        return jsonify(_kb.list_links())
    payload = request.get_json(force=True, silent=True) or {}
    try:
        links = _kb.save_link(payload)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(links)


def _admin_links_delete(link_id):
    return jsonify(_kb.delete_link(link_id))


def _admin_links_crawl(link_id):
    """从友情链接一键采集入库。"""
    link = next((l for l in _kb.list_links() if l["id"] == link_id), None)
    if not link:
        return jsonify({"error": "链接不存在"}), 404
    try:
        doc = _crawl_to_kb(link["url"], doc_type="link")
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "采集失败：%s" % str(e)[:160]}), 502
    return jsonify({"doc": doc, "message": "「%s」采集成功，已入库" % link["name"]})


_ADMIN_ROUTES = [
    ("/api/admin/kb/docs", "api_admin_kb_docs", _admin_kb_docs, ["GET"]),
    ("/api/admin/kb/docs/<doc_id>", "api_admin_kb_doc_detail", _admin_kb_doc_detail, ["GET"]),
    ("/api/admin/kb/docs/<doc_id>/approve", "api_admin_kb_approve", _admin_kb_approve, ["POST"]),
    ("/api/admin/kb/docs/<doc_id>/reject", "api_admin_kb_reject", _admin_kb_reject, ["POST"]),
    ("/api/admin/kb/docs/<doc_id>", "api_admin_kb_delete", _admin_kb_delete, ["DELETE"]),
    ("/api/admin/kb/crawl", "api_admin_kb_crawl", _admin_kb_crawl, ["POST"]),
    ("/api/admin/kb/options", "api_admin_kb_options", _admin_kb_options, ["GET"]),
    ("/api/admin/kb/rebuild", "api_admin_kb_rebuild_all", _admin_kb_rebuild_all, ["POST"]),
    ("/api/admin/kb/docs/<doc_id>/rebuild", "api_admin_kb_rebuild_doc", _admin_kb_rebuild_doc, ["POST"]),
    ("/api/admin/kb/weknora/status", "api_admin_kb_weknora_status", _admin_kb_weknora_status, ["GET"]),
    ("/api/admin/kb/weknora/docs", "api_admin_kb_weknora_docs", _admin_kb_weknora_docs, ["GET"]),
    ("/api/admin/kb/weknora/upload", "api_admin_kb_weknora_upload", _admin_kb_weknora_upload, ["POST"]),
    ("/api/admin/kb/weknora/docs/<kid>", "api_admin_kb_weknora_doc", _admin_kb_weknora_doc, ["GET"]),
    ("/api/admin/kb/weknora/docs/<kid>", "api_admin_kb_weknora_delete", _admin_kb_weknora_delete, ["DELETE"]),
    ("/api/admin/kb/weknora/search", "api_admin_kb_weknora_search", _admin_kb_weknora_search, ["POST"]),
    ("/api/admin/kb/analytics", "api_admin_kb_analytics", _admin_kb_analytics, ["GET"]),
    ("/api/admin/kb/eval/run", "api_admin_kb_eval_run", _admin_kb_eval_run, ["POST"]),
    ("/api/admin/kb/eval/status", "api_admin_kb_eval_status", _admin_kb_eval_status, ["GET"]),
    ("/api/admin/kb/eval/results", "api_admin_kb_eval_results", _admin_kb_eval_results, ["GET"]),
    ("/api/admin/links", "api_admin_links", _admin_links, ["GET", "POST"]),
    ("/api/admin/links/<link_id>", "api_admin_links_delete", _admin_links_delete, ["DELETE"]),
    ("/api/admin/links/<link_id>/crawl", "api_admin_links_crawl", _admin_links_crawl, ["POST"]),
]
