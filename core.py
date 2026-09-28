# -*- coding: utf-8 -*-
"""平台共享基础设施（R5 自 app.py 拆出）：路径/凭据/JSON 读写/鉴权/限流。

本模块无路由、不持有 Flask app——各域模块单向 import 这里的工具；
app.py 装配时把这里的函数注入各 Blueprint（同 prd_sessions 模式）。
"""
import os
import json
import time
import hashlib
import threading
from functools import wraps
from flask import request, jsonify

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


def limiter(limit, window, bucket="default", message="请求太频繁，请稍后再试"):
    """限流装饰器（R3 收敛样板）：限流是端点第一条语句时用它。

    bucket 支持 "{view_arg}" 占位（如 "agent_{agent_id}"）。
    注意：需要"先做其他校验再限流"的端点（如 agent run 先 404）保持
    函数体内手写 rate_limited，避免顺序语义变化。
    """
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            b = bucket.format(**request.view_args) if "{" in bucket else bucket
            if rate_limited(request.remote_addr, limit=limit, window=window, bucket=b):
                return jsonify({"error": message}), 429
            return fn(*args, **kwargs)
        return wrapper
    return deco
