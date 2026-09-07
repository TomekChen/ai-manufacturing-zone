# -*- coding: utf-8 -*-
"""售前方案师（A1 上线，A2 收编进注册表框架）：PRD 生成垂直智能体。

与后台版（/api/admin/prd/generate）共用同一引擎 kb_prd.generate_prd；
WeKnora 开启时接地直走 rag/engine（store 仅回退用，见 runtime.py）。
"""
from rag import prd as kb_prd

from .base import AgentBase, make_result
from .registry import register


@register
class PrdAdvisorAgent(AgentBase):
    id = "prd-advisor"
    name = "售前方案师"
    role = "PRD 生成智能体"
    emoji = "🧭"
    color = "blue"
    desc = ("填写客户公司与业务介绍，一键生成一份面向该客户的《AI 智能体平台功能需求 PRD》，"
            "生成前自动检索知识库做行业接地。")
    caps = [
        "引导模式：客户没想清楚，先出方案草稿 + 待澄清问题",
        "规范化模式：整理客户原始需求并标注缺口与歧义",
        "知识库行业接地，方案贴合智能制造真实场景",
    ]
    status = "live"
    endpoint = "/api/agents/prd-advisor/run"
    triggers = ["prd", "方案", "需求文档", "售前", "标书", "可行性"]

    def available(self):
        return kb_prd.has_api_key()

    def run(self, payload):
        r = kb_prd.generate_prd(None, payload or {})
        grounded = bool(r.get("grounded"))
        confidence = 0.6 if grounded else 0.3
        return make_result(
            self, r,
            refs=r.get("sources") or [],
            confidence=confidence,
            mode=r.get("mode"),
            model=r.get("model"),
        )
