# -*- coding: utf-8 -*-
"""WeKnora 引擎收口层（W2）。

SPEC（WEKNORA_INTEGRATION_SPEC.md 第五节）：所有对 WeKnora LITE sidecar 的 HTTP
调用只允许走本模块；WEKNORA_ENABLED=false 时调用方回退旧 rag 链路（回滚网）。

鉴权说明（按 v0.7.2 Go 源码核对，勿改字段名）：
  - API Key 请求头是 X-API-Key: sk-...，不是 Authorization: Bearer。
  - scoped key 能力：retrieve / chat / ingest / manage_kbs，且限定 KB 白名单。
  - sk- token 仅在创建时返回一次（列表接口不回显）。

env：
  WEKNORA_ENABLED    1/true/on 开；其余关（关=回退旧链路）
  WEKNORA_BASE_URL   默认 http://weknora-app:8080（portal 加入 weknora-lite_wknet 外部网络）
  WEKNORA_API_KEY    sk-...
  WEKNORA_KB_ID      「智能制造专区」知识库 id
  WEKNORA_TIMEOUT    单请求超时秒数，默认 60
"""
import json
import logging
import os

import requests

log = logging.getLogger("wk.engine")

_BASE = os.environ.get("WEKNORA_BASE_URL", "http://weknora-app:8080").rstrip("/")
_API_KEY = os.environ.get("WEKNORA_API_KEY", "")
_KB_ID = os.environ.get("WEKNORA_KB_ID", "")
_TIMEOUT = int(os.environ.get("WEKNORA_TIMEOUT", "60"))


class EngineError(RuntimeError):
    """WeKnora 调用失败（网络不可达 / HTTP >= 400）。"""


def is_enabled():
    """回退开关：未开或缺关键配置一律按未启用处理（调用方走旧链路）。"""
    if os.environ.get("WEKNORA_ENABLED", "").lower() not in ("1", "true", "on", "yes"):
        return False
    if not _API_KEY or not _KB_ID:
        log.warning("WEKNORA_ENABLED 已开但缺少 WEKNORA_API_KEY / WEKNORA_KB_ID")
        return False
    return True


def status():
    """引擎概览（不发请求，供 /options 与前端模式判定）。"""
    kb_id = _KB_ID
    return {
        "enabled": is_enabled(),
        "configured": bool(_API_KEY and _KB_ID),
        "kb_id": (kb_id[:8] + "…") if kb_id else "",
        "base_url": _BASE,
    }


def _headers(extra=None):
    h = {"X-API-Key": _API_KEY}
    if extra:
        h.update(extra)
    return h


def _call(method, path, timeout=None, **kw):
    """统一请求入口：非 2xx 抛 EngineError（带 WeKnora 的错误消息）。"""
    url = _BASE + "/api/v1" + path
    try:
        r = requests.request(method, url, headers=_headers(kw.pop("headers", None)),
                             timeout=timeout or _TIMEOUT, **kw)
    except requests.exceptions.RequestException as e:
        raise EngineError("WeKnora 不可达：%s" % str(e)[:120])
    if r.status_code >= 400:
        msg = ""
        try:
            j = r.json()
            err = j.get("error")
            msg = err.get("message") if isinstance(err, dict) else (err or j.get("message") or "")
        except Exception:
            msg = (r.text or "")[:160]
        raise EngineError("WeKnora HTTP %d：%s" % (r.status_code, msg or "未知错误"))
    return r


def health():
    """引擎健康：能建立连接且非 5xx 即在线（8805 仅内网/本机，管理员自查用）。"""
    try:
        r = requests.get(_BASE + "/health", timeout=5)
        return r.status_code < 500
    except requests.exceptions.RequestException:
        return False


# ---------------------------------------------------------------- 文档管理

def list_docs(page=1, page_size=100):
    """文档列表（GET /knowledge-bases/{kb}/knowledge）。解析异步：看 parse_status。"""
    r = _call("GET", "/knowledge-bases/%s/knowledge" % _KB_ID,
              params={"page": page, "page_size": page_size})
    data = r.json().get("data")
    items = data.get("items") if isinstance(data, dict) else data
    items = items or []
    total = r.json().get("total")
    if total is None:
        total = data.get("total") if isinstance(data, dict) else len(items)
    docs = [{
        "id": it.get("id"),
        "title": it.get("title") or it.get("file_name") or "(未命名)",
        "file_name": it.get("file_name") or "",
        "parse_status": it.get("parse_status") or "unknown",
        "summary_status": it.get("summary_status") or "",
        "file_type": it.get("file_type") or "",
        "file_size": it.get("file_size") or 0,
        "error_message": it.get("error_message") or "",
        "created_at": (it.get("created_at") or "")[:19].replace("T", " "),
    } for it in items]
    return {"total": total or len(docs), "docs": docs}


def doc_detail(knowledge_id):
    """单文档详情/解析状态（GET /knowledge/{id}）。"""
    r = _call("GET", "/knowledge/%s" % knowledge_id)
    return r.json().get("data") or {}


def doc_chunks(knowledge_id, page=1, page_size=200):
    """分块预览（GET /chunks/{knowledge_id}）。"""
    r = _call("GET", "/chunks/%s" % knowledge_id,
              params={"page": page, "page_size": page_size})
    data = r.json().get("data")
    return data.get("items") if isinstance(data, dict) else (data or [])


def upload_file(filename, blob):
    """上传文档（POST /knowledge-bases/{kb}/knowledge/file，multipart）。
    解析在 WeKnora 异步执行，返回文档 id，状态轮询 list_docs / doc_detail。"""
    r = _call("POST", "/knowledge-bases/%s/knowledge/file" % _KB_ID, timeout=600,
              files={"file": (filename, blob)},
              data={"enable_multimodel": "false"})
    return (r.json().get("data") or {}).get("id")


def upload_url(url):
    """URL 采集入库（POST /knowledge-bases/{kb}/knowledge/url，异步解析）。"""
    r = _call("POST", "/knowledge-bases/%s/knowledge/url" % _KB_ID,
              json={"url": url, "enable_multimodel": False})
    return r.json().get("data") or {}


def delete_doc(knowledge_id):
    """删除文档及其分块（DELETE /knowledge/{id}）。"""
    _call("DELETE", "/knowledge/%s" % knowledge_id)


def reparse(knowledge_id):
    """重新解析（POST /knowledge/{id}/reparse）。"""
    _call("POST", "/knowledge/%s/reparse" % knowledge_id)


# ---------------------------------------------------------------- 检索 / 问答

def _to_float(v):
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None


def search(query, top_k=None):
    """直接检索（POST /knowledge-search）。
    注意：此端点返回的是关键词式分数（~0.0x），与问答链路的向量分（0.3+）
    两套尺度不可混比（批次1测试结论）。"""
    payload = {"query": query, "knowledge_base_ids": [_KB_ID]}
    if top_k:
        payload["top_k"] = top_k
    r = _call("POST", "/knowledge-search", json=payload, timeout=90)
    hits = r.json().get("data") or []
    return [{
        "chunk_id": h.get("id"),
        "knowledge_id": h.get("knowledge_id"),
        "filename": h.get("knowledge_filename") or h.get("knowledge_title") or "",
        "content": h.get("content") or "",
        "score": _to_float(h.get("score")),
    } for h in hits]


def search_context(query, top_k=None):
    """检索并归一成旧链路 hit 形状 {doc:{title,url}, text, score}——W4 起 PRD 接地与
    离线评测共用，调用方代码零改动即可换底座。score 是 knowledge-search 的关键词式
    分数（仅排序参考，勿与旧向量分混比，批次1测试结论）。"""
    return [{
        "doc": {"title": h["filename"], "url": ""},
        "text": h["content"],
        "score": h["score"],
    } for h in search(query, top_k)]


def _norm_refs(refs):
    """把 knowledge_references 归一成前端易用的 [{title, knowledge_id, snippet}]。"""
    out = []
    for ref in refs or []:
        if not isinstance(ref, dict):
            continue
        out.append({
            "title": ref.get("filename") or ref.get("file_name")
                     or ref.get("knowledge_title") or "(未命名)",
            "knowledge_id": ref.get("knowledge_id") or "",
            "chunk_id": ref.get("chunk_id") or "",
            "snippet": (ref.get("content") or "")[:160],
        })
    return out


def chat(question, session_id=None, timeout_s=300):
    """会话问答（POST /sessions + POST /knowledge-chat/{sid}，SSE 聚合）。
    返回 (answer, references, session_id)；W3 接入 /api/kb/ask 时携带 session_id
    即可多轮续聊。"""
    if not session_id:
        r = _call("POST", "/sessions", json={"title": (question or "portal")[:40]},
                  timeout=30)
        session_id = (r.json().get("data") or {}).get("id")
        if not session_id:
            raise EngineError("创建 WeKnora 会话失败")
    payload = {"query": question, "knowledge_base_ids": [_KB_ID], "disable_title": True}
    url = "%s/api/v1/knowledge-chat/%s" % (_BASE, session_id)
    # SSE 解析教训（批次1 + W3 真机）：帧顶层字段是 response_type（不是 type）；
    # 答案增量 = response_type=="answer" 帧的【顶层 content】（data 里只有 event_id）；
    # 引用 = references 帧顶层 knowledge_references；协议无全量回显字段，只能增量拼接。
    parts, references = [], []
    try:
        with requests.post(url, json=payload, stream=True, timeout=(10, timeout_s),
                           headers=_headers({"Content-Type": "application/json"})) as resp:
            if resp.status_code >= 400:
                raise EngineError("WeKnora HTTP %d" % resp.status_code)
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                try:
                    frame = json.loads(line[5:].strip())
                except Exception:
                    continue
                if not isinstance(frame, dict):
                    continue
                etype = str(frame.get("response_type") or frame.get("type")
                            or frame.get("event") or "")
                if etype == "answer":
                    delta = frame.get("content")
                    if isinstance(delta, str) and delta:
                        parts.append(delta)
                refs = frame.get("knowledge_references")
                if refs:
                    references = _norm_refs(refs)
    except requests.exceptions.RequestException as e:
        raise EngineError("WeKnora 问答中断：%s" % str(e)[:120])
    return "".join(parts), references, session_id