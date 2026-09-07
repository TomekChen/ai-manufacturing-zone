# -*- coding: utf-8 -*-
"""预约演示端点单测：入参校验 / 落盘 / 邮件打桩 / 限流 / 管理员列表（离线，不发真邮件）。

运行：py tests/test_booking.py
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

import app  # noqa: E402

# 预约文件重定向到临时目录，不污染本地 data/
_TMP = tempfile.mkdtemp(prefix="booking_test_")
app.DEMO_BOOKINGS_FILE = os.path.join(_TMP, "demo_bookings.json")

# 邮件打桩：永不真发。SEND_OK 控制成功/失败分支。
SENT = []
SEND_OK = [True]


def fake_send(subject, body):
    SENT.append({"subject": subject, "body": body})
    return (SEND_OK[0], "stubbed")


app.notify.send_email = fake_send

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


def clear_booking_bucket():
    app._ask_limits.setdefault("demo_booking", {}).pop("127.0.0.1", None)


def read_file():
    return app.load_json(app.DEMO_BOOKINGS_FILE, [])


TOKEN = app.hash_password(app.ADMIN_ACCOUNT + app.ADMIN_PASSWORD + app.SECRET_KEY)[:32]


def test_booking():
    print("\n[booking 公开提交]")
    clear_booking_bucket()
    SENT.clear()

    r = c.post("/api/demo/booking", json={
        "name": "  王经理  ", "contact": " 13800000000 ", "project": " 设备医生 ",
        "note": " 想看预测性维护全流程 "})
    body = r.get_json()
    check("合法预约 200", r.status_code == 200, str(body))
    check("响应 ok/notified/message 齐全",
          body.get("ok") is True and body.get("notified") is True and bool(body.get("message")))
    check("邮件打桩收到 1 封", len(SENT) == 1)
    check("邮件主题含称呼与项目", "预约演示" in SENT[0]["subject"] and "王经理" in SENT[0]["subject"]
          and "设备医生" in SENT[0]["subject"])
    check("邮件正文含联系方式", "13800000000" in SENT[0]["body"])

    recs = read_file()
    check("落盘 1 条", len(recs) == 1, str(len(recs)))
    rec = recs[0]
    check("字段清洗：去空格", rec["name"] == "王经理" and rec["contact"] == "13800000000"
          and rec["project"] == "设备医生" and rec["note"] == "想看预测性维护全流程")
    check("字段齐全：id/ip/ts/notified", bool(rec["id"]) and rec["ip"] == "127.0.0.1"
          and "T" in rec["ts"] and rec["notified"] is True)

    print("\n[booking 校验]")
    clear_booking_bucket()
    n0 = len(read_file())
    r = c.post("/api/demo/booking", json={"contact": "13800000000"})
    check("缺称呼 400", r.status_code == 400 and "称呼" in (r.get_json() or {}).get("error", ""))
    r = c.post("/api/demo/booking", json={"name": "王经理", "contact": "123"})
    check("联系方式过短 400", r.status_code == 400 and "联系" in (r.get_json() or {}).get("error", ""))
    check("校验失败不落盘", len(read_file()) == n0)

    print("\n[booking 截断与 notified=False]")
    clear_booking_bucket()
    r = c.post("/api/demo/booking", json={
        "name": "超" * 50, "contact": "联" * 90, "project": "项" * 70, "note": "备" * 600})
    check("超长入参仍 200", r.status_code == 200)
    rec = read_file()[-1]
    check("name 截断 <=40", len(rec["name"]) <= 40, str(len(rec["name"])))
    check("contact 截断 <=80", len(rec["contact"]) <= 80)
    check("project 截断 <=60", len(rec["project"]) <= 60)
    check("note 截断 <=500", len(rec["note"]) <= 500)

    SEND_OK[0] = False
    clear_booking_bucket()
    r = c.post("/api/demo/booking", json={"name": "李工", "contact": "lisi@example.com"})
    body = r.get_json()
    check("邮件失败仍受理 200", r.status_code == 200 and body.get("ok") is True)
    check("notified=False 透传给前端", body.get("notified") is False)
    check("失败记录 notified=False", read_file()[-1]["notified"] is False)
    SEND_OK[0] = True

    print("\n[booking 限流]")
    clear_booking_bucket()
    codes = []
    for i in range(4):
        rr = c.post("/api/demo/booking", json={"name": "用户%d" % i, "contact": "1380000000%d" % i})
        codes.append(rr.status_code)
    check("第 4 次提交 429（每 IP 每小时 3 次）", codes == [200, 200, 200, 429], str(codes))
    check("限流记在 demo_booking 桶",
          len(app._ask_limits.get("demo_booking", {}).get("127.0.0.1", [])) == 3)

    print("\n[booking 管理员列表]")
    r = c.get("/api/admin/demo/bookings")
    check("未登录 401", r.status_code == 401)
    r = c.get("/api/admin/demo/bookings", headers={"Authorization": "Bearer wrong-token"})
    check("错误 token 401", r.status_code == 401)
    r = c.get("/api/admin/demo/bookings", headers={"Authorization": "Bearer " + TOKEN})
    data = r.get_json()
    check("正确 token 200", r.status_code == 200)
    check("列表非空", isinstance(data, list) and len(data) >= 6, str(len(data) if isinstance(data, list) else data))
    if isinstance(data, list) and len(data) >= 6:
        check("新的在前（倒序）", data[0]["ts"] >= data[-1]["ts"])
        check("最新一条是限流前最后一次成功提交", data[0]["name"] == "用户2", str(data[0]["name"]))
        check("列表不含内部字段缺失", all(("id" in b and "notified" in b) for b in data))


if __name__ == "__main__":
    test_booking()
    print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
