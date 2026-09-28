# -*- coding: utf-8 -*-
"""MCP 远程端点（A6）：Streamable HTTP 无状态实现，外部 MCP 客户端直连 /mcp。

与 stdio 桥（mcp_bridge.py，跑在客户端本机）互补：远程模式零安装，
Claude/Qoder/Cursor 等填一个 URL 即可。无状态——不签发 Mcp-Session-Id，
每个 POST 独立处理，响应 application/json（SSE 流对无状态服务是可选的，
GET /mcp 按 spec 返回 405）。

工具实现直调内部函数（不走 HTTP 回环）；每个工具沿用公开 API 的同款限流，
限流超额按 JSON-RPC error 返回 HTTP 429。
"""
import json

from flask import Blueprint, request, jsonify

import agents
import agents_api
import qa

bp = Blueprint("mcp_endpoint", __name__)

SERVER_INFO = {"name": "ai-manufacturing-zone", "version": "1.0.0"}
PROTOCOL_VERSION = "2025-03-26"
_SUPPORTED_PROTOCOL_VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18"}

JSONRPC_PARSE_ERROR = -32700
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602

# 每工具限流：与公开 HTTP API 同款额度（见 qa/agents_api 各端点）
_TOOL_LIMITS = {
    "ask_knowledge_base": (10, 60),
    "generate_prd_proposal": (5, 3600),
    "dispatch_task": (5, 3600),
    "list_agents": None,
}


# ── 工具实现（直调内部函数；ValueError/RuntimeError 收敛为 isError） ─────────

def _tool_list_agents():
    return [{"id": a.get("id"), "name": a.get("name"), "role": a.get("role"),
             "desc": a.get("desc"), "caps": a.get("caps"),
             "endpoint": a.get("endpoint")}
            for a in agents.list_agents(only_live=True)]


def _tool_ask_knowledge_base(question, history=None):
    return {"answer": qa.kb_ask_core(question, history=history or []).get("answer"),
            "note": "完整来源引用见门户问答页"}


def _tool_generate_prd_proposal(company, industry, business,
                                mode="guide", raw_requirements=""):
    agent = agents.get_agent("prd-advisor")
    if agent is None or agent.status != "live":
        raise RuntimeError("智能体不存在或未上线")
    if not agent.available():
        raise RuntimeError("未配置 DASHSCOPE_API_KEY，方案生成暂不可用")
    out = agent.run({"company": company, "industry": industry,
                     "business": business, "mode": mode,
                     "raw_requirements": raw_requirements})
    res = out.get("result")
    if isinstance(res, dict):
        res = dict(res)
        res["_confidence"] = out.get("confidence")
        res["_refs"] = out.get("refs")
    return res


def _tool_dispatch_task(task, auto_run=False):
    agent = agents.route_task(task)
    if agent is None:
        return {"ok": False, "matched": None, "message": "暂无可处理该任务的智能体"}
    out = {"ok": True, "matched": agent.id, "agent": agent.meta()}
    if auto_run:
        out["run"] = agents_api._run_agent(agent, {}).get_json()
    return out


_TOOLS = [
    {"name": "list_agents",
     "description": "列出智能制造专区的在线智能体（id/名称/职责/能力），可用于了解有哪些能力、该调哪个工具。",
     "inputSchema": {"type": "object", "properties": {}, "required": []},
     "fn": _tool_list_agents},
    {"name": "ask_knowledge_base",
     "description": "制造业数字化知识问答：AI 落地场景、MES/视检/标注等行业认知问题。回答基于门户知识库，引用不足时明确说明。限流 10 次/分钟。",
     "inputSchema": {"type": "object", "properties": {
         "question": {"type": "string", "description": "问题（必填，≤500 字）"},
         "history": {"type": "array", "description": "多轮上下文 [{question, answer}]"},
     }, "required": ["question"]},
     "fn": _tool_ask_knowledge_base},
    {"name": "generate_prd_proposal",
     "description": "售前方案师：为制造客户生成《AI 智能体平台功能需求 PRD》。mode=guide 出草稿+澄清问题；normalize 规范化原始需求。限流 5 次/小时。",
     "inputSchema": {"type": "object", "properties": {
         "company": {"type": "string", "description": "客户公司名称（必填）"},
         "industry": {"type": "string", "description": "客户所属行业"},
         "business": {"type": "string", "description": "主营业务介绍"},
         "mode": {"type": "string", "enum": ["guide", "normalize"]},
         "raw_requirements": {"type": "string", "description": "normalize 模式下的客户原始需求"},
     }, "required": ["company", "industry", "business"]},
     "fn": _tool_generate_prd_proposal},
    {"name": "dispatch_task",
     "description": "把一句自然语言任务描述交给 planner，自动路由到合适的智能体；auto_run=true 时直接代为执行。",
     "inputSchema": {"type": "object", "properties": {
         "task": {"type": "string", "description": "任务文本"},
         "auto_run": {"type": "boolean", "description": "代为执行并带回结果"},
     }, "required": ["task"]},
     "fn": _tool_dispatch_task},
]


def _rpc_result(id_, result):
    return jsonify({"jsonrpc": "2.0", "id": id_, "result": result})


def _rpc_error(id_, code, message, status=200):
    return jsonify({"jsonrpc": "2.0", "id": id_,
                    "error": {"code": code, "message": message}}), status


def _call_tool(name, args):
    """执行工具：结果转 text content；业务异常转 isError 结果（协议错误才是 JSON-RPC error）。"""
    tool = next((t for t in _TOOLS if t["name"] == name), None)
    if tool is None:
        return None
    try:
        data = tool["fn"](**(args or {}))
        text = json.dumps(data, ensure_ascii=False, default=str)
        return {"content": [{"type": "text", "text": text}], "isError": False}
    except (ValueError, RuntimeError) as e:
        return {"content": [{"type": "text", "text": str(e)}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": "执行失败：%s" % str(e)[:160]}],
                "isError": True}


@bp.route("/mcp", methods=["POST"])
def mcp_post():
    """Streamable HTTP：单个 JSON-RPC 消息进出，无状态。"""
    try:
        msg = request.get_json(force=True, silent=False)
    except Exception:
        return _rpc_error(None, JSONRPC_PARSE_ERROR, "请求不是合法 JSON", 400)
    if not isinstance(msg, dict):
        return _rpc_error(None, JSONRPC_PARSE_ERROR, "请求不是 JSON-RPC 消息", 400)

    method = msg.get("method") or ""
    id_ = msg.get("id")
    is_notification = id_ is None

    if method == "initialize":
        client_ver = (msg.get("params") or {}).get("protocolVersion")
        return _rpc_result(id_, {
            "protocolVersion": client_ver if client_ver in _SUPPORTED_PROTOCOL_VERSIONS
            else PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    if method.startswith("notifications/"):
        # initialized/cancelled 等通知：无需响应体，202 表示已接收
        return "", 202
    if method == "ping":
        return _rpc_result(id_, {})
    if method == "tools/list":
        return _rpc_result(id_, {"tools": [
            {k: t[k] for k in ("name", "description", "inputSchema")} for t in _TOOLS]})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name") or ""
        tool = next((t for t in _TOOLS if t["name"] == name), None)
        if tool is None:
            return _rpc_error(id_, JSONRPC_METHOD_NOT_FOUND, "未知工具：%s" % name)
        limit = _TOOL_LIMITS.get(name)
        if limit:
            from core import rate_limited
            if rate_limited(request.remote_addr, limit=limit[0], window=limit[1],
                            bucket="mcp_tool_%s" % name):
                return _rpc_error(id_, JSONRPC_INVALID_PARAMS,
                                  "调用太频繁，请稍后再试（%d 次/%d 秒）" % limit, status=429)
        result = _call_tool(name, params.get("arguments") or {})
        return _rpc_result(id_, result)
    if is_notification:
        return "", 202
    return _rpc_error(id_, JSONRPC_METHOD_NOT_FOUND, "未知方法：%s" % method)


@bp.route("/mcp", methods=["GET", "DELETE"])
def mcp_unsupported():
    """无状态服务不提供 SSE 流与会话终止，按 spec 返回 405。"""
    return jsonify({"error": "Method Not Allowed"}), 405
