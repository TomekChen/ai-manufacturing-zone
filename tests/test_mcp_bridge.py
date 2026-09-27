# -*- coding: utf-8 -*-
"""A5 MCP 桥测试（离线打桩，不真发请求）。

运行：F:/projects/ai-manufacturing-zone/.venv/Scripts/python.exe tests/test_mcp_bridge.py
（桥依赖 mcp 包，装在项目 venv，其他套件用的解释器跑不了本文件。）
"""
import os
import sys
import urllib.error

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

import mcp_bridge  # noqa: E402
from mcp_bridge import PortalError, _flatten_agent_run  # noqa: E402

_REAL_HTTP = mcp_bridge._http  # 各用例会替换 _http 打桩，测真实传输层前要还原

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  -", name)
    else:
        FAIL += 1
        print("  FAIL-", name, extra)


def stub_http(fn):
    mcp_bridge._http = fn


AGENTS = [{"id": "prd-advisor", "name": "售前方案师", "role": "PRD 生成智能体",
           "desc": "d", "caps": ["c"], "status": "live",
           "endpoint": "/api/agents/prd-advisor/run", "triggers": ["prd"]},
          {"id": "kb-assistant", "name": "知识管家", "role": "知识库问答智能体",
           "desc": "d", "caps": ["c"], "status": "live",
           "endpoint": "/api/agents/kb-assistant/run", "triggers": ["问答"]}]

MAKE_RESULT = {"ok": True, "agent_id": "prd-advisor",
               "result": {"prd": "# 方案", "grounded": True, "sources": ["知识A"]},
               "refs": ["知识A"], "confidence": 0.6, "mode": "guide", "model": "stub"}


def test_list_agents():
    print("\n[list_agents]")
    calls = []

    def fake(method, path, body=None):
        calls.append((method, path))
        return AGENTS
    stub_http(fake)
    out = mcp_bridge.list_agents()
    check("GET /api/agents", calls == [("GET", "/api/agents")], str(calls))
    check("返回 2 个且只留展示字段（不带 triggers/status）",
          len(out) == 2 and all("triggers" not in x and "status" not in x for x in out))

    def boom(method, path, body=None):
        raise PortalError("门户返回 500：炸了")
    stub_http(boom)
    out = mcp_bridge.list_agents()
    check("门户故障收敛为 error 字段不抛异常",
          len(out) == 1 and "error" in out[0] and "500" in out[0]["error"])


def test_ask_kb():
    print("\n[ask_knowledge_base]")
    calls = []

    def fake(method, path, body=None):
        calls.append((method, path, body))
        return {"answer": "答案是…", "sources": [{"title": "知识A", "url": "u"}],
                "intent": "knowledge", "ask_id": "x", "engine": "stub"}
    stub_http(fake)
    out = mcp_bridge.ask_knowledge_base("什么是 MES")
    check("POST /api/kb/ask 且 question 透传",
          calls == [("POST", "/api/kb/ask", {"question": "什么是 MES", "history": []})],
          str(calls))
    check("只回 answer/sources/intent（不带 ask_id/engine 内部字段）",
          set(out) == {"answer", "sources", "intent"} and out["answer"] == "答案是…")

    out = mcp_bridge.ask_knowledge_base("追问", history=[{"question": "上", "answer": "答"}])
    check("history 透传", calls[-1][2]["history"] == [{"question": "上", "answer": "答"}])

    def boom(method, path, body=None):
        raise PortalError("门户返回 429：提问太频繁")
    stub_http(boom)
    out = mcp_bridge.ask_knowledge_base("q")
    check("限流错误透出 429 文案", "429" in out.get("error", ""))


def test_generate_prd():
    print("\n[generate_prd_proposal]")
    calls = []

    def fake(method, path, body=None):
        calls.append((method, path, body))
        return MAKE_RESULT
    stub_http(fake)
    out = mcp_bridge.generate_prd_proposal("某某精密", "汽车零部件", "变速箱壳体")
    check("POST /api/agents/prd-advisor/run",
          calls[-1][:2] == ("POST", "/api/agents/prd-advisor/run"))
    check("入参映射完整", calls[-1][2] == {
        "company": "某某精密", "industry": "汽车零部件", "business": "变速箱壳体",
        "mode": "guide", "raw_requirements": ""}, str(calls[-1][2]))
    check("make_result 打平：result 字段上提 + _confidence/_refs 附加",
          out["prd"] == "# 方案" and out["_confidence"] == 0.6
          and out["_refs"] == ["知识A"] and "result" not in out)

    out = mcp_bridge.generate_prd_proposal("某厂", "i", "b", mode="normalize",
                                           raw_requirements="要一个 MES")
    check("normalize 模式参数透传", calls[-1][2]["mode"] == "normalize"
          and calls[-1][2]["raw_requirements"] == "要一个 MES")

    def boom(method, path, body=None):
        raise PortalError("门户返回 503：智能体暂不可用")
    stub_http(boom)
    out = mcp_bridge.generate_prd_proposal("x", "y", "z")
    check("失败收敛为 error 字段", "503" in out.get("error", ""))


def test_dispatch():
    print("\n[dispatch_task]")
    calls = []

    def fake(method, path, body=None):
        calls.append((method, path, body))
        return {"ok": True, "matched": "prd-advisor"}
    stub_http(fake)
    out = mcp_bridge.dispatch_task("帮我写方案", auto_run=True)
    check("body 映射 task/auto_run",
          calls[-1] == ("POST", "/api/agents/dispatch",
                        {"task": "帮我写方案", "auto_run": True}), str(calls[-1]))
    check("返回原样", out.get("matched") == "prd-advisor")


def test_flatten_edge():
    print("\n[_flatten_agent_run 边界]")
    check("result 是字符串原样上提", _flatten_agent_run({"result": "纯文本"}) == "纯文本")
    check("非 make_result 形状原样返回", _flatten_agent_run({"error": "x"}) == {"error": "x"})
    check("result 为 None 原样返回", _flatten_agent_run({"ok": True}) == {"ok": True})


def test_http_error_mapping():
    print("\n[_http 错误映射（真实 urllib 路径）]")
    mcp_bridge._http = _REAL_HTTP  # 还原真传输层（前面的用例换成了打桩）
    saved = mcp_bridge.urllib.request.urlopen

    def raise_http_error(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
    mcp_bridge.urllib.request.urlopen = raise_http_error
    try:
        mcp_bridge._http("POST", "/api/prd-sessions", {"a": 1})
        check("HTTPError 应抛 PortalError", False)
    except PortalError as e:
        check("非 2xx → PortalError 带状态码", "429" in str(e))
    finally:
        mcp_bridge.urllib.request.urlopen = saved

    saved2 = mcp_bridge.urllib.request.urlopen

    def raise_conn(req, timeout=None):
        raise OSError("connection refused")
    mcp_bridge.urllib.request.urlopen = raise_conn
    try:
        mcp_bridge._http("GET", "/api/agents")
        check("网络错应抛 PortalError", False)
    except PortalError as e:
        check("网络错 → PortalError 带门户地址", mcp_bridge.PORTAL_BASE_URL in str(e))
    finally:
        mcp_bridge.urllib.request.urlopen = saved2


if __name__ == "__main__":
    test_list_agents()
    test_ask_kb()
    test_generate_prd()
    test_dispatch()
    test_flatten_edge()
    test_http_error_mapping()
    print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
