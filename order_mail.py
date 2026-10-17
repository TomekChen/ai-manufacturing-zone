# -*- coding: utf-8 -*-
"""订单邮件自动捕获（A8）：IMAP 收件箱轮询 → 订单机器人抽取 → 捕获账本。

Blueprint + 依赖注入（同 prd_sessions 模式）：本模块不 import app，
app.py 装配时 init(data_dir, load_json, save_json, require_admin) 注入设施。

存储（data/ 挂载卷内，不入 git）：
  order_mail.json       邮箱配置（口令只写不回显，接口永不返回 password）
  order_captures.json   捕获账本 append-only，留最近 500 条
  order_mail_status.json 轮询状态（last_check/last_error），与管理端写配置解耦

去重：RFC822 Message-ID（缺失退回 from+subject+date 哈希）；UIDVALIDITY 变化
时重扫全箱由 Message-ID 去重兜底。取信用 BODY.PEEK，不改邮箱已读标记。
抽取复用注册表里的订单机器人 agent.run()，本模块不碰 LLM 细节。
"""
import hashlib
import imaplib
import io
import os
import re
import secrets
import threading
import time
import traceback
from datetime import datetime
from email import policy
from email.parser import BytesParser

from flask import Blueprint, request, jsonify

bp = Blueprint("order_mail", __name__)

# 轮询与容量
POLL_INTERVAL_SEC = 300      # 后台线程巡检周期（enabled 才真正连邮箱）
FETCH_BATCH = 50             # 单次最多处理多少封
MAX_BODY_CHARS = 12000       # 与订单机器人 run() 的截断上限一致
MAX_CAPTURES = 500
MAX_ATTACHMENTS = 5          # 单封邮件最多解析几个附件
MAX_ATTACH_BYTES = 5 * 1024 * 1024  # 单个附件大小上限（5MB）

# 依赖注入槽（app.py 装配时填充）
_data_dir = None
_load_json = None
_save_json = None
_require_admin = None


def init(data_dir, load_json_fn, save_json_fn, require_admin_dec):
    """装配注入并注册 admin 路由——require_admin 到此时才可用。"""
    global _data_dir, _load_json, _save_json, _require_admin
    _data_dir = data_dir
    _load_json = load_json_fn
    _save_json = save_json_fn
    _require_admin = require_admin_dec
    bp.add_url_rule("/api/admin/order-mail", "api_order_mail_get",
                    view_func=_require_admin(_api_config_get), methods=["GET"])
    bp.add_url_rule("/api/admin/order-mail", "api_order_mail_save",
                    view_func=_require_admin(_api_config_save), methods=["POST"])
    bp.add_url_rule("/api/admin/order-mail/test", "api_order_mail_test",
                    view_func=_require_admin(_api_config_test), methods=["POST"])
    bp.add_url_rule("/api/admin/order-mail/fetch", "api_order_mail_fetch",
                    view_func=_require_admin(_api_fetch_once), methods=["POST"])
    bp.add_url_rule("/api/admin/order-mail/captures", "api_order_mail_captures",
                    view_func=_require_admin(_api_captures_list), methods=["GET"])
    bp.add_url_rule("/api/admin/order-mail/captures/<cid>", "api_order_mail_capture_status",
                    view_func=_require_admin(_api_capture_status), methods=["POST"])


# ---------- 存储 ----------

def _config_file():
    return os.path.join(_data_dir, "order_mail.json")


def _captures_file():
    return os.path.join(_data_dir, "order_captures.json")


def _status_file():
    return os.path.join(_data_dir, "order_mail_status.json")


def read_config():
    cfg = _load_json(_config_file(), {}) or {}
    if not isinstance(cfg, dict):
        return {}
    return cfg


def _public_config(cfg):
    """口令只写不回显：只告诉前端有没有设过。"""
    return {"host": cfg.get("host", ""), "port": cfg.get("port", 993),
            "user": cfg.get("user", ""), "folder": cfg.get("folder", "INBOX"),
            "ssl": bool(cfg.get("ssl", True)), "enabled": bool(cfg.get("enabled")),
            "password_set": bool(cfg.get("password"))}


def _status():
    st = _load_json(_status_file(), {}) or {}
    return st if isinstance(st, dict) else {}


def _set_status(**kv):
    st = _status()
    st.update(kv)
    _save_json(_status_file(), st)


# ---------- IMAP ----------

def _connect(cfg):
    port = int(cfg.get("port") or 993)
    if cfg.get("ssl", True):
        conn = imaplib.IMAP4_SSL(cfg["host"], port)
    else:
        conn = imaplib.IMAP4(cfg["host"], port)
    conn.login(cfg["user"], cfg["password"])
    return conn


def _body_text(msg):
    """正文文本：优先 text/plain，只有 HTML 时剥标签兜底。"""
    import re as _re
    part = msg.get_body(preferencelist=("plain",))
    if part is None:
        part = msg.get_body(preferencelist=("html",))
        if part is None:
            return ""
        try:
            html = part.get_content()
        except Exception:
            return ""
        return _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", html)).strip()
    try:
        return str(part.get_content())
    except Exception:
        return ""


def _attachment_text(msg):
    """附件解析（A8 增强）：PDF 文字层 / xlsx / csv / txt → 文本；不支持格式记提示不报错。

    返回 (text, notes)：text 拼进抽取正文，notes 逐条说明为什么没解析出内容。
    """
    texts, notes = [], []
    try:
        atts = list(msg.iter_attachments())
    except Exception:
        atts = []
    for att in atts[:MAX_ATTACHMENTS]:
        name = att.get_filename() or "attachment"
        lower = name.lower()
        payload = att.get_payload(decode=True)
        if not payload:
            continue
        if len(payload) > MAX_ATTACH_BYTES:
            notes.append("%s（超过 5MB 未解析）" % name)
            continue
        try:
            if lower.endswith(".pdf"):
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(payload))
                t = "\n".join((p.extract_text() or "") for p in reader.pages[:20])
                if t.strip():
                    texts.append("【附件 %s】\n%s" % (name, t.strip()))
                else:
                    notes.append("%s（扫描件 PDF 无文字层，OCR 暂不支持）" % name)
            elif lower.endswith((".xlsx", ".xlsm")):
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
                try:
                    ws = wb.worksheets[0]
                    lines = ["\t".join("" if c is None else str(c) for c in row).strip()
                             for row in ws.iter_rows(values_only=True)]
                finally:
                    wb.close()
                t = "\n".join(line for line in lines if line)
                if t:
                    texts.append("【附件 %s】\n%s" % (name, t))
            elif lower.endswith((".csv", ".txt")):
                t = None
                for enc in ("utf-8-sig", "gbk", "utf-8", "latin-1"):
                    try:
                        t = payload.decode(enc)
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
                if t and t.strip():
                    texts.append("【附件 %s】\n%s" % (name, t.strip()))
            elif lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                notes.append("%s（图片附件，OCR 暂不支持）" % name)
            else:
                notes.append("%s（暂不支持该格式）" % name)
        except Exception as e:
            notes.append("%s（解析失败：%s）" % (name, str(e)[:60]))
    return "\n".join(texts), notes


def _dedup_key(msg, raw_headers):
    mid = (msg.get("Message-ID") or "").strip()
    if mid:
        return "mid:" + mid
    basis = "|".join(str(msg.get(h) or "") for h in ("From", "Subject", "Date"))
    return "hash:" + hashlib.sha256(basis.encode("utf-8", "replace")).hexdigest()[:32]


def test_connection(cfg):
    """连邮箱试登录并选中文件夹，返回 {ok, count, error}——保存前/排障用。"""
    try:
        conn = _connect(cfg)
    except Exception as e:
        return {"ok": False, "count": None, "error": "连接/登录失败：%s" % str(e)[:160]}
    try:
        typ, data = conn.select(cfg.get("folder") or "INBOX", readonly=True)
        if typ != "OK":
            return {"ok": False, "count": None, "error": "无法打开文件夹 %s" % (cfg.get("folder") or "INBOX")}
        return {"ok": True, "count": int(data[0]) if data and data[0] else 0, "error": None}
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def append_capture(cap):
    """捕获账本写入（公共入口）：order_mail 轮询与 web_capture 网页抓单共用，留最近 500 条。"""
    captures = _load_json(_captures_file(), []) or []
    captures.append(cap)
    _save_json(_captures_file(), captures[-MAX_CAPTURES:])
    return cap


def fetch_once(cfg=None, agent=None, limit=FETCH_BATCH):
    """拉一轮新邮件 → 订单机器人抽取 → 写捕获账本。

    返回 {checked, new, captured, errors}。cfg 缺省读已存配置；
    agent 可注入（测试桩），缺省从注册表取 order-catcher。
    """
    cfg = cfg if cfg is not None else read_config()
    if not cfg.get("host") or not cfg.get("user"):
        raise ValueError("邮箱未配置")
    if agent is None:
        from agents.registry import get_agent
        agent = get_agent("order-catcher")
    if agent is None or not agent.available():
        raise RuntimeError("订单抽取引擎不可用（未配置 DASHSCOPE_API_KEY）")

    captures = _load_json(_captures_file(), []) or []
    seen = {c.get("dedup") for c in captures if c.get("dedup")}
    conn = _connect(cfg)
    checked = new = errors = 0
    try:
        typ, data = conn.select(cfg.get("folder") or "INBOX")
        if typ != "OK":
            raise RuntimeError("无法打开文件夹 %s" % (cfg.get("folder") or "INBOX"))
        # UIDVALIDITY 变化说明邮箱侧 uid 空间重排，从 0 重扫（Message-ID 去重兜底）
        old_uv = str(cfg.get("uidvalidity") or "")
        try:
            _, uv = conn.response("UIDVALIDITY")
            uidvalidity = uv[0].decode() if uv and uv[0] else ""
        except Exception:
            uidvalidity = ""
        last_uid = int(cfg.get("last_uid") or 0) if uidvalidity == old_uv else 0

        typ, uids = conn.uid("search", None, "UID", "%d:*" % (max(last_uid, 0) + 1))
        if typ != "OK":
            raise RuntimeError("UID 检索失败")
        uid_list = sorted(int(u) for u in (uids[0].split() if uids and uids[0] else [])
                          if int(u) > last_uid)[-limit:]

        for uid in uid_list:
            checked += 1
            typ, fdata = conn.uid("fetch", str(uid), "(BODY.PEEK[])")
            if typ != "OK" or not fdata or not fdata[0]:
                errors += 1
                continue
            raw = fdata[0][1]
            try:
                msg = BytesParser(policy=policy.default).parsebytes(raw)
            except Exception:
                errors += 1
                continue
            dedup = _dedup_key(msg, raw)
            if dedup in seen:
                continue
            seen.add(dedup)
            body = _body_text(msg)[:MAX_BODY_CHARS]
            # 附件解析（A8 增强）：正文为空或附件带单据时，附件文本拼进抽取正文
            att_text, att_notes = _attachment_text(msg)
            if att_text:
                body = ((body + "\n" if body.strip() else "") + att_text)[:MAX_BODY_CHARS]
            cap = {
                "id": secrets.token_hex(8),
                "ts": datetime.now().isoformat(timespec="seconds"),
                "from": str(msg.get("From") or "")[:200],
                "subject": str(msg.get("Subject") or "")[:200],
                "dedup": dedup,
                "uid": uid,
            }
            if not body.strip():
                note = "正文无可抽取文本（可能只有附件/图片）"
                if att_notes:
                    note += "；" + "；".join(att_notes)
                cap.update({"status": "skipped", "confidence": 0, "note": note})
            else:
                try:
                    result = agent.run({"text": body})
                    cap.update({"status": "new",
                                "order": result.get("result"),
                                "confidence": result.get("confidence")})
                    new += 1
                except Exception as e:
                    # 抽取失败也不丢信：记 error 账，人工可补录
                    cap.update({"status": "error", "confidence": 0,
                                "error": str(e)[:200],
                                "body_excerpt": body[:400]})
                    errors += 1
            captures.append(cap)
        new_last = uid_list[-1] if uid_list else last_uid
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    cfg = dict(cfg)
    cfg["uidvalidity"] = uidvalidity
    cfg["last_uid"] = new_last
    _save_json(_config_file(), cfg)
    _save_json(_captures_file(), captures[-MAX_CAPTURES:])
    return {"checked": checked, "new": new, "errors": errors,
            "total": len(captures)}


# ---------- 轮询线程（同 portal.start_heartbeat 模式） ----------

def _loop():
    while True:
        time.sleep(POLL_INTERVAL_SEC)
        try:
            cfg = read_config()
            if not cfg.get("enabled"):
                continue
            r = fetch_once(cfg)
            _set_status(last_check=datetime.now().isoformat(timespec="seconds"),
                        last_result=r, last_error=None)
        except Exception as e:
            _set_status(last_check=datetime.now().isoformat(timespec="seconds"),
                        last_error=str(e)[:200],
                        last_trace=traceback.format_exc()[-800:])
            # 线程不能死：错误已记账，下一周期照常巡检


def start_poller():
    threading.Thread(target=_loop, daemon=True).start()


# ---------- HTTP 视图（全部 admin） ----------

def _api_config_get():
    cfg = read_config()
    out = _public_config(cfg)
    st = _status()
    out["last_check"] = st.get("last_check")
    out["last_error"] = st.get("last_error")
    out["last_result"] = st.get("last_result")
    out["poll_interval"] = POLL_INTERVAL_SEC
    return jsonify(out)


def _api_config_save():
    p = request.get_json(force=True, silent=True) or {}
    host = (p.get("host") or "").strip()
    user = (p.get("user") or "").strip()
    if not host or not user:
        return jsonify({"error": "host 和 user 不能为空"}), 400
    cfg = read_config()
    cfg.update({
        "host": host,
        "port": int(p.get("port") or 993),
        "user": user,
        "folder": (p.get("folder") or "INBOX").strip() or "INBOX",
        "ssl": bool(p.get("ssl", True)),
        "enabled": bool(p.get("enabled")),
    })
    # 口令只写不回显：前端传空 = 保持原值；传值 = 覆盖
    pwd = p.get("password") or ""
    if pwd:
        cfg["password"] = pwd
    _save_json(_config_file(), cfg)
    return jsonify({"ok": True, **_public_config(cfg)})


def _api_config_test():
    p = request.get_json(force=True, silent=True) or {}
    cfg = read_config()
    if p.get("password"):
        cfg = dict(cfg)
        cfg["password"] = p["password"]
    if p.get("host"):
        cfg = dict(cfg)
        cfg.update({k: p[k] for k in ("host", "port", "user", "folder", "ssl") if k in p})
    if not cfg.get("host") or not cfg.get("user"):
        return jsonify({"error": "请先填写 host 和 user"}), 400
    if not cfg.get("password"):
        return jsonify({"error": "请先填写密码"}), 400
    return jsonify(test_connection(cfg))


def _api_fetch_once():
    try:
        r = fetch_once()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": "拉取失败：%s" % str(e)[:160]}), 502
    _set_status(last_check=datetime.now().isoformat(timespec="seconds"),
                last_result=r, last_error=None)
    return jsonify({"ok": True, **r})


def _api_captures_list():
    rows = list(reversed(_load_json(_captures_file(), []) or []))[:200]
    return jsonify(rows)


def _api_capture_status(cid):
    p = request.get_json(force=True, silent=True) or {}
    status = (p.get("status") or "").strip()
    if status not in ("confirmed", "ignored", "new"):
        return jsonify({"error": "status 只能是 confirmed/ignored/new"}), 400
    captures = _load_json(_captures_file(), []) or []
    cap = next((c for c in captures if c.get("id") == cid), None)
    if cap is None:
        return jsonify({"error": "捕获记录不存在"}), 404
    cap["status"] = status
    _save_json(_captures_file(), captures)
    return jsonify({"ok": True, "id": cid, "status": status})
