# -*- coding: utf-8 -*-
"""WeKnora 引擎管理转发域（R5 自 kb_admin.py 拆出）：管理界面在引擎开启时
改走这组端点，所有 WeKnora 调用收口在 rag/engine.py。

Blueprint + 依赖注入（同 kb_admin 模式）；WEKNORA_ENABLED=false 时前端
自动回退旧界面（kb_admin 的旧端点原样保留，就是回滚网本身）。
"""
from flask import Blueprint, request, jsonify

from rag import engine as wk_engine
from kb_admin import ALLOWED_KB_EXTS, MAX_KB_SIZE

bp = Blueprint("kb_weknora", __name__)


def init(require_admin_dec):
    """装配注入：admin 路由统一挂 require_admin 后注册。"""
    for rule, endpoint, fn, methods in _ADMIN_ROUTES:
        bp.add_url_rule(rule, endpoint,
                        view_func=require_admin_dec(fn), methods=methods)


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


_ADMIN_ROUTES = [
    ("/api/admin/kb/weknora/status", "api_admin_kb_weknora_status", _admin_kb_weknora_status, ["GET"]),
    ("/api/admin/kb/weknora/docs", "api_admin_kb_weknora_docs", _admin_kb_weknora_docs, ["GET"]),
    ("/api/admin/kb/weknora/upload", "api_admin_kb_weknora_upload", _admin_kb_weknora_upload, ["POST"]),
    ("/api/admin/kb/weknora/docs/<kid>", "api_admin_kb_weknora_doc", _admin_kb_weknora_doc, ["GET"]),
    ("/api/admin/kb/weknora/docs/<kid>", "api_admin_kb_weknora_delete", _admin_kb_weknora_delete, ["DELETE"]),
    ("/api/admin/kb/weknora/search", "api_admin_kb_weknora_search", _admin_kb_weknora_search, ["POST"]),
]
