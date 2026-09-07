# -*- coding: utf-8 -*-
"""智能体注册表（A2）：每上线一个垂直智能体，import 即注册，全站自动可发现。

- GET /api/agents           ← list_agents(only_live=True) 驱动首页"已上线"卡片
- POST /api/agents/<id>/run ← get_agent(id).run(payload)
- POST /api/agents/dispatch ← route_task(task) 按 triggers 关键词路由（planner）
注册表是唯一事实源：app.py 不再硬编码卡片，A1 的硬编码列表已迁移至此。
"""

_AGENTS = []


def register(cls):
    """类装饰器：实例化并登记。id 为空/纯空白或重复直接抛错（上线期就该发现）。"""
    inst = cls()
    inst.id = (inst.id or "").strip()
    if not inst.id:
        raise ValueError("agent id 不能为空: %s" % cls.__name__)
    if any(a.id == inst.id for a in _AGENTS):
        raise ValueError("agent id 重复: %s" % inst.id)
    _AGENTS.append(inst)
    return cls


def get_agent(agent_id):
    for a in _AGENTS:
        if a.id == agent_id:
            return a
    return None


def list_agents(only_live=True):
    """注册表快照；only_live=True 只返回可体验的（首页入口用）。"""
    ags = [a.meta() for a in _AGENTS]
    if only_live:
        ags = [m for m in ags if m["status"] == "live"]
    return ags


def route_task(task):
    """planner：任务文本按 triggers 关键词命中第一个 live 智能体，无匹配返回 None。"""
    t = (task or "").lower()
    if not t:
        return None
    for a in _AGENTS:
        if a.status != "live":
            continue
        for kw in a.triggers:
            if kw and kw.lower() in t:
                return a
    return None


# 智能体实现（import 即注册；新智能体在此追加一行）
from . import prd_advisor  # noqa: E402,F401
