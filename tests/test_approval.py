# -*- coding: utf-8 -*-
"""A10 审批留痕中间层单测：提交即 pending → 批准/驳回 → append-only 留痕（离线、确定性、不触发真 LLM）。

运行：py tests/test_approval.py

打桩：审批单内嵌的智能体执行走注册表实例，测试直接替换 order-catcher
实例的 run 方法（finally 恢复），available() 走 rag.prd.has_api_key 桩。
数据写真实 DATA_DIR 的 approvals.json，测试前后清理。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

# 与 tests/test_agents.py 相同的本机缺库兜底（faiss/bs4 原生依赖不装也能跑）
for mod in ("faiss", "bs4", "bs4.BeautifulSoup"):
    try:
        __import__(mod)
    except ImportError:
        sys.modules[mod] = type(sys)("fake_" + mod)
if "bs4" in sys.modules and not hasattr(sys.modules["bs4"], "BeautifulSoup"):
    sys.modules["bs4.BeautifulSoup"] = type(sys)("fake_bs")
    sys.modules["bs4"].BeautifulSoup = object

import app  # noqa: E402  装配即注册路由
import agents.order_catcher as oc  # noqa: E402
import approval  # noqa: E402
from agents.registry import get_agent  # noqa: E402
from core import DATA_DIR  # noqa: E402

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

# 本机未必配 DASHSCOPE_API_KEY：available() 走 rag.prd.has_api_key，桩一处生效
oc.kb_prd.has_api_key = lambda: True

GOOD_ORDER = {"order_no": "PO-2026-88", "customer": "某某精密厂", "contact": "",
              "products": [{"name": "法兰盘", "spec": "", "qty": "100", "unit": "件"}],
              "delivery_date": "2026-11-01", "notes": "", "missing": []}

RECON_RESULT = {"matched": [{"our": "应收 50,000", "bank": "收 50,000", "amount": "50,000", "basis": "单号"}],
                "suspected": [], "unmatched_bank": ["付 32,100"], "unmatched_ledger": ["应付 32,100"],
                "suggestions": ["借 银行存款 50,000 / 贷 应收账款 50,000"],
                "summary": {"matched_count": 1, "suspected_count": 0, "unmatched_count": 2},
                "notes": ""}


def clear_data():
    f = os.path.join(DATA_DIR, "approvals.json")
    if os.path.exists(f):
        os.remove(f)
    app._ask_limits.pop("approval_submit", None)


class StubAgent:
    """注册表实例的 run 替换桩：模拟正常/异常/坏输出。"""

    def __init__(self, real):
        self._real = real

    def __enter__(self):
        self.saved = self._real.run
        self._real.run = lambda payload: {
            "ok": True, "agent_id": self._real.id,
            "result": dict(GOOD_ORDER), "confidence": 0.8}
        self.saved_key = oc.kb_prd.has_api_key
        oc.kb_prd.has_api_key = lambda: True
        return self._real

    def __exit__(self, *exc):
        self._real.run = self.saved
        oc.kb_prd.has_api_key = self.saved_key
        return False


def test_submit():
    print("\n[approval / 公开提交]")
    c = app.app.test_client()
    clear_data()
    ag = get_agent("order-catcher")

    with StubAgent(ag):
        r = c.post("/api/approvals", json={"agent_id": "order-catcher", "payload": {"text": "法兰盘 100 件"}})
    check("提交 200 且 pending", r.status_code == 200 and r.get_json().get("status") == "pending", str(r.get_json())[:150])
    aid = r.get_json()["id"]
    check("返回摘要（订单形状）", "某某精密厂" in r.get_json()["summary"])

    items = approval._items()
    check("已落账 pending", len(items) == 1 and items[0]["status"] == "pending")
    check("trail 首条 submitted",
          items[0]["trail"][0]["action"] == "submitted" and items[0]["result"] == GOOD_ORDER)
    check("payload 原样存档（可追溯输入）", items[0]["payload"] == {"text": "法兰盘 100 件"})

    r = c.post("/api/approvals", json={"agent_id": "ghost-agent", "payload": {"text": "x"}})
    check("未知智能体 404", r.status_code == 404)
    r = c.post("/api/approvals", json={"agent_id": "order-catcher"})
    check("payload 缺失 400", r.status_code == 400)
    r = c.post("/api/approvals", json={"agent_id": "order-catcher", "payload": {}})
    check("payload 空 dict 400", r.status_code == 400)

    old_key = oc.kb_prd.has_api_key
    try:
        oc.kb_prd.has_api_key = lambda: False
        r = c.post("/api/approvals", json={"agent_id": "order-catcher", "payload": {"text": "x"}})
        check("引擎不可用 503", r.status_code == 503)
    finally:
        oc.kb_prd.has_api_key = old_key

    with StubAgent(ag):
        old_run = ag.run
        try:
            ag.run = lambda payload: (_ for _ in ()).throw(RuntimeError("模型未返回结构化结果"))
            r = c.post("/api/approvals", json={"agent_id": "order-catcher", "payload": {"text": "x"}})
            check("agent RuntimeError 502 且不落账", r.status_code == 502 and len(approval._items()) == 1)
            ag.run = lambda payload: (_ for _ in ()).throw(ValueError("请粘贴订单原文"))
            r = c.post("/api/approvals", json={"agent_id": "order-catcher", "payload": {"text": " "}})
            check("agent ValueError 400 且不落账", r.status_code == 400 and len(approval._items()) == 1)
        finally:
            ag.run = old_run

    check("限流桶独立：approval_submit",
          "127.0.0.1" in app._ask_limits.get("approval_submit", {}))
    return aid


def test_decide(aid):
    print("\n[approval / 审批流转]")
    c = app.app.test_client()

    r = c.get("/api/admin/approvals")
    check("列表未带 token 401", r.status_code == 401)
    r = c.get("/api/admin/approvals", headers=H)
    rows = r.get_json()
    check("列表 200 且不含 payload/result（瘦身）",
          r.status_code == 200 and len(rows) == 1
          and "payload" not in rows[0] and "result" not in rows[0] and "trail" not in rows[0])
    check("列表摘要正确", rows[0]["id"] == aid and "某某精密厂" in rows[0]["summary"])

    r = c.get("/api/admin/approvals/ghost", headers=H)
    check("详情不存在 404", r.status_code == 404)
    r = c.get("/api/admin/approvals/%s" % aid, headers=H)
    check("详情含 trail 与原始入参",
          r.status_code == 200 and len(r.get_json()["trail"]) == 1
          and r.get_json()["payload"] == {"text": "法兰盘 100 件"})

    r = c.post("/api/admin/approvals/%s/approve" % aid, headers=H, json={})
    check("批准 200 且 decided_at 落", r.status_code == 200 and r.get_json()["status"] == "approved"
          and r.get_json()["decided_at"])
    r = c.post("/api/admin/approvals/%s/reject" % aid, headers=H, json={"note": "换理由再改"})
    check("已决再改 409（留痕不可变）", r.status_code == 409)
    d = c.get("/api/admin/approvals/%s" % aid, headers=H).get_json()
    check("trail 增至 2 条（append-only）", len(d["trail"]) == 2
          and d["trail"][-1]["action"] == "approved")
    check("状态仍为 approved（未被驳回覆盖）", d["status"] == "approved")


def test_reject_flow():
    print("\n[approval / 驳回必填理由]")
    c = app.app.test_client()
    clear_data()
    with StubAgent(get_agent("order-catcher")):
        r = c.post("/api/approvals", json={"agent_id": "order-catcher", "payload": {"text": "x"}})
        aid = r.get_json()["id"]

    r = c.post("/api/admin/approvals/%s/reject" % aid, headers=H, json={"note": "   "})
    check("空理由驳回 400", r.status_code == 400)
    r = c.post("/api/admin/approvals/%s/approve" % aid, headers=H, json={})
    check("批准无需理由", r.status_code == 200)
    return aid


def test_summarize():
    print("\n[approval / 摘要生成]")
    s = approval._summarize(RECON_RESULT)
    check("对账形状：完全匹配 1 · 疑似 0 · 未达 2", s == "完全匹配 1 · 疑似 0 · 未达 2", s)
    s = approval._summarize(GOOD_ORDER)
    check("订单形状含客户与交期", "某某精密厂" in s and "2026-11-01" in s, s)
    s = approval._summarize("纯文本结果")
    check("非 dict 兜底截断", "纯文本结果" in s)
    s = approval._summarize({"foo": 1})
    check("未知形状兜底不抛异常", isinstance(s, str) and len(s) > 0)


def test_decide_unit():
    print("\n[approval / decide 单元]")
    clear_data()
    with StubAgent(get_agent("order-catcher")):
        r = app.app.test_client().post("/api/approvals",
                                       json={"agent_id": "order-catcher", "payload": {"text": "x"}})
        aid = r.get_json()["id"]
    check("decide 不存在 → None", approval.decide("ghost", "approved") is None)
    check("decide 正常 → approved", approval.decide(aid, "approved", "ok").get("status") == "approved")
    try:
        approval.decide(aid, "rejected", "again")
        check("二次 decide 抛 AlreadyDecided", False)
    except approval.AlreadyDecided:
        check("二次 decide 抛 AlreadyDecided", True)


def test_rate_limit():
    print("\n[approval / 限流语义：无效请求不占额度]")
    c = app.app.test_client()
    clear_data()
    r = c.post("/api/approvals", json={"agent_id": "ghost", "payload": {"text": "x"}})
    check("404 不占额度", r.status_code == 404)
    with StubAgent(get_agent("order-catcher")):
        codes = [c.post("/api/approvals", json={"agent_id": "order-catcher",
                                                "payload": {"text": "x%d" % i}}).status_code
                 for i in range(6)]
        check("前 5 次有效提交 200", codes[:5] == [200] * 5, str(codes))
        check("第 6 次 429", codes[5] == 429, str(codes))


if __name__ == "__main__":
    try:
        aid = test_submit()
        test_decide(aid)
        test_reject_flow()
        test_summarize()
        test_decide_unit()
        test_rate_limit()
    finally:
        clear_data()
    print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
