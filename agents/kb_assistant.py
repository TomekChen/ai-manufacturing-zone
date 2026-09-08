# -*- coding: utf-8 -*-
"""知识管家（A3 第二个上线智能体）：知识库问答垂直智能体。

经 agents.runtime.kb_ask（app.kb_ask_core 注入）提问，与 /api/kb/ask 视图
完全同一条链路：意图路由（知识/闲聊/超范围）→ WeKnora 引擎/旧链路回退。
本模块不 import app，依赖一律走 runtime 注入。
"""
from .base import AgentBase, make_result
from .registry import register
from . import runtime


@register
class KbAssistantAgent(AgentBase):
    id = "kb-assistant"
    name = "知识管家"
    role = "知识库问答智能体"
    emoji = "📚"
    color = "cyan"
    desc = ("基于本站知识库的制造业数字化问答：AI 落地场景、系统操作、行业认知等问题即问即答，"
            "回答附知识库引用，引用不足时明确说明、不编造。")
    caps = [
        "制造业数字化知识即问即答",
        "回答附知识库引用与出处",
        "引用不足时明确说不知道，不编造",
    ]
    status = "live"
    endpoint = "/api/agents/kb-assistant/run"
    triggers = ["知识库", "问答", "咨询", "查询", "是什么", "怎么查", "科普", "介绍一下", "了解"]
    ui = "qa"

    def available(self):
        return runtime.kb_ask is not None

    def run(self, payload):
        p = payload or {}
        res = runtime.kb_ask(
            p.get("question"),
            history=p.get("history"),
            retrieval=p.get("retrieval"),
        )
        refs = res.get("sources") or []
        # 有引用 → 答案有据可依给中高置信；零引用（引擎拒绝式回答）→ 低置信
        confidence = 0.7 if refs else 0.2
        return make_result(
            self, res,
            refs=refs,
            confidence=confidence,
            intent=res.get("intent"),
            engine=res.get("engine") or res.get("retrieval"),
        )
