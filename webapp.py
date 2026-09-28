# -*- coding: utf-8 -*-
"""站点服务域（R5 自 app.py 拆出）：管理员登录、图片上传、预约演示、SPA 静态服务。

一个变更理由：站点自身的运转设施（谁能进后台、资源怎么存取、线索怎么收）。
命名不用 site.py——那是 Python 标准库模块名，本地同名文件会遮蔽它。
"""
import os
import secrets
from datetime import datetime
from flask import Blueprint, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

import notify
from core import (ADMIN_ACCOUNT, ADMIN_PASSWORD, SECRET_KEY, UPLOAD_DIR, DIST_DIR,
                  ALLOWED_IMAGE_EXTS, load_json, save_json, hash_password,
                  require_admin, limiter)

bp = Blueprint("webapp", __name__)

DEMO_BOOKINGS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "demo_bookings.json")


@bp.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    payload = request.get_json(force=True) or {}
    account = payload.get("account", "")
    password = payload.get("password", "")
    if account == ADMIN_ACCOUNT and password == ADMIN_PASSWORD:
        token = hash_password(account + password + SECRET_KEY)[:32]
        return jsonify({"token": token})
    return jsonify({"error": "invalid account or password"}), 401


@bp.route("/api/admin/upload", methods=["POST"])
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


@bp.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@bp.route("/api/demo/booking", methods=["POST"])
@limiter(3, 3600, bucket="demo_booking", message="提交太频繁，请稍后再试")
def api_demo_booking():
    """公开预约：称呼+联系方式必填；落盘后尝试邮件通知（发送失败不影响受理）。"""
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


@bp.route("/api/admin/demo/bookings", methods=["GET"])
@require_admin
def api_admin_demo_bookings():
    """后台预约列表（新→旧），供管理端「预约」页签查看。"""
    return jsonify(list(reversed(load_json(DEMO_BOOKINGS_FILE, []))))


# 静态文件服务（处理 SPA 路由）
@bp.route("/", defaults={"path": ""})
@bp.route("/<path:path>")
def serve(path):
    if path and os.path.exists(os.path.join(DIST_DIR, path)):
        return send_from_directory(DIST_DIR, path)
    return send_from_directory(DIST_DIR, "index.html")
