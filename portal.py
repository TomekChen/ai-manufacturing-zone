# -*- coding: utf-8 -*-
"""门户展示域（R5 自 app.py 拆出）：外观配置、项目卡 CRUD、探活心跳。

一个变更理由：首页对外呈现什么、活不活着。项目卡后台异步心跳、
保存后异步复测（不阻塞响应）的行为保持与拆分前一致。
"""
import time
import secrets
import threading
from datetime import datetime
from urllib.parse import urlparse
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
from flask import Blueprint, request, jsonify

from core import (CONFIG_FILE, PROJECTS_FILE, DEFAULT_CONFIG,
                  load_json, save_json, get_config, get_projects, require_admin)

bp = Blueprint("portal", __name__)


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


def start_heartbeat():
    """启动后台心跳线程（app.py 装配时调用一次）。"""
    threading.Thread(target=heartbeat_loop, daemon=True).start()


def probe_url(url, timeout=15):
    """详细探测：返回 {alive, status, error}，供后台"测试连接"按钮实时反馈。"""
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


@bp.route("/api/config", methods=["GET"])
def api_config():
    return jsonify(get_config())


@bp.route("/api/admin/config", methods=["POST"])
@require_admin
def api_admin_config():
    payload = request.get_json(force=True) or {}
    cfg = get_config()
    cfg.update({k: v for k, v in payload.items() if k in ("title", "accent", "canvas")})
    save_json(CONFIG_FILE, cfg)
    return jsonify(cfg)


@bp.route("/api/admin/config/reset", methods=["POST"])
@require_admin
def api_admin_config_reset():
    """恢复默认外观配置（把标题/主色/背景重置回内置默认值），供管理员改坏外观时一键救急。"""
    cfg = dict(DEFAULT_CONFIG)
    save_json(CONFIG_FILE, cfg)
    return jsonify(cfg)


@bp.route("/api/projects", methods=["GET"])
def api_projects():
    return jsonify(get_projects())


@bp.route("/api/admin/projects", methods=["GET", "POST"])
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


@bp.route("/api/admin/projects/<pid>", methods=["DELETE"])
@require_admin
def api_admin_delete_project(pid):
    projects = [p for p in get_projects() if p["id"] != pid]
    save_json(PROJECTS_FILE, projects)
    return jsonify(projects)


@bp.route("/api/admin/heartbeat", methods=["POST"])
@require_admin
def api_admin_heartbeat():
    heartbeat_all()
    return jsonify(get_projects())


@bp.route("/api/admin/probe", methods=["POST"])
@require_admin
def api_admin_probe():
    payload = request.get_json(force=True) or {}
    url = (payload.get("url") or "").strip()
    return jsonify(probe_url(url))
