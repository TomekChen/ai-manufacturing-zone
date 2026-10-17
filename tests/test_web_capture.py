# -*- coding: utf-8 -*-
"""网页抓单（A8 增强③）单测：来源管理/抓取/去重/账本（离线，不碰真网页与真 LLM）。

运行：py tests/test_web_capture.py

打桩说明：
- fetcher 注入假抓取函数（不真发 HTTP）；
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
import web_capture as wc  # noqa: E402
import agents.order_catcher as oc  # noqa: E402

_TMP = tempfile.mkdtemp(prefix="web_capture_test_")
wc._data_dir = _TMP
wc._load_json = app.load_json
wc._save_json = app.save_json
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

# ---- 订单机器人引擎桩 ----
GOOD_ORDER = {"order_no": "PO-WEB-1", "customer": "网页客户",
              "contact": "王工", "products": [], "delivery_date": "",
              "notes": "", "missing": []}

oc.kb_prd.has_api_key = lambda: True
oc.chat = lambda messages, temperature=0.3, timeout=60: json.dumps(GOOD_ORDER, ensure_ascii=False)


class StubAgent:
    available = lambda self: True
    def run(self, payload):
        return {"ok": True, "agent_id": "order-catcher", "result": dict(GOOD_ORDER),
                "confidence": 0.7, "refs": [], "mode": "order"}


PAGE_TEXT = "门户订单 PO-WEB-1 精密轴承 200 套"

captures_file = os.path.join(_TMP, "order_captures.json")


def run_all():
    print("== 1. 来源管理 ==")
    r = c.get("/api/admin/web-sources")
    check("未带 token 列表 401", r.status_code == 401)
    r = c.post("/api/admin/web-sources", json={"name": "客户A门户"}, headers=H)
    check("缺 url 保存 400", r.status_code == 400)
    r = c.post("/api/admin/web-sources", json={"name": "客户A门户", "url": "ftp://x"}, headers=H)
    check("非 http url 保存 400", r.status_code == 400)
    r = c.post("/api/admin/web-sources", json={"name": "客户A门户", "url": "http://portal.example.com"}, headers=H)
    check("保存来源 200", r.status_code == 200, r.get_data(as_text=True))
    sid = r.get_json()["source"]["id"]
    check("来源含 last_fetch=None", r.get_json()["source"]["last_fetch"] is None)
    r = c.post("/api/admin/web-sources", json={"id": "nope", "name": "x", "url": "http://x.com"}, headers=H)
    check("更新不存在的 id 404", r.status_code == 404)
    r = c.post("/api/admin/web-sources", json={"id": sid, "name": "客户A门户改", "url": "http://portal.example.com/v2"}, headers=H)
    check("更新来源 200 且名字变了", r.status_code == 200 and r.get_json()["source"]["name"] == "客户A门户改")
    r = c.get("/api/admin/web-sources", headers=H)
    check("列表 200 且有 1 条", r.status_code == 200 and len(r.get_json()) == 1)

    print("== 2. fetch_page 校验 ==")
    try:
        wc.fetch_page("ftp://bad")
        check("非 http url 抛 ValueError", False)
    except ValueError:
        check("非 http url 抛 ValueError", True)
    except Exception as e:
        check("非 http url 抛 ValueError", False, repr(e))

    print("== 3. 抓取（注入假 fetcher） ==")
    r = c.post("/api/admin/web-capture/fetch", json={"id": "nope"}, headers=H)
    check("抓取未知来源 404", r.status_code == 404)

    calls = []
    def fake_fetch(url):
        calls.append(url)
        return PAGE_TEXT, "stub"
    r = c.post("/api/admin/web-capture/fetch", json={"id": sid},
               content_type="application/json", headers=H)
    # 该次走真 fetch_page 会失败（无网络/403）——为确定性，先单独测 capture_from_source
    check("端点不炸（真抓取失败给 50x 而非 500）", r.status_code in (400, 502, 503), r.status_code)

    cap = wc.capture_from_source({"id": sid, "name": "客户A门户", "url": "http://portal.example.com"},
                                 agent=StubAgent(), fetcher=fake_fetch)
    check("捕获 status=new", cap["status"] == "new", cap.get("status"))
    check("source=web", cap["source"] == "web")
    check("engine 来自 fetcher", cap["engine"] == "stub")
    check("subject 带来源名", "客户A门户" in cap["subject"])
    check("订单结果入库", cap["order"]["order_no"] == "PO-WEB-1")
    check("fake_fetch 被调用且传 url", calls == ["http://portal.example.com"])
    led = json.load(open(captures_file, encoding="utf-8"))
    check("账本落了 1 条", len(led) == 1 and led[0]["source"] == "web")

    print("== 4. 内容未变去重 ==")
    cap2 = wc.capture_from_source({"id": sid, "name": "客户A门户", "url": "http://portal.example.com"},
                                  agent=StubAgent(), fetcher=fake_fetch)
    check("同内容捕获 skipped", cap2["status"] == "skipped", cap2.get("status"))
    check("skipped 附说明", "内容未变化" in (cap2.get("note") or ""))
    led = json.load(open(captures_file, encoding="utf-8"))
    check("账本仍是 2 条（skipped 也记账）", len(led) == 2)

    print("== 5. 内容变化再次入账 ==")
    PAGE_TEXT2 = PAGE_TEXT + "\n加急：交期提前到 11 月"
    def fake_fetch2(url):
        return PAGE_TEXT2, "stub"
    cap3 = wc.capture_from_source({"id": sid, "name": "客户A门户", "url": "http://portal.example.com"},
                                  agent=StubAgent(), fetcher=fake_fetch2)
    check("新内容捕获 new", cap3["status"] == "new")

    print("== 6. 异常路径 ==")
    def bad_fetch(url):
        raise RuntimeError("页面抓取失败：超时")
    try:
        wc.capture_from_source({"id": sid, "name": "x", "url": "http://x.com"},
                               agent=StubAgent(), fetcher=bad_fetch)
        check("抓取失败抛 RuntimeError", False)
    except RuntimeError:
        check("抓取失败抛 RuntimeError", True)
    def empty_fetch(url):
        return "   \n  ", "stub"
    try:
        wc.capture_from_source({"id": sid, "name": "x", "url": "http://x.com"},
                               agent=StubAgent(), fetcher=empty_fetch)
        check("空白页抛 RuntimeError", False)
    except RuntimeError as e:
        check("空白页抛 RuntimeError", "无可用文本" in str(e))

    class DeadAgent:
        available = lambda self: False
        def run(self, payload): raise AssertionError("不应被调")
    try:
        wc.capture_from_source({"id": sid, "name": "x", "url": "http://x.com"},
                               agent=DeadAgent(), fetcher=fake_fetch)
        check("引擎不可用抛 RuntimeError", False)
    except RuntimeError as e:
        check("引擎不可用抛 RuntimeError", "不可用" in str(e))

    class FailAgent:
        available = lambda self: True
        def run(self, payload): raise RuntimeError("模型抽风")
    cap4 = wc.capture_from_source({"id": sid, "name": "x", "url": "http://x.com"},
                                  agent=FailAgent(), fetcher=fake_fetch2)
    check("抽取失败 status=error", cap4["status"] == "error" and "模型抽风" in cap4.get("error", ""))

    print("== 7. 删除来源 ==")
    r = c.delete("/api/admin/web-sources/nope", headers=H)
    check("删除不存在 404", r.status_code == 404)
    r = c.delete("/api/admin/web-sources/" + sid, headers=H)
    check("删除 200", r.status_code == 200)
    r = c.get("/api/admin/web-sources", headers=H)
    check("删后列表为空", r.get_json() == [])


if __name__ == "__main__":
    run_all()
    print("\n%d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
