# -*- coding: utf-8 -*-
"""A2 编排层单测：注册表 + planner 派发 + 通用/兼容 run 端点（离线、确定性、不触发真 LLM）。

运行：py tests/test_agents.py

打桩说明：本机若配了 DASHSCOPE_API_KEY，合法入参会真实调用 LLM（烧钱且慢），
必须把 rag.prd 的 has_api_key/generate_prd 换成假实现——app 与 agents.prd_advisor
引用的是同一个 rag.prd 模块对象，桩一处两边生效。
"""
import os
import sys
from types import SimpleNamespace

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

# 与 tests/test_rag_eval.py 相同的本机缺库兜底（faiss/bs4 原生依赖不装也能跑）
for mod in ("faiss", "bs4", "bs4.BeautifulSoup"):
    try:
        __import__(mod)
    except ImportError:
        sys.modules[mod] = type(sys)("fake_" + mod)
if "bs4" in sys.modules and not hasattr(sys.modules["bs4"], "BeautifulSoup"):
    sys.modules["bs4.BeautifulSoup"] = type(sys)("fake_bs")
    sys.modules["bs4"].BeautifulSoup = object

import agents  # noqa: E402  import 即注册
from agents.base import AgentBase, make_result  # noqa: E402
from agents.registry import register, get_agent, route_task  # noqa: E402
import app  # noqa: E402


def fake_generate_prd(KB, payload):
    if not (payload.get("company") or "").strip():
        raise ValueError("请填写公司名称")
    if len((payload.get("business") or "").strip()) < 5:
        raise ValueError("业务介绍太短")
    return {"prd": "# 假 PRD", "grounded": True, "hits": 3, "mode": payload.get("mode", "guide"),
            "model": "stub", "sources": [{"title": "来源A", "url": ""}]}


app.kb_prd.has_api_key = lambda: True
app.kb_prd.generate_prd = fake_generate_prd

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  -", name)
    else:
        FAIL += 1
        print("  FAIL-", name, extra)


def expect_error(name, exc, fn):
    try:
        fn()
        check(name + " (应抛 %s)" % exc.__name__, False)
    except exc:
        check(name, True)
    except Exception as e:
        check(name + " 但抛了 %r" % e, False)


# ---------- 注册表 / make_result（纯单元，不起 HTTP） ----------
def test_registry_unit():
    print("\n[registry / make_result]")
    a = get_agent("prd-advisor")
    check("get_agent 命中 prd-advisor", a is not None and a.id == "prd-advisor")
    check("get_agent 未命中返回 None", get_agent("no-such-agent") is None)
    check("prd-advisor status=live", a.status == "live")
    meta = a.meta()
    for k in ("id", "name", "role", "emoji", "color", "desc", "caps", "status", "endpoint", "triggers"):
        check("meta 含字段 %s" % k, k in meta, str(sorted(meta.keys())))
    check("endpoint 指向通用 run", meta["endpoint"] == "/api/agents/prd-advisor/run")
    check("list_agents(only_live) 含 prd-advisor",
          any(x["id"] == "prd-advisor" for x in agents.list_agents(only_live=True)))

    expect_error("重复 id 注册报 ValueError", ValueError,
                 lambda: register(type("Dup", (), {"id": "prd-advisor"})))
    expect_error("空 id 注册报 ValueError", ValueError,
                 lambda: register(type("Empty", (), {"id": "  "})))

    r = make_result(SimpleNamespace(id="x"), {"k": 1}, refs=[{"title": "t"}], confidence=0.7, mode="guide")
    check("make_result 统一契约", r["ok"] is True and r["agent_id"] == "x"
          and r["result"] == {"k": 1} and r["refs"] == [{"title": "t"}]
          and r["confidence"] == 0.7 and r["mode"] == "guide")

    check("route_task 命中：含 'prd' 的任务 → prd-advisor", route_task("帮我写一份 PRD 方案") is a)
    check("route_task 大小写不敏感", route_task("做个prd") is a)
    check("route_task 命中：中文触发词", route_task("我们要做售前方案") is a)
    check("route_task 未命中返回 None", route_task("今天天气怎么样") is None)

    # 未上线智能体：注册表(公开)不可见、路由跳过
    @register
    class _Waiter(AgentBase):
        id = "test-waiter"
        name = "测试待上线"
        role = "占位"
        emoji = "🧪"
        color = "blue"
        desc = "d"
        caps = []
        status = "coming_soon"
        endpoint = "/api/agents/test-waiter/run"
        triggers = ["waiter"]

        def run(self, payload):
            return make_result(self, "ok")

    check("coming_soon 不进公开注册表",
          all(x["id"] != "test-waiter" for x in agents.list_agents(only_live=True)))
    check("route_task 跳过未上线智能体", route_task("我要 waiter 服务") is None)


# ---------- HTTP 端点 ----------
VALID = {"company": "测试公司", "business": "这是一段足够长的业务介绍"}


def test_endpoints():
    print("\n[endpoints]")
    c = app.app.test_client()

    r = c.get("/api/agents")
    data = r.get_json()
    check("GET /api/agents 200", r.status_code == 200)
    check("注册表首项 prd-advisor", isinstance(data, list) and data and data[0]["id"] == "prd-advisor")

    r = c.post("/api/agents/prd-advisor/run", json=VALID)
    body = r.get_json()
    check("通用 run 合法入参 200", r.status_code == 200, str(body)[:120])
    check("统一契约：ok/agent_id", body.get("ok") is True and body.get("agent_id") == "prd-advisor")
    check("统一契约：result.prd 来自打桩引擎", body.get("result", {}).get("prd") == "# 假 PRD")
    check("统一契约：refs 透传 sources", body.get("refs") == [{"title": "来源A", "url": ""}])
    check("统一契约：confidence 接地后 0.6", body.get("confidence") == 0.6)
    check("统一契约：mode/model 透传", body.get("mode") == "guide" and body.get("model") == "stub")

    r = c.post("/api/agents/prd-advisor/run", json={"company": "", "business": ""})
    check("空入参 400（校验在 LLM 前）", r.status_code == 400 and bool((r.get_json() or {}).get("error")))

    # 限流：agent_prd-advisor 桶，空入参那发也占名额（限流先于校验）。
    # 名额账本：统一契约合法 1 发 + 空入参 1 发 = 已占 2 席；循环 5 发 → 200×3 后 429×2。
    codes = []
    for i in range(5):
        rr = c.post("/api/agents/prd-advisor/run", json=VALID)
        codes.append(rr.status_code)
    check("限流：已占 2 席后循环 5 发 → 200×3 然后 429×2",
          codes == [200, 200, 200, 429, 429], str(codes))
    check("限流桶隔离：记在 agent_prd-advisor 桶",
          len(app._ask_limits.get("agent_prd-advisor", {}).get("127.0.0.1", [])) == 5)
    check("限流桶隔离：default 桶未被污染", "127.0.0.1" not in app._ask_limits.get("default", {}))
    check("限流桶隔离：旧 agent_prd 桶尚未使用", "127.0.0.1" not in app._ask_limits.get("agent_prd", {}))

    r = c.post("/api/agents/ghost/run", json=VALID)
    check("不存在的智能体 404", r.status_code == 404)
    r = c.post("/api/agents/test-waiter/run", json=VALID)
    check("未上线智能体 404", r.status_code == 404)

    # dispatch：planner 关键词路由
    r = c.post("/api/agents/dispatch", json={"task": "   "})
    check("dispatch 空 task 400", r.status_code == 400)
    r = c.post("/api/agents/dispatch", json={"task": "今天天气怎么样"})
    body = r.get_json()
    check("dispatch 未命中 404 + matched=None",
          r.status_code == 404 and body.get("ok") is False and body.get("matched") is None)
    r = c.post("/api/agents/dispatch", json={"task": "帮客户写个售前 prd"})
    body = r.get_json()
    check("dispatch 命中：matched=prd-advisor", r.status_code == 200 and body.get("matched") == "prd-advisor")
    check("dispatch 命中：agent.meta() 一并返回", body.get("agent", {}).get("id") == "prd-advisor")
    check("dispatch 非 auto_run 不代跑", "run" not in body)
    r = c.post("/api/agents/dispatch",
               json={"task": "写prd", "auto_run": True, "payload": VALID})
    body = r.get_json()
    check("dispatch auto_run 代跑带回结果",
          r.status_code == 200 and body.get("run", {}).get("result", {}).get("prd") == "# 假 PRD",
          str(body)[:160])
    check("dispatch 限流桶独立计数",
          len(app._ask_limits.get("agent_dispatch", {}).get("127.0.0.1", [])) == 4)

    # A1 兼容路径：扁平形状
    r = c.post("/api/agents/prd/run", json=VALID)
    body = r.get_json()
    check("legacy /api/agents/prd/run 200", r.status_code == 200)
    check("legacy 扁平形状：无 result 包装", "result" not in body and body.get("prd") == "# 假 PRD")
    check("legacy 扁平形状：grounded 透传", body.get("grounded") is True)
    r = c.post("/api/agents/prd/run", json={"company": ""})
    check("legacy 空入参 400", r.status_code == 400)

    # admin 版端点不受影响
    r = c.post("/api/admin/prd/generate", json=VALID)
    check("admin PRD 端点未登录仍 401", r.status_code == 401)


if __name__ == "__main__":
    test_registry_unit()
    test_endpoints()
    print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
