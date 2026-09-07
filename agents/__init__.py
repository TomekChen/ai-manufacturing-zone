# -*- coding: utf-8 -*-
"""平台智能体包（A2 编排层）：注册表 + planner 路由 + 统一运行契约。

app.py 启动时：
    import agents                     # import 即完成注册
    agents.runtime.store = KB         # 注入知识库（WeKnora 关闭时的回退检索用）

设计边界：planner 当前是注册表上的关键词规则（triggers），不引 LangChain；
注册表是唯一事实源，首页卡片与运行端点都从这里读。
"""
from . import runtime  # noqa: F401
from .base import AgentBase, make_result  # noqa: F401
from .registry import get_agent, list_agents, register, route_task  # noqa: F401
