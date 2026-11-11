# -*- coding: utf-8 -*-
"""场景分镜师（第五个上线智能体，scroll-world 的集成形态）：
品牌/行业输入 → 滚动漫游动画的分镜脚本。

场景：首页顶部的「制造世界」滚动漫游动画需要 4-8 个首尾衔接的场景；
人工写分镜要同时懂行业、美术方向和镜头衔接。本智能体把品牌/行业一句话
扩写成完整分镜脚本（场景顺序 + 每场景内容 + 静帧绘制提示词 + 镜头衔接），
产出的提示词直接喂文生图流水线（DashScope Wanx，服务器侧脚本生成静帧）。
LLM 输出强制 JSON，解析失败收敛 RuntimeError（端点层 502）；入参校验失败
抛 ValueError（端点层 400）。
"""
import json

from rag import prd as kb_prd
from rag.llm import chat

from .base import AgentBase, make_result
from .registry import register

_SYSTEM = """你是制造企业的滚动漫游动画分镜师。用户给出品牌名/行业/想展示的内容，产出一条「镜头从厂区外部飞入各部门内部、场景间无切剪」的滚动分镜脚本，只输出一个 JSON 对象，不要输出任何其他文字：
{
  "brand": "品牌/主题名，无法判断则空字符串",
  "style": "整体美术方向，一句话（配色/视角/光照基调）",
  "scenes": [
    {"no": "01", "title": "场景标题（4-10字）", "desc": "场景内容一句话（给观众看的说明）",
     "still_prompt": "该场景的等距立体静帧绘制提示词：具体到建筑/设备/人物/大屏内容，与整体风格锚定一致，画面主体明确",
     "camera_move": "镜头如何从上一个场景飞入本场景（无切剪衔接，一句话；第一个场景写从外部高空俯冲进场）"}
  ]
}
要求：scenes 4-8 个，按镜头飞行的叙事顺序排列（外部全貌 → 逐部门内部 → 收尾）；still_prompt 各场景风格必须互相锚定（同一配色/视角/光照），否则画面跳戏；desc 面向观众，still_prompt 面向绘图模型，不要混写。"""


@register
class SceneDirectorAgent(AgentBase):
    id = "scene-director"
    name = "场景分镜师"
    role = "滚动漫游动画分镜智能体"
    emoji = "🎬"
    color = "purple"
    desc = ("给出品牌名和想展示的行业内容，自动扩写成 4-8 个首尾衔接的滚动漫游分镜脚本"
            "（场景顺序/内容/静帧绘制提示词/镜头衔接），提示词直接可喂文生图流水线。")
    caps = [
        "品牌/行业一句话扩写完整分镜脚本",
        "场景间无切剪的镜头衔接设计",
        "每场景附可绘图的等距静帧提示词",
    ]
    status = "live"
    endpoint = "/api/agents/scene-director/run"
    triggers = ["分镜", "漫游", "场景动画", "分镜脚本", "镜头脚本"]
    ui = "scenes"

    def available(self):
        return kb_prd.has_api_key()

    def _messages(self, text):
        return [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ]

    def _parse(self, raw):
        s = (raw or "").strip()
        if s.startswith("```"):
            s = s.strip("`").lstrip("json").strip()
        start, end = s.find("{"), s.rfind("}")
        if start == -1 or end <= start:
            raise RuntimeError("分镜失败：模型未返回结构化结果，请重试")
        try:
            out = json.loads(s[start:end + 1])
        except ValueError:
            raise RuntimeError("分镜失败：结果解析出错，请重试")
        if not isinstance(out, dict):
            raise RuntimeError("分镜失败：结果形状异常，请重试")
        scenes = out.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            raise RuntimeError("分镜失败：模型未产出任何场景，请重试")
        if len(scenes) > 8:
            scenes = scenes[:8]
        out["scenes"] = [s for s in scenes if isinstance(s, dict)]
        return out

    def run(self, payload):
        p = payload or {}
        text = (p.get("text") or p.get("brand") or p.get("question") or "").strip()
        if not text:
            raise ValueError("请给出品牌名/行业和想展示的内容")
        if len(text) > 2000:
            text = text[:2000]
        try:
            raw = chat(self._messages(text), temperature=0.4)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError("分镜失败：%s" % str(e)[:120])
        out = self._parse(raw)
        n = len(out["scenes"])
        confidence = 0.8 if 4 <= n <= 8 else 0.5
        return make_result(self, out, confidence=confidence)
