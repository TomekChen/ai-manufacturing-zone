# -*- coding: utf-8 -*-
"""售前方案会话账本（A4，自 app.py 拆出）：生成即存档、版本回放、只读分享。

Blueprint + 依赖注入（同 agents/runtime 的模式）：本模块不 import app，
app.py 装配时调用 init(data_dir, rate_limited_fn, require_admin_dec) 注入
共享设施后 register_blueprint。对外的 HTTP 路由与数据形状与拆分前完全一致。

存储：data/prd_sessions.json，append-only——旧版本永不修改，留最近 100 个会话。
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, Response

bp = Blueprint("prd_sessions", __name__)

# 依赖注入槽（app.py 装配时填充）
_data_dir = None
_load_json = None     # app.load_json
_save_json = None     # app.save_json
_rate_limited = None  # app.rate_limited(ip, limit, window, bucket)
_kb = None            # app.KB（rag.store.KnowledgeStore）——know-how 入库用


def init(data_dir, load_json_fn, save_json_fn, rate_limited_fn, require_admin_dec, kb=None):
    """装配注入：存储目录、读写工具、限流函数、管理员鉴权装饰器、知识库。

    admin 端点在这里动态注册——require_admin 到此时才可用。
    """
    global _data_dir, _load_json, _save_json, _rate_limited, _kb
    _data_dir = data_dir
    _load_json = load_json_fn
    _save_json = save_json_fn
    _rate_limited = rate_limited_fn
    _kb = kb
    bp.add_url_rule("/api/admin/prd-sessions", "api_admin_prd_sessions",
                    view_func=require_admin_dec(_admin_prd_sessions),
                    methods=["GET"])
    bp.add_url_rule("/api/admin/prd-sessions/<sid>/ingest",
                    "api_admin_prd_session_ingest",
                    view_func=require_admin_dec(_api_prd_session_ingest),
                    methods=["POST"])


import json  # noqa: E402
import os    # noqa: E402
import secrets  # noqa: E402
import html  # noqa: E402


def _sessions_file():
    return os.path.join(_data_dir, "prd_sessions.json")


@bp.route("/api/prd-sessions", methods=["POST"])
def api_prd_session_save():
    """保存一次生成结果：无 session_id 新建会话（v1），有则追加版本（v+1）。

    旧版本永不修改（可回放的"账本"），会话留最近 100 个防膨胀。
    body: {session_id?, title?, inputs: {...}, result: {...}}
    """
    if _rate_limited(request.remote_addr, limit=30, window=3600, bucket="prd_session"):
        return jsonify({"error": "保存太频繁，请稍后再试"}), 429
    p = request.get_json(force=True, silent=True) or {}
    inputs = p.get("inputs") if isinstance(p.get("inputs"), dict) else {}
    result = p.get("result") if isinstance(p.get("result"), dict) else {}
    prd_text = (result.get("prd") or "").strip()
    if not prd_text:
        return jsonify({"error": "result.prd 不能为空"}), 400
    title = (p.get("title") or inputs.get("company") or "").strip()[:60]
    if not title:
        return jsonify({"error": "缺少会话标题（title 或 inputs.company）"}), 400
    sid = (p.get("session_id") or "").strip()
    sessions = _load_json(_sessions_file(), [])
    now = datetime.now().isoformat(timespec="seconds")
    sess = None
    if sid:
        sess = next((s for s in sessions if s.get("id") == sid), None)
    if sess is None:
        # 新会话（含传入了未知 session_id 的情况：重新开一个，不炸）
        sess = {"id": secrets.token_hex(8), "title": title, "created": now,
                "updated": now, "versions": []}
        sessions.append(sess)
    version = {"no": len(sess["versions"]) + 1, "ts": now,
               "inputs": inputs, "result": result}
    sess["versions"].append(version)
    sess["updated"] = now
    if not sess.get("title"):
        sess["title"] = title
    _save_json(_sessions_file(), sessions[-100:])
    return jsonify({"ok": True, "session_id": sess["id"], "version": version["no"]})


@bp.route("/api/prd-sessions/<sid>", methods=["GET"])
def api_prd_session_get(sid):
    """读取一个会话（含全部版本），前端回放历史用。"""
    sess = next((s for s in _load_json(_sessions_file(), []) if s.get("id") == sid),
                None)
    if sess is None:
        return jsonify({"error": "会话不存在"}), 404
    return jsonify(sess)


def _admin_prd_sessions():
    """后台方案会话列表（新→旧）：只回摘要不带全文，够管理端盘点沉淀量。"""
    rows = []
    for s in reversed(_load_json(_sessions_file(), [])):
        versions = s.get("versions") or []
        rows.append({
            "id": s.get("id"), "title": s.get("title"),
            "created": s.get("created"), "updated": s.get("updated"),
            "version_count": len(versions),
            "ingested": bool(s.get("ingested")),
        })
    return jsonify(rows)


def _api_prd_session_ingest(sid):
    """know-how 入库飞轮：把会话最新版方案存入知识库（status=pending）。

    管理员点入库 → 文档进待审 → 管理后台「知识库」页签批准 → 知识管家可引用。
    一个会话只入一次（幂等防重复文档），已入库返回 409 + doc_id。
    """
    if _kb is None:
        return jsonify({"error": "知识库未装配"}), 503
    sessions = _load_json(_sessions_file(), [])
    sess = next((s for s in sessions if s.get("id") == sid), None)
    if sess is None:
        return jsonify({"error": "会话不存在"}), 404
    if sess.get("ingested"):
        return jsonify({"error": "该会话已入库", "doc_id": sess["ingested"].get("doc_id")}), 409
    versions = sess.get("versions") or []
    latest = versions[-1] if versions else None
    prd = str(((latest or {}).get("result") or {}).get("prd") or "").strip()
    if not prd:
        return jsonify({"error": "会话没有可入库的方案正文"}), 400
    title = sess.get("title") or "售前方案会话"
    text = ("# %s\n\n> 来源：售前方案会话沉淀（共 %d 个版本，本篇取最新 v%s）\n\n%s"
            % (title, len(versions), (latest or {}).get("no", "?"), prd))
    doc = _kb.add_text(text, title=title, doc_type="session",
                       status="pending", url="/s/%s" % sid)
    sess["ingested"] = {"doc_id": doc.get("id"),
                        "ts": datetime.now().isoformat(timespec="seconds")}
    _save_json(_sessions_file(), sessions[-100:])
    return jsonify({"ok": True,
                    "doc": {"id": doc.get("id"), "title": doc.get("title"),
                            "status": doc.get("status")}})


_SHARE_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · 售前方案会话</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background: #f6f7f9; color: #1f2328; }}
  header {{ background: #fff; border-bottom: 1px solid #e5e7eb; padding: 18px 24px; }}
  header h1 {{ margin: 0; font-size: 18px; }}
  header .sub {{ margin-top: 6px; font-size: 13px; color: #6b7280; }}
  main {{ max-width: 860px; margin: 24px auto; padding: 0 16px; }}
  .ver {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 10px;
         margin-bottom: 20px; overflow: hidden; }}
  .ver-bar {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
             padding: 12px 16px; border-bottom: 1px solid #f0f1f3; }}
  .badge {{ font-size: 12px; padding: 2px 10px; border-radius: 999px;
           background: #f3f4f6; border: 1px solid #e5e7eb; color: #6b7280; }}
  .badge.ok {{ color: #15803d; background: #f0fdf4; border-color: #bbf7d0; }}
  .ver.no {{ font-weight: 600; font-size: 14px; margin-right: 4px; }}
  .ver pre {{ margin: 0; padding: 16px; white-space: pre-wrap; word-break: break-word;
             font-size: 14px; line-height: 1.7; font-family: inherit; }}
  footer {{ text-align: center; color: #9ca3af; font-size: 12px; padding: 24px 0 40px; }}
</style>
</head>
<body>
<header>
  <h1>🧭 {title} · 售前方案会话</h1>
  <div class="sub">智能制造专区 · 由售前方案师生成 · 只读分享（共 {nver} 个版本，旧版本保留可追溯）</div>
</header>
<main>
{versions}
</main>
<footer>让每家制造厂，都有自己的 AI 供应商</footer>
</body>
</html>"""

_SHARE_VERSION = """<div class="ver" id="v{no}">
  <div class="ver-bar">
    <span class="ver no">v{no}</span>
    <span class="badge">{ts}</span>
    <span class="badge">{mode}</span>
    {grounded}
  </div>
  <pre>{prd}</pre>
</div>"""


@bp.route("/s/<sid>", methods=["GET"])
def prd_session_share(sid):
    """方案会话只读分享页：无登录，收链接的人直接看全部版本（最新在前）。"""
    sess = next((s for s in _load_json(_sessions_file(), []) if s.get("id") == sid),
                None)
    if sess is None:
        return jsonify({"error": "会话不存在"}), 404
    parts = []
    for v in reversed(sess.get("versions", [])):
        res = v.get("result") or {}
        grounded = ('<span class="badge ok">已接地知识库 %s 条</span>' % res.get("hits")
                    if res.get("grounded") else
                    '<span class="badge">未接地知识库</span>')
        parts.append(_SHARE_VERSION.format(
            no=html.escape(str(v.get("no", "?"))),
            ts=html.escape(str(v.get("ts", ""))),
            mode=html.escape("引导模式" if res.get("mode") == "guide" else "规范化模式"),
            grounded=grounded,
            prd=html.escape(str(res.get("prd") or "")),
        ))
    page = _SHARE_PAGE.format(
        title=html.escape(str(sess.get("title") or "方案会话")),
        nver=len(sess.get("versions", [])),
        versions="\n".join(parts),
    )
    return Response(page, mimetype="text/html")
