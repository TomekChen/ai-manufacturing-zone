# -*- coding: utf-8 -*-
"""平台智能体基类与统一结果契约（A2 编排层）。

统一接口：任务入 → 结构化结果 + 引用 + 置信度出。
run(payload) 必须返回 make_result 产出的 dict；抛 ValueError 视为用户输入错误(400)，
RuntimeError/Exception 由端点收敛为 502/500。
"""


class AgentBase:
    """垂直智能体基类：子类填元数据类属性，实现 run(payload)。"""

    id = ""
    name = ""
    role = ""
    emoji = "🤖"
    color = "blue"
    desc = ""
    caps = []
    status = "coming_soon"   # live=可体验（首页渲染"立即体验"入口）；coming_soon=仅注册未上线
    endpoint = ""            # 公开运行端点，前端卡片据此发起调用
    triggers = []            # planner 关键词（不区分大小写），dispatch 按它路由

    def meta(self):
        """注册表对外元数据（公开 API / 首页卡片用的就是它）。"""
        return {
            "id": self.id, "name": self.name, "role": self.role,
            "emoji": self.emoji, "color": self.color, "desc": self.desc,
            "caps": list(self.caps), "status": self.status,
            "endpoint": self.endpoint, "triggers": list(self.triggers),
        }

    def available(self):
        """智能体当前是否可运行（如依赖的 API key 是否配置）。端点据此返回 503。"""
        return True

    def run(self, payload):
        """payload 为已解析 JSON dict。子类实现，返回 make_result 形状。"""
        raise NotImplementedError


def make_result(agent, result, refs=None, confidence=None, **extra):
    """统一结果包装：结构化结果 + 引用 + 置信度。extra 可带 mode/model 等元数据。"""
    out = {
        "ok": True,
        "agent_id": agent.id,
        "result": result,
        "refs": refs or [],
        "confidence": confidence,
    }
    out.update(extra)
    return out
