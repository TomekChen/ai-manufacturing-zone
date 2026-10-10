# -*- coding: utf-8 -*-
"""订单机器人（A7 第三个上线智能体）：订单原文 → 结构化工单抽取。

场景：客户订单散落在邮件/客户网页系统里靠人工抓取，易漏单、录入错。
把粘贴进来的订单原文（邮件正文/网页询盘/聊天记录均可）抽成结构化工单，
缺失字段明确提示，漏单风险前置。LLM 输出强制 JSON，解析失败收敛为
RuntimeError（端点层 502）；入参校验失败抛 ValueError（端点层 400）。
"""
import json

from rag import prd as kb_prd  # has_api_key 与售前方案师同一来源
from rag.llm import chat  # 单测 monkeypatch 本模块的 chat 名字

from .base import AgentBase, make_result
from .registry import register

_SYSTEM = """你是制造企业的订单录入助手。从用户粘贴的订单原文（可能是邮件、网页询盘、聊天记录）中抽取结构化工单，只输出一个 JSON 对象，不要输出任何其他文字：
{
  "order_no": "订单号，原文没有则空字符串",
  "customer": "客户名称，无法判断则空字符串",
  "contact": "联系人及联系方式（电话/邮箱/微信），原文没有则空字符串",
  "products": [{"name": "品名", "spec": "规格型号，没有则空字符串", "qty": "数量", "unit": "单位（件/套/PCS等），没有则空字符串"}],
  "delivery_date": "交货日期，原文有年份则标准化为 YYYY-MM-DD；原文没写年份就保留原文写法（如"12月20日"），不要猜测年份；没有则空字符串",
  "notes": "其他重要备注（特殊要求/包装/运输方式等），没有则空字符串",
  "missing": ["缺失或无法确定的关键字段名列表，如 customer、delivery_date"]
}
要求：产品可能多个，全部列入 products；数量保留原文写法（如"5000PCS"可写 qty="5000" unit="PCS"）；不要编造原文没有的信息。"""


@register
class OrderCatcherAgent(AgentBase):
    id = "order-catcher"
    name = "订单机器人"
    role = "订单信息抽取智能体"
    emoji = "📨"
    color = "green"
    desc = ("把客户邮件、网页询盘、聊天记录里的订单原文粘贴进来，自动抽取成结构化工单"
            "（客户/品名/数量/交期/联系方式），缺失字段明确提示，防漏单防录错。")
    caps = [
        "邮件/网页/聊天记录订单原文抽取",
        "结构化工单：客户/品名/数量/交期/联系方式",
        "缺失字段提示，漏单风险前置",
    ]
    status = "live"
    endpoint = "/api/agents/order-catcher/run"
    triggers = ["订单", "抓单", "询盘", "下单", "漏单"]
    ui = "order"

    def available(self):
        return kb_prd.has_api_key()

    def _messages(self, text):
        return [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ]

    def _parse(self, raw):
        """LLM 返回强制 JSON；剥掉可能的 ```json 围栏后解析，失败收敛 502。"""
        s = (raw or "").strip()
        if s.startswith("```"):
            s = s.strip("`").lstrip("json").strip()
        start, end = s.find("{"), s.rfind("}")
        if start == -1 or end <= start:
            raise RuntimeError("抽取失败：模型未返回结构化结果，请重试")
        try:
            order = json.loads(s[start:end + 1])
        except ValueError:
            raise RuntimeError("抽取失败：结果解析出错，请重试")
        if not isinstance(order, dict):
            raise RuntimeError("抽取失败：结果形状异常，请重试")
        if not isinstance(order.get("products"), list):
            order["products"] = []
        if not isinstance(order.get("missing"), list):
            order["missing"] = []
        return order

    def run(self, payload):
        p = payload or {}
        text = (p.get("text") or p.get("question") or "").strip()
        if not text:
            raise ValueError("请粘贴订单原文（邮件正文/网页询盘/聊天记录均可）")
        if len(text) > 12000:
            text = text[:12000]
        try:
            raw = chat(self._messages(text), temperature=0.1)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError("抽取失败：%s" % str(e)[:120])
        order = self._parse(raw)
        missing = order.get("missing") or []
        if order.get("customer") and order.get("products"):
            confidence = 0.8 if not missing else 0.6
        else:
            confidence = 0.3
        return make_result(self, order, confidence=confidence)
