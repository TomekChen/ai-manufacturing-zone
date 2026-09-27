# -*- coding: utf-8 -*-
"""A5 MCP 桥：把门户的智能体与知识问答暴露为 MCP 工具，供本机 MCP 客户端调用。

stdio 传输：MCP 客户端（Claude Desktop / Qoder 等）按配置用 python 拉起本进程，
零服务端改动——全部走门户公开 HTTP API，限流、校验、错误形状天然复用。

依赖：pip install "mcp<2"（FastMCP 在 2.x 已改名，钉 1.x 稳定 API）。
环境变量：PORTAL_BASE_URL（默认线上 http://47.115.223.159:8804）。

工具面：
  list_agents             查看在线智能体及其能力
  ask_knowledge_base      制造业数字化知识问答（10 次/分钟）
  generate_prd_proposal   售前方案师生成 PRD（每 IP 每小时 5 次）
  dispatch_task           planner 按任务文本自动路由到合适智能体
"""
import json
import os
import urllib.error
import urllib.request

from mcp.server.fastmcp import FastMCP

PORTAL_BASE_URL = (os.environ.get("PORTAL_BASE_URL")
                   or "http://47.115.223.159:8804").rstrip("/")

mcp = FastMCP("ai-manufacturing-zone")


class PortalError(Exception):
    """门户调用失败（网络错误或非 2xx），message 已是人类可读文案。"""


def _http(method, path, body=None):
    """门户 HTTP 唯一 I/O 口：返回解析后的 dict/list；非 2xx/网络错抛 PortalError。

    测试打桩这里（monkeypatch mcp_bridge._http），不真发请求。
    """
    req = urllib.request.Request(
        PORTAL_BASE_URL + path, method=method,
        data=json.dumps(body).encode("utf-8") if body is not None else None)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = (json.loads(e.read().decode("utf-8")) or {}).get("error") or ""
        except Exception:
            pass
        raise PortalError("门户返回 %s：%s" % (e.code, detail or "无详情")) from None
    except Exception as e:
        raise PortalError("无法连接门户（%s）：%s" % (PORTAL_BASE_URL, str(e)[:120])) from None
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def _flatten_agent_run(out):
    """通用 run 端点返回 make_result 形状，抽出结构化结果；失败时原样带错误返回。"""
    if isinstance(out, dict) and out.get("result") is not None:
        res = out["result"]
        if isinstance(res, dict):
            flat = dict(res)
            flat["_confidence"] = out.get("confidence")
            flat["_refs"] = out.get("refs")
            return flat
        return res
    return out


@mcp.tool()
def list_agents() -> list:
    """列出智能制造专区的在线智能体（id/名称/职责/能力/入口）。

    返回 live 状态的智能体元数据列表，可用于了解有哪些能力、该调哪个工具。
    """
    try:
        rows = _http("GET", "/api/agents")
    except PortalError as e:
        return [{"error": str(e)}]
    return [{"id": a.get("id"), "name": a.get("name"), "role": a.get("role"),
             "desc": a.get("desc"), "caps": a.get("caps"),
             "endpoint": a.get("endpoint")} for a in rows]


@mcp.tool()
def ask_knowledge_base(question: str, history: list = None) -> dict:
    """制造业数字化知识问答：AI 落地场景、MES/视检/标注等行业认知、平台使用问题。

    回答基于门户知识库检索并附引用来源，引用不足时明确说明、不编造。
    多轮追问可把上一轮问答对列表传给 history（[{"question":..,"answer":..}, ...]）。
    限流：每 IP 每分钟 10 次。
    """
    try:
        res = _http("POST", "/api/kb/ask",
                    {"question": question, "history": history or []})
    except PortalError as e:
        return {"error": str(e)}
    return {"answer": res.get("answer"), "sources": res.get("sources"),
            "intent": res.get("intent")}


@mcp.tool()
def generate_prd_proposal(company: str, industry: str, business: str,
                          mode: str = "guide", raw_requirements: str = "") -> dict:
    """售前方案师：为制造客户生成《AI 智能体平台功能需求 PRD》方案。

    Args:
        company: 客户公司名称（必填）
        industry: 客户所属行业，如 汽车零部件 / 3C 电子（必填）
        business: 主营业务介绍，越具体方案越贴合（必填）
        mode: guide=客户需求模糊，出草稿方案+待澄清问题；normalize=已有明确需求，规范化并标注缺口
        raw_requirements: mode=normalize 时填客户原始需求原文

    生成前自动检索知识库做行业接地，结果附引用。限流：每 IP 每小时 5 次。
    """
    try:
        out = _http("POST", "/api/agents/prd-advisor/run",
                    {"company": company, "industry": industry,
                     "business": business, "mode": mode,
                     "raw_requirements": raw_requirements})
    except PortalError as e:
        return {"error": str(e)}
    return _flatten_agent_run(out)


@mcp.tool()
def dispatch_task(task: str, auto_run: bool = False) -> dict:
    """把一句自然语言任务描述交给 planner，自动路由到合适的智能体。

    Args:
        task: 任务文本，如「帮我给某某公司写个方案」「查一下什么是 MES」
        auto_run: true 时直接代为执行并带回结果（消耗对应智能体的限流额度）

    返回匹配到的智能体元数据；auto_run=true 时额外带 run 结果。
    """
    try:
        out = _http("POST", "/api/agents/dispatch",
                    {"task": task, "auto_run": auto_run})
    except PortalError as e:
        return {"error": str(e)}
    return out


if __name__ == "__main__":
    mcp.run()
