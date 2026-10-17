# -*- coding: utf-8 -*-
"""网页抓单（A8 增强③，学 OpenMuse durable tasks 的浏览器 worker 思路）：

客户订单只存在于他们自己的门户网站（无邮件、无 API）时，管理端配置网页来源，
抓取渲染后文本 → 订单机器人抽取 → 复用 order_mail 捕获账本（source=web）。

抓取引擎双轨（镜像体积评估的结论：主镜像不装 Playwright/Chromium，~400MB）：
  1. 环境里装了 playwright（pip install playwright && playwright install chromium）
     则优先用真浏览器渲染——JS-SPA 门户也能抓；
  2. 缺省走 requests + BeautifulSoup——服务端渲染的门户直接可用，零新增依赖。
切换无需改代码，哪条路可用走哪条，返回值带 engine 字段供管理端显示。

Blueprint + 依赖注入（同 order_mail 模式）：本模块不 import app，
app.py 装配时 init(data_dir, load_json_fn, save_json_fn, require_admin_dec,
append_capture_fn) 注入设施。捕获账本属于 order_mail 域，本模块通过注入的
append_capture 写入，不直接碰它的数据文件。

存储：data/web_sources.json——[{id, name, url, enabled, last_fetch, last_status}]
"""
import hashlib
import os
import re
import secrets
from datetime import datetime

from flask import Blueprint, request, jsonify

bp = Blueprint("web_capture", __name__)

MAX_PAGE_CHARS = 12000       # 与订单机器人 run() 的截断上限一致
FETCH_TIMEOUT = 20           # 秒
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 依赖注入槽（app.py 装配时填充）
_data_dir = None
_load_json = None
_save_json = None
_require_admin = None
_append_capture = None


def init(data_dir, load_json_fn, save_json_fn, require_admin_dec, append_capture_fn):
    global _data_dir, _load_json, _save_json, _require_admin, _append_capture
    _data_dir = data_dir
    _load_json = load_json_fn
    _save_json = save_json_fn
    _require_admin = require_admin_dec
    _append_capture = append_capture_fn
    bp.add_url_rule("/api/admin/web-sources", "api_web_sources_list",
                    view_func=_require_admin(_api_sources_list), methods=["GET"])
    bp.add_url_rule("/api/admin/web-sources", "api_web_sources_save",
                    view_func=_require_admin(_api_sources_save), methods=["POST"])
    bp.add_url_rule("/api/admin/web-sources/<sid>", "api_web_sources_delete",
                    view_func=_require_admin(_api_source_delete), methods=["DELETE"])
    bp.add_url_rule("/api/admin/web-capture/fetch", "api_web_capture_fetch",
                    view_func=_require_admin(_api_fetch), methods=["POST"])


# ---------- 存储 ----------

def _sources_file():
    return os.path.join(_data_dir, "web_sources.json")


def read_sources():
    rows = _load_json(_sources_file(), []) or []
    return [r for r in rows if isinstance(r, dict)]


def _save_sources(rows):
    _save_json(_sources_file(), rows)


# ---------- 抓取 ----------

def _fetch_playwright(url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, timeout=FETCH_TIMEOUT * 1000, wait_until="domcontentloaded")
            text = page.inner_text("body")
            return text, "playwright"
        finally:
            browser.close()


def _fetch_requests(url):
    import requests
    from bs4 import BeautifulSoup
    r = requests.get(url, timeout=FETCH_TIMEOUT, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    # 服务端渲染页面：剥 script/style 后取正文文本
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()
    return text, "requests"


def fetch_page(url):
    """抓取页面文本：playwright 可用且渲染成功则用之，否则 requests+bs4 兜底。

    返回 (text, engine)；两条路都失败抛 RuntimeError（端点层 502）。
    fetcher 可注入（测试桩）。
    """
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("URL 必须以 http:// 或 https:// 开头")
    try:
        return _fetch_playwright(url)
    except ImportError:
        pass  # 未安装 playwright，走 requests
    except Exception:
        pass  # 装了但浏览器/渲染失败（如 chromium 未 install），同样兜底
    try:
        return _fetch_requests(url)
    except Exception as e:
        raise RuntimeError("页面抓取失败：%s" % str(e)[:160])


def capture_from_source(source, agent=None, fetcher=None):
    """抓一个来源 → 订单机器人抽取 → 写捕获账本。返回捕获记录 dict。"""
    url = source.get("url") or ""
    if agent is None:
        from agents.registry import get_agent
        agent = get_agent("order-catcher")
    if agent is None or not agent.available():
        raise RuntimeError("订单抽取引擎不可用（未配置 DASHSCOPE_API_KEY）")
    do_fetch = fetcher or fetch_page
    text, engine = do_fetch(url)
    text = (text or "")[:MAX_PAGE_CHARS]
    if not text.strip():
        raise RuntimeError("页面无可用文本（可能是纯 JS 渲染且未启用 Playwright）")

    cap = {
        "id": secrets.token_hex(8),
        "ts": datetime.now().isoformat(timespec="seconds"),
        "from": url[:200],
        "subject": "%s（网页抓单 · %s）" % (source.get("name") or "未命名来源", engine),
        "dedup": "web:" + hashlib.sha256((url + "|" + text[:500]).encode("utf-8", "replace")).hexdigest()[:32],
        "uid": None,
        "source": "web",
        "engine": engine,
    }
    # 内容没变不重复入账（同一来源反复抓取的幂等）
    existing = _load_json(os.path.join(_data_dir, "order_captures.json"), []) or []
    if any(c.get("dedup") == cap["dedup"] for c in existing):
        cap.update({"status": "skipped", "confidence": 0, "note": "页面内容未变化，跳过"})
    else:
        try:
            result = agent.run({"text": text})
            cap.update({"status": "new", "order": result.get("result"),
                        "confidence": result.get("confidence")})
        except Exception as e:
            cap.update({"status": "error", "confidence": 0,
                        "error": str(e)[:200], "body_excerpt": text[:400]})
    _append_capture(cap)
    return cap


# ---------- HTTP 视图（全部 admin） ----------

def _api_sources_list():
    return jsonify(read_sources())


def _api_sources_save():
    p = request.get_json(force=True, silent=True) or {}
    name = (p.get("name") or "").strip()
    url = (p.get("url") or "").strip()
    if not name or not url:
        return jsonify({"error": "name 和 url 不能为空"}), 400
    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"error": "URL 必须以 http:// 或 https:// 开头"}), 400
    rows = read_sources()
    sid = p.get("id")
    if sid:
        row = next((r for r in rows if r.get("id") == sid), None)
        if row is None:
            return jsonify({"error": "来源不存在"}), 404
        row.update({"name": name, "url": url, "enabled": bool(p.get("enabled", True))})
    else:
        row = {"id": secrets.token_hex(8), "name": name, "url": url,
               "enabled": bool(p.get("enabled", True)),
               "last_fetch": None, "last_status": None}
        rows.append(row)
    _save_sources(rows)
    return jsonify({"ok": True, "source": row})


def _api_source_delete(sid):
    rows = read_sources()
    row = next((r for r in rows if r.get("id") == sid), None)
    if row is None:
        return jsonify({"error": "来源不存在"}), 404
    rows.remove(row)
    _save_sources(rows)
    return jsonify({"ok": True, "deleted": sid})


def _api_fetch():
    p = request.get_json(force=True, silent=True) or {}
    sid = (p.get("id") or "").strip()
    row = next((r for r in read_sources() if r.get("id") == sid), None)
    if row is None:
        return jsonify({"error": "来源不存在"}), 404
    try:
        cap = capture_from_source(row)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": "抓取失败：%s" % str(e)[:160]}), 502
    # 更新来源状态
    rows = read_sources()
    for r in rows:
        if r.get("id") == sid:
            r["last_fetch"] = cap["ts"]
            r["last_status"] = cap["status"]
    _save_sources(rows)
    return jsonify({"ok": True, "capture": {k: cap.get(k) for k in
                    ("id", "status", "confidence", "engine", "note", "order")}})
