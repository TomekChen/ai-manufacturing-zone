# -*- coding: utf-8 -*-
"""A7 订单机器人单测：注册表 + 抽取结果契约 + 通用 run 端点 + dispatch 路由（离线、确定性、不触发真 LLM）。

运行：py tests/test_order_catcher.py

打桩：把 agents.order_catcher.chat 换成假实现（模块顶层 import 进来的名字，
桩 agents.order_catcher.chat 一处即生效）；LLM 失败/坏 JSON 的收敛行为也要覆盖。
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

import agents  # noqa: E402  import 即注册
import app  # noqa: E402
import agents.order_catcher as oc  # noqa: E402
from agents.registry import get_agent, route_task  # noqa: E402

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  -", name)
    else:
        FAIL += 1
        print("  FAIL-", name, extra)


GOOD_JSON = '''{"order_no": "PO-2026-1201", "customer": "华阳汽车零部件", "contact": "李经理 13800000000",
"products": [{"name": "304不锈钢法兰盘", "spec": "DN50 带颈对焊", "qty": "2000", "unit": "件"}],
"delivery_date": "2026-12-20", "notes": "木箱包装", "missing": ["delivery_date"]}'''

# 本机未必配 DASHSCOPE_API_KEY：available() 走 rag.prd.has_api_key（与 app 同一模块对象），
# 桩 rag.prd 一处两边生效（同 test_agents.py 对 prd-advisor 的处理）
oc.kb_prd.has_api_key = lambda: True

FENCED_JSON = "```json\n%s\n```" % GOOD_JSON


def fake_chat(messages, temperature=0.1, timeout=60):
    text = messages[-1]["content"]
    if "没有订单信息" in text:
        return FENCED_JSON  # 缺字段的形态也返回合法 JSON（missing 列表承载）
    return GOOD_JSON


oc.chat = fake_chat


def expect_error(name, exc, fn):
    try:
        fn()
        check(name + " (应抛 %s)" % exc.__name__, False)
    except exc:
        check(name, True)
    except Exception as e:
        check(name + " 但抛了 %r" % e, False)


def test_registry():
    print("\n[order-catcher / 注册表]")
    a = get_agent("order-catcher")
    check("已注册且 live", a is not None and a.status == "live")
    meta = a.meta()
    check("meta.ui=order", meta.get("ui") == "order")
    check("endpoint 指向通用 run", meta["endpoint"] == "/api/agents/order-catcher/run")
    check("公开注册表顺序：prd → kb → order → recon",
          [x["id"] for x in agents.list_agents(only_live=True)] ==
          ["prd-advisor", "kb-assistant", "order-catcher", "reconciler"])
    check("route_task：抓单任务命中 order-catcher", route_task("帮我抓一下客户邮件里的订单") is a)
    check("route_task：询盘命中", route_task("新询盘要录入") is a)
    check("route_task：prd 任务仍归 prd-advisor", route_task("写个售前方案") is get_agent("prd-advisor"))


def test_run_unit():
    print("\n[order-catcher / run 单元]")
    a = get_agent("order-catcher")
    r = a.run({"text": "李经理：订购法兰盘 2000 件，12月20日前交货"})
    check("统一契约 ok/agent_id", r["ok"] is True and r["agent_id"] == "order-catcher")
    check("result.customer 抽出", r["result"]["customer"] == "华阳汽车零部件")
    check("result.products 列表", r["result"]["products"][0]["name"] == "304不锈钢法兰盘")
    check("有缺失字段 → confidence 0.6", r["confidence"] == 0.6)

    r2 = a.run({"question": "没有订单信息"})  # 走 fake 的另一分支（missing 含 delivery_date 同样命中）
    check("question 别名入参可用", r2["result"]["order_no"] == "PO-2026-1201")

    expect_error("空文本抛 ValueError", ValueError, lambda: a.run({"text": "   "}))
    expect_error("缺字段抛 ValueError", ValueError, lambda: a.run({}))

    old = oc.chat
    try:
        oc.chat = lambda *a_, **k_: "这不是 JSON"
        expect_error("坏 JSON 收敛 RuntimeError", RuntimeError, lambda: a.run({"text": "x"}))
        oc.chat = lambda *a_, **k_: "前导说明 {\"customer\": \"甲\", \"products\": [], \"missing\": []} 尾部"
        r3 = a.run({"text": "x"})
        check("夹带文字的 JSON 也能解析", r3["result"]["customer"] == "甲")
        oc.chat = lambda *a_, **k_: "{\"customer\": \"甲\"}"  # products/missing 缺省兜底
        r4 = a.run({"text": "x"})
        check("products/missing 非列表兜底为空列表",
              r4["result"]["products"] == [] and r4["result"]["missing"] == [])
        check("关键字段不全 → confidence 0.3", r4["confidence"] == 0.3)

        def boom(*a_, **k_):
            raise ConnectionError("网络断")
        oc.chat = boom
        expect_error("LLM 异常收敛 RuntimeError", RuntimeError, lambda: a.run({"text": "x"}))
    finally:
        oc.chat = old


def test_http():
    print("\n[order-catcher / HTTP 端点]")
    c = app.app.test_client()
    r = c.get("/api/agents")
    ids = [x["id"] for x in r.get_json()]
    check("GET /api/agents 含 order-catcher", "order-catcher" in ids)

    r = c.post("/api/agents/order-catcher/run", json={"text": "法兰盘 2000 件"})
    body = r.get_json()
    check("通用 run 200", r.status_code == 200, str(body)[:120])
    check("统一契约 result.customer", body.get("result", {}).get("customer") == "华阳汽车零部件")
    check("confidence 外层透传", body.get("confidence") == 0.6)

    r = c.post("/api/agents/order-catcher/run", json={"text": "  "})
    check("空文本 400", r.status_code == 400)

    r = c.post("/api/agents/dispatch", json={"task": "客户又下订单了，帮我录入"})
    body = r.get_json()
    check("dispatch 命中 order-catcher",
          r.status_code == 200 and body.get("matched") == "order-catcher", str(body)[:120])

    check("限流桶独立：agent_order-catcher",
          "127.0.0.1" in app._ask_limits.get("agent_order-catcher", {}))


if __name__ == "__main__":
    test_registry()
    test_run_unit()
    test_http()
    print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
