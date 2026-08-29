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

import kb

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
def api_admin_probe():
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(force=True) or {}
    url = (payload.get("url") or "").strip()
    return jsonify(probe_url(url))


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


# ===================== 知识库（RAG）=====================

# 全局知识库存储（数据文件在 data/ 挂载卷内，容器重建不丢）
KB = kb.KnowledgeStore(DATA_DIR)

# 公开问答的简单内存限流：每 IP 每分钟最多 10 次
_ask_limits = {}
_ask_limit_lock = threading.Lock()


def rate_limited(ip, limit=10, window=60):
    now = time.time()
    with _ask_limit_lock:
        lst = [t for t in _ask_limits.get(ip, []) if now - t < window]
        if len(lst) >= limit:
            _ask_limits[ip] = lst
            return True
        lst.append(now)
        _ask_limits[ip] = lst
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


@app.route("/api/kb/ask", methods=["POST"])
def api_kb_ask():
    """知识库问答：FAISS 检索 + 百炼 LLM 生成。"""
    if rate_limited(request.remote_addr, limit=10, window=60):
        return jsonify({"error": "提问太频繁，请稍后再试"}), 429
    payload = request.get_json(force=True, silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "请输入问题"}), 400
    if len(question) > 500:
        return jsonify({"error": "问题太长（最多 500 字）"}), 400
    try:
        result = KB.ask(question)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "问答失败：%s" % str(e)[:120]}), 500
    return jsonify(result)


@app.route("/api/admin/kb/docs", methods=["GET"])
def api_admin_kb_docs():
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"docs": KB.list_docs(), "stats": KB.stats()})


@app.route("/api/admin/kb/docs/<doc_id>", methods=["GET"])
def api_admin_kb_doc_detail(doc_id):
    """管理员预览单条文档及分块内容。"""
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        detail = KB.get_doc_detail(doc_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "加载失败：%s" % str(e)[:120]}), 500
    return jsonify(detail)


@app.route("/api/admin/kb/docs/<doc_id>/approve", methods=["POST"])
def api_admin_kb_approve(doc_id):
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        doc = KB.approve(doc_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "入库失败：%s" % str(e)[:120]}), 502
    return jsonify({"doc": doc, "stats": KB.stats()})


@app.route("/api/admin/kb/docs/<doc_id>/reject", methods=["POST"])
def api_admin_kb_reject(doc_id):
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        doc = KB.reject(doc_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"doc": doc, "stats": KB.stats()})


@app.route("/api/admin/kb/docs/<doc_id>", methods=["DELETE"])
def api_admin_kb_delete(doc_id):
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        KB.delete(doc_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"docs": KB.list_docs(), "stats": KB.stats()})


def _crawl_to_kb(url, doc_type="url"):
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
                      doc_type=doc_type, status="approved")
    return doc


@app.route("/api/admin/kb/crawl", methods=["POST"])
def api_admin_kb_crawl():
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(force=True, silent=True) or {}
    try:
        doc = _crawl_to_kb(payload.get("url"))
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "采集失败：%s" % str(e)[:160]}), 502
    return jsonify({"doc": doc, "message": "采集成功，已入库"})


@app.route("/api/admin/links", methods=["GET", "POST"])
def api_admin_links():
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return jsonify(KB.list_links())
    payload = request.get_json(force=True, silent=True) or {}
    try:
        links = KB.save_link(payload)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(links)


@app.route("/api/admin/links/<link_id>", methods=["DELETE"])
def api_admin_links_delete(link_id):
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(KB.delete_link(link_id))


@app.route("/api/admin/links/<link_id>/crawl", methods=["POST"])
def api_admin_links_crawl(link_id):
    """从友情链接一键采集入库。"""
    if not verify_token(request.headers.get("Authorization", "")):
        return jsonify({"error": "Unauthorized"}), 401
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
