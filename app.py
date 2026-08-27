import os
import json
import time
import threading
import secrets
import hashlib
from datetime import datetime
from urllib.parse import urlparse
from flask import Flask, send_from_directory, request, jsonify
from werkzeug.utils import secure_filename
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DIST_DIR = os.path.join(BASE_DIR, "dist")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")

ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB

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
    return load_json(CONFIG_FILE, {"title": "智能制造专区", "accent": "#3b82f6", "canvas": "#0b0b0f"})


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
def api_admin_config():
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(force=True) or {}
    cfg = get_config()
    cfg.update({k: v for k, v in payload.items() if k in ("title", "accent", "canvas")})
    save_json(CONFIG_FILE, cfg)
    return jsonify(cfg)


@app.route("/api/projects", methods=["GET"])
def api_projects():
    return jsonify(get_projects())


@app.route("/api/admin/projects", methods=["GET", "POST"])
def api_admin_projects():
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
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
def api_admin_delete_project(pid):
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
    projects = [p for p in get_projects() if p["id"] != pid]
    save_json(PROJECTS_FILE, projects)
    return jsonify(projects)


@app.route("/api/admin/heartbeat", methods=["POST"])
def api_admin_heartbeat():
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
    heartbeat_all()
    return jsonify(get_projects())


@app.route("/api/admin/upload", methods=["POST"])
def api_admin_upload():
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
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
