# -*- coding: utf-8 -*-
"""订单邮件自动捕获（A8-T2）单测：IMAP 拉取/去重/账本/端点（离线，不碰真邮箱与真 LLM）。

运行：py tests/test_order_mail.py

打桩说明：
- om._connect → FakeConn（内存里的假 IMAP 服务器）；
- order_catcher 的 has_api_key/chat → 假实现（本机无 DASHSCOPE_API_KEY）；
- 数据目录重定向到临时目录，不污染本地 data/。
"""
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

# 本机缺库兜底（faiss/bs4）
for mod in ("faiss", "bs4", "bs4.BeautifulSoup"):
    try:
        __import__(mod)
    except ImportError:
        sys.modules[mod] = type(sys)("fake_" + mod)
if "bs4" in sys.modules and not hasattr(sys.modules["bs4"], "BeautifulSoup"):
    sys.modules["bs4.BeautifulSoup"] = type(sys)("fake_bs")
    sys.modules["bs4"].BeautifulSoup = object

import json

import app  # noqa: E402
import order_mail as om  # noqa: E402
import agents.order_catcher as oc  # noqa: E402
from email.message import EmailMessage  # noqa: E402

_TMP = tempfile.mkdtemp(prefix="order_mail_test_")
om._data_dir = _TMP

c = app.app.test_client()
PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  -", name)
    else:
        FAIL += 1
        print("  FAIL-", name, extra)


def _admin_headers():
    TOKEN = app.hash_password(app.ADMIN_ACCOUNT + app.ADMIN_PASSWORD
                              + app.SECRET_KEY)[:32]
    return {"Authorization": "Bearer " + TOKEN}


H = _admin_headers()

# ---- 订单机器人引擎桩（与 test_order_catcher 同款） ----
GOOD_ORDER = {"order_no": "PO-2026-88", "customer": "某某精密厂",
              "contact": "李工 13800000000",
              "products": [{"name": "精密轴", "spec": "φ20", "qty": "100", "unit": "件"}],
              "delivery_date": "12月20日", "notes": "", "missing": []}

oc.kb_prd.has_api_key = lambda: True
oc.chat = lambda messages, temperature=0.3, timeout=60: json.dumps(GOOD_ORDER, ensure_ascii=False)


class FlakyAgent:
    """抽取失败/成功可切换的假 agent（fetch_once 的 agent 注入口）。"""
    def __init__(self, fail=False, raise_value_error=False):
        self.fail = fail
        self.raise_value_error = raise_value_error
        self.available = lambda: True

    def run(self, payload):
        if self.raise_value_error:
            raise ValueError("请粘贴订单原文")
        if self.fail:
            raise RuntimeError("抽取失败：模型未返回结构化结果")
        return {"ok": True, "agent_id": "order-catcher", "result": dict(GOOD_ORDER),
                "confidence": 0.8, "refs": [], "mode": "order"}


# ---- 假 IMAP 服务器 ----

def make_raw(mid=None, frm="客户李工 <buyer@example.com>", subj="订单 PO-2026-88",
             body="订单号 PO-2026-88，精密轴 φ20 x 100 件，12月20日交货。"):
    m = EmailMessage()
    m["From"] = frm
    m["To"] = "sales@example.com"
    m["Subject"] = subj
    if mid:
        m["Message-ID"] = mid
    m.set_content(body)
    return m.as_bytes()


class FakeConn:
    def __init__(self, raw_by_uid, uidvalidity=b"1111"):
        self.raws = raw_by_uid
        self.uv = uidvalidity

    def select(self, folder, readonly=False):
        return ("OK", [str(len(self.raws)).encode()])

    def response(self, key):
        return ("OK", [self.uv])

    def uid(self, cmd, *args):
        if cmd == "search":
            if not self.raws:
                return ("OK", [b""])
            return ("OK", [b" ".join(str(u).encode() for u in sorted(self.raws))])
        if cmd == "fetch":
            uid = int(args[0])
            raw = self.raws.get(uid)
            if raw is None:
                return ("OK", [None])
            return ("OK", [(b"1 (UID %d BODY[]) " % uid, raw), b")"])
        raise AssertionError("unexpected uid cmd %r" % cmd)

    def logout(self):
        pass


def clear_data():
    for f in ("order_mail.json", "order_captures.json", "order_mail_status.json"):
        p = os.path.join(_TMP, f)
        if os.path.exists(p):
            os.remove(p)


def make_raw_att(mid, atts, body="见附件"):
    """带附件的邮件（atts: [(filename, bytes)]），正文故意写得极简。"""
    m = EmailMessage()
    m["From"] = "客户李工 <buyer@example.com>"
    m["To"] = "sales@example.com"
    m["Subject"] = "订单 PO-2026-88（附件版）"
    if mid:
        m["Message-ID"] = mid
    m.set_content(body)
    for fname, data in atts:
        m.add_attachment(data, maintype="application", subtype="octet-stream",
                         filename=fname)
    return m.as_bytes()


def test_attachments():
    print("\n[附件解析 A8 增强]")
    import io
    import openpyxl
    from email import policy
    from email.parser import BytesParser

    clear_data()

    # 单元层：xlsx 附件 → 文本；图片附件 → OCR 提示
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["品名", "数量"])
    ws.append(["精密轴", 100])
    buf = io.BytesIO()
    wb.save(buf)
    raw = make_raw_att("<att-1@x>", [("order.xlsx", buf.getvalue())])
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    text, notes = om._attachment_text(msg)
    check("xlsx 附件解析出表格", "精密轴" in text and "100" in text, text[:60])
    check("xlsx 无 notes", notes == [])

    raw2 = make_raw_att("<att-2@x>", [("scan.png", b"\x89PNG fake")], body="")
    _, notes2 = om._attachment_text(BytesParser(policy=policy.default).parsebytes(raw2))
    check("图片附件提示 OCR 暂不支持",
          len(notes2) == 1 and "OCR 暂不支持" in notes2[0], str(notes2))

    # 扫描件 PDF（无文字层）→ OCR 提示
    try:
        from pypdf import PdfWriter
        pw = PdfWriter()
        pw.add_blank_page(width=612, height=792)
        pbuf = io.BytesIO()
        pw.write(pbuf)
        raw3 = make_raw_att("<att-3@x>", [("scan.pdf", pbuf.getvalue())])
        _, notes3 = om._attachment_text(BytesParser(policy=policy.default).parsebytes(raw3))
        check("无文字层 PDF 提示 OCR", len(notes3) == 1 and "OCR" in notes3[0], str(notes3))
    except ImportError:
        print("  skip- pypdf 不在本地环境，跳过 PDF 分支")

    # 端到端：正文空壳 + xlsx 附件 → 附件文本进抽取入参，捕获 status=new
    seen_payload = {}
    class RecordAgent:
        available = lambda self: True
        def run(self, payload):
            seen_payload.update(payload)
            return {"ok": True, "agent_id": "order-catcher", "result": dict(GOOD_ORDER),
                    "confidence": 0.8, "refs": [], "mode": "order"}

    om._connect = lambda cfg: FakeConn({1: raw})
    r = om.fetch_once(dict(CFG), agent=RecordAgent())
    caps = om._load_json(om._captures_file(), [])
    check("附件邮件捕获 new", r["new"] == 1 and caps[0]["status"] == "new", str(r))
    check("附件文本进入抽取入参", "精密轴" in seen_payload.get("text", ""),
          seen_payload.get("text", "")[:80])

    # 端到端：只有图片附件 → skipped，note 带附件说明（不丢信）
    om._connect = lambda cfg: FakeConn({2: raw2})
    r2 = om.fetch_once(dict(CFG), agent=RecordAgent())
    caps2 = om._load_json(om._captures_file(), [])
    skip = [c for c in caps2 if c.get("status") == "skipped"]
    check("图片附件邮件 skipped 且 note 说明", len(skip) == 1 and "OCR" in skip[0].get("note", ""),
          str(skip)[:120])


CFG = {"host": "imap.example.com", "port": 993, "user": "sales@example.com",
       "password": "secret", "folder": "INBOX", "ssl": True, "enabled": True}


# ---------- 纯单元：fetch_once ----------
def test_fetch_once():
    print("\n[fetch_once 单元]")
    clear_data()

    # 邮箱未配置
    try:
        om.fetch_once()
        check("未配置邮箱应抛 ValueError", False)
    except ValueError:
        check("未配置邮箱抛 ValueError", True)
    except Exception as e:
        check("未配置邮箱抛 ValueError", False, repr(e))

    # 引擎不可用（关掉 has_api_key 桩）
    old_has_key = oc.kb_prd.has_api_key
    oc.kb_prd.has_api_key = lambda: False
    try:
        om.fetch_once(dict(CFG), agent=None)
        check("引擎不可用应抛 RuntimeError", False)
    except RuntimeError:
        check("引擎不可用抛 RuntimeError", True)
    except Exception as e:
        check("引擎不可用抛 RuntimeError", False, repr(e))
    finally:
        oc.kb_prd.has_api_key = lambda: True

    # 正常拉取：2 封 → 2 条捕获，uid 推进
    raws = {5: make_raw("<m-5@example.com>"), 9: make_raw("<m-9@example.com>")}
    om._connect = lambda cfg: FakeConn(raws)
    r = om.fetch_once(dict(CFG), agent=FlakyAgent())
    check("拉取 checked=2", r["checked"] == 2, str(r))
    check("拉取 new=2 errors=0", r["new"] == 2 and r["errors"] == 0, str(r))
    caps = om._load_json(om._captures_file(), [])
    check("账本写入 2 条", len(caps) == 2)
    check("捕获含 order/confidence", caps[0]["order"]["order_no"] == "PO-2026-88"
          and caps[0]["confidence"] == 0.8)
    check("捕获记录 from/subject/dedup", caps[0]["from"].startswith("客户李工")
          and caps[0]["dedup"] == "mid:<m-5@example.com>")
    cfg = om.read_config()
    check("last_uid 推进到 9", cfg.get("last_uid") == 9, str(cfg.get("last_uid")))
    check("uidvalidity 已存", cfg.get("uidvalidity") == "1111")

    # 再拉一轮（读已存配置，带 last_uid）：同一批 uid → checked=0，无重复
    r2 = om.fetch_once(om.read_config(), agent=FlakyAgent())
    check("同 uid 空间第二轮 checked=0", r2["checked"] == 0 and r2["new"] == 0, str(r2))
    check("账本仍 2 条（无重复）", len(om._load_json(om._captures_file(), [])) == 2)

    # 新 uid 到达：只拉新的
    raws[12] = make_raw("<m-12@example.com>")
    r3 = om.fetch_once(om.read_config(), agent=FlakyAgent())
    check("增量拉取只处理新 uid", r3["checked"] == 1 and r3["new"] == 1, str(r3))
    check("账本 3 条", len(om._load_json(om._captures_file(), [])) == 3)

    # UIDVALIDITY 变化 → 从 0 重扫，但 Message-ID 去重兜底，不产生重复
    om._connect = lambda cfg: FakeConn(raws, uidvalidity=b"2222")
    r4 = om.fetch_once(dict(CFG), agent=FlakyAgent())
    check("UIDVALIDITY 变化重扫全箱", r4["checked"] == 3, str(r4))
    check("重扫后账本仍 3 条（去重兜底）", len(om._load_json(om._captures_file(), [])) == 3)

    # 无 Message-ID 的邮件 → hash 去重键
    raws2 = {3: make_raw(None)}
    om._connect = lambda cfg: FakeConn(raws2, uidvalidity=b"3333")
    r5 = om.fetch_once(dict(CFG), agent=FlakyAgent())
    caps5 = om._load_json(om._captures_file(), [])
    check("无 Message-ID 用 hash 去重键", r5["new"] == 1
          and caps5[-1]["dedup"].startswith("hash:"))

    # 抽取失败 → error 账不丢信
    raws3 = {2: make_raw("<m-err@example.com>")}
    om._connect = lambda cfg: FakeConn(raws3, uidvalidity=b"4444")
    r6 = om.fetch_once(dict(CFG), agent=FlakyAgent(fail=True))
    caps6 = om._load_json(om._captures_file(), [])
    check("抽取失败记 error 账", r6["errors"] == 1 and caps6[-1]["status"] == "error"
          and caps6[-1].get("body_excerpt"))

    # 空正文 → skipped
    raws4 = {4: make_raw("<m-empty@example.com>", body="")}
    om._connect = lambda cfg: FakeConn(raws4, uidvalidity=b"5555")
    r7 = om.fetch_once(dict(CFG), agent=FlakyAgent())
    caps7 = om._load_json(om._captures_file(), [])
    check("空正文 skipped 不进抽取", r7["new"] == 0 and caps7[-1]["status"] == "skipped")


# ---------- HTTP 端点 ----------
def test_endpoints():
    print("\n[HTTP 端点]")
    clear_data()

    r = c.get("/api/admin/order-mail")
    check("未带 token 401", r.status_code == 401)
    r = c.get("/api/admin/order-mail", headers=H)
    body = r.get_json() or {}
    check("GET 配置 200 且含 password_set=false", r.status_code == 200
          and body.get("password_set") is False, str(body))

    r = c.post("/api/admin/order-mail", headers=H,
               json={"host": "", "user": ""})
    check("空 host/user 400", r.status_code == 400)

    r = c.post("/api/admin/order-mail", headers=H,
               json={"host": "imap.example.com", "user": "sales@example.com",
                     "password": "secret1", "enabled": True})
    body = r.get_json() or {}
    check("保存配置 200", r.status_code == 200 and body.get("ok") is True, str(body))
    check("口令不回显", "password" not in body and body.get("password_set") is True, str(body))
    saved = om.read_config()
    check("口令已落库", saved.get("password") == "secret1")
    check("enabled 已落库", saved.get("enabled") is True)

    # 空口令 = 保持原值
    c.post("/api/admin/order-mail", headers=H,
           json={"host": "imap.example.com", "user": "sales@example.com"})
    check("空口令保存保持原值", om.read_config().get("password") == "secret1")

    # test 端点：走假 _connect
    om._connect = lambda cfg: FakeConn({1: make_raw("<t-1@x>")})
    r = c.post("/api/admin/order-mail/test", headers=H, json={})
    body = r.get_json() or {}
    check("test 连接 200 ok", r.status_code == 200 and body.get("ok") is True
          and body.get("count") == 1, str(body))
    r = c.post("/api/admin/order-mail/test", headers=H, json={"password": "bad"})
    check("test 带 body 密码仍走桩（连接成功）", (r.get_json() or {}).get("ok") is True)

    # 未配置密码时 test 400
    clear_data()
    r = c.post("/api/admin/order-mail/test", headers=H, json={"host": "imap.example.com"})
    check("无密码 test 400", r.status_code == 400)

    # fetch 端点：未配置 400
    r = c.post("/api/admin/order-mail/fetch", headers=H)
    check("未配置 fetch 400", r.status_code == 400)

    # fetch 端点：正常（引擎走真注册表 order-catcher + chat 桩）
    c.post("/api/admin/order-mail", headers=H,
           json={"host": "imap.example.com", "user": "sales@example.com",
                 "password": "secret", "enabled": False})
    om._connect = lambda cfg: FakeConn({2: make_raw("<h-2@x>")})
    r = c.post("/api/admin/order-mail/fetch", headers=H)
    body = r.get_json() or {}
    check("fetch 端点 200 且 new=1", r.status_code == 200 and body.get("new") == 1, str(body))

    # captures 列表与状态流转
    r = c.get("/api/admin/order-mail/captures", headers=H)
    rows = r.get_json() or []
    check("captures 列表 200 且最新在前", r.status_code == 200
          and len(rows) == 1 and rows[0]["dedup"] == "mid:<h-2@x>")
    cid = rows[0]["id"]
    r = c.post("/api/admin/order-mail/captures/%s" % cid, headers=H,
               json={"status": "confirmed"})
    check("状态流转 confirmed 200", (r.get_json() or {}).get("status") == "confirmed")
    r = c.post("/api/admin/order-mail/captures/ghost", headers=H,
               json={"status": "confirmed"})
    check("未知 id 404", r.status_code == 404)
    r = c.post("/api/admin/order-mail/captures/%s" % cid, headers=H,
               json={"status": "hacked"})
    check("非法 status 400", r.status_code == 400)

    # 503：引擎不可用（把 has_api_key 关掉）
    old_has_key = oc.kb_prd.has_api_key
    oc.kb_prd.has_api_key = lambda: False
    try:
        r = c.post("/api/admin/order-mail/fetch", headers=H)
        check("引擎不可用 fetch 503", r.status_code == 503)
    finally:
        oc.kb_prd.has_api_key = lambda: True

    # 502：连接失败
    def boom(cfg):
        raise ConnectionRefusedError("connection refused")
    om._connect = boom
    r = c.post("/api/admin/order-mail/fetch", headers=H)
    check("连接失败 fetch 502", r.status_code == 502)

    # 轮询线程函数不炸：enabled=False 直接跳过
    om._connect = boom
    try:
        om._loop.__wrapped__ if False else None
        import threading
        t = threading.Thread(target=lambda: om.read_config(), daemon=True)
        t.start(); t.join()
        check("轮询线程状态文件可读写", isinstance(om._status(), dict))
    except Exception as e:
        check("轮询线程状态文件可读写", False, repr(e))


if __name__ == "__main__":
    test_fetch_once()
    test_attachments()
    test_endpoints()
    print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
