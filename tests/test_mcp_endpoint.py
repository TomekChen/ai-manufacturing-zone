# -*- coding: utf-8 -*-
"""A6 MCP 远程端点测试（离线，test_client 直发 JSON-RPC）。

运行：py tests/test_mcp_endpoint.py
"""
import os
import sys
import json

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
import qa  # noqa: E402
import mcp_endpoint  # noqa: E402

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


def rpc(method, params=None, id_=1, raw=None):
    body = raw if raw is not None else {
        "jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    return c.post("/mcp", json=body)


def clear_buckets():
    for k in list(app._ask_limits):
        if k.startswith("mcp_tool_"):
            app._ask_limits[k].pop("127.0.0.1", None)


def test_initialize():
    print("\n[握手 initialize]")
    r = rpc("initialize", {"protocolVersion": "2025-03-26",
                           "capabilities": {}, "clientInfo": {"name": "t"}})
    body = r.get_json() or {}
    check("initialize 200 且回显协议版本",
          r.status_code == 200 and body["result"]["protocolVersion"] == "2025-03-26",
          str(body)[:150])
    check("serverInfo 是门户", body["result"]["serverInfo"]["name"] == "ai-manufacturing-zone")
    check("capabilities 声明 tools", "tools" in body["result"]["capabilities"])

    r2 = rpc("initialize", {"protocolVersion": "2099-01-01"})
    body2 = r2.get_json() or {}
    check("未知客户端版本回退服务端版本",
          body2["result"]["protocolVersion"] == mcp_endpoint.PROTOCOL_VERSION)


def test_notifications():
    print("\n[通知 202]")
    r = c.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    check("notifications/initialized → 202 空体", r.status_code == 202 and not r.get_data())
    r2 = c.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/cancelled",
                              "params": {"requestId": 1}})
    check("cancelled 等通知也是 202", r2.status_code == 202)


def test_tools_list():
    print("\n[tools/list]")
    body = rpc("tools/list").get_json() or {}
    tools = body.get("result", {}).get("tools", [])
    names = [t["name"] for t in tools]
    check("4 个工具与 stdio 桥一致",
          names == ["list_agents", "ask_knowledge_base",
                    "generate_prd_proposal", "dispatch_task"], str(names))
    check("每个工具带 inputSchema 且必填项齐全",
          all("inputSchema" in t for t in tools)
          and "question" in next(t for t in tools
                                 if t["name"] == "ask_knowledge_base")["inputSchema"]["required"])


def test_tools_call():
    print("\n[tools/call]")
    r = rpc("tools/call", {"name": "list_agents", "arguments": {}})
    body = r.get_json() or {}
    result = body.get("result", {})
    check("list_agents 200 且 isError=false",
          r.status_code == 200 and result.get("isError") is False, str(body)[:150])
    data = json.loads(result["content"][0]["text"])
    check("content 是 JSON 文本且含两个智能体",
          isinstance(data, list) and {a["id"] for a in data} == {"prd-advisor", "kb-assistant"})

    # ask_knowledge_base：kb_ask_core 离线打桩（不真调 LLM）
    saved = qa.kb_ask_core
    qa.kb_ask_core = lambda q, history=None: {"answer": "测试答案", "sources": []}
    try:
        r2 = rpc("tools/call", {"name": "ask_knowledge_base",
                                "arguments": {"question": "什么是 MES"}})
        d2 = json.loads((r2.get_json() or {}).get("result", {})["content"][0]["text"])
        check("ask 走 qa.kb_ask_core 且 question 透传", d2.get("answer") == "测试答案")

        def boom(q, history=None):
            raise RuntimeError("引擎故障")
        qa.kb_ask_core = boom
        r3 = rpc("tools/call", {"name": "ask_knowledge_base",
                                "arguments": {"question": "x"}})
        res3 = (r3.get_json() or {}).get("result", {})
        check("业务异常 → isError=true 文本可读（非 JSON-RPC error）",
              res3.get("isError") is True and "引擎故障" in res3["content"][0]["text"])
    finally:
        qa.kb_ask_core = saved

    # generate_prd：离线无 API Key → isError（不打真 LLM）
    r4 = rpc("tools/call", {"name": "generate_prd_proposal",
                            "arguments": {"company": "某厂", "industry": "i", "business": "b"}})
    res4 = (r4.get_json() or {}).get("result", {})
    check("无 Key 时 generate 收敛为 isError",
          res4.get("isError") is True and ("DASHSCOPE" in res4["content"][0]["text"]
                                           or "暂不可用" in res4["content"][0]["text"]))

    r5 = rpc("tools/call", {"name": "dispatch_task",
                            "arguments": {"task": "帮我写个方案"}})
    d5 = json.loads((r5.get_json() or {}).get("result", {})["content"][0]["text"])
    check("dispatch 命中 prd-advisor", d5.get("matched") == "prd-advisor")

    r6 = rpc("tools/call", {"name": "no_such_tool", "arguments": {}})
    err6 = (r6.get_json() or {}).get("error", {})
    check("未知工具 → JSON-RPC -32601",
          r6.status_code == 200 and err6.get("code") == -32601)


def test_protocol_errors():
    print("\n[协议错误]")
    r = c.post("/mcp", data="not-json", content_type="application/json")
    check("非法 JSON → 400 -32700",
          r.status_code == 400 and (r.get_json() or {}).get("error", {}).get("code") == -32700)
    r2 = rpc("bogus/method")
    check("未知方法 → -32601",
          (r2.get_json() or {}).get("error", {}).get("code") == -32601)
    r3 = c.get("/mcp")
    check("GET /mcp → 405（无状态不提供 SSE 流）", r3.status_code == 405)
    r4 = c.delete("/mcp")
    check("DELETE /mcp → 405", r4.status_code == 405)


def test_rate_limit():
    print("\n[按工具限流]")
    clear_buckets()
    last = None
    for _ in range(5):
        last = rpc("tools/call", {"name": "generate_prd_proposal",
                                  "arguments": {"company": "x", "industry": "y", "business": "z"}})
    check("前 5 次正常（无 Key 也走限流前路径）", last.status_code == 200)
    r = rpc("tools/call", {"name": "generate_prd_proposal",
                           "arguments": {"company": "x", "industry": "y", "business": "z"}})
    check("第 6 次 429", r.status_code == 429, str(r.status_code))
    r2 = rpc("tools/call", {"name": "list_agents", "arguments": {}})
    check("其他工具不受影响", r2.status_code == 200)
    clear_buckets()


if __name__ == "__main__":
    test_initialize()
    test_notifications()
    test_tools_list()
    test_tools_call()
    test_protocol_errors()
    test_rate_limit()
    print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
