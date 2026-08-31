# -*- coding: utf-8 -*-
"""PRD 生成器（对齐老板新方向：AI 智能体平台转型售前工具）。

一句话：填「公司 + 业务介绍」→ 产出一份面向该客户的《AI 智能体平台功能需求 PRD》。

两种模式（老板在需求里明确要的）：
  - guide（引导）：客户不懂要什么 -> 先给一版完整方案草稿 + 末尾列"待客户澄清的问题"。
  - normalize（规范化）：客户已给原始需求 -> 整理成规范 PRD，补缺口、标歧义。

行业接地：生成前先用知识库检索相关片段注入为"行业参考与案例"，呼应"做智能制造
know-how 专家"。知识库为空或检索异常时自动降级为不接地，不影响生成。

Seam（可测边界）：has_api_key / clean_input / build_system_prompt / format_kb_context /
build_user_prompt / build_prd_messages / generate_prd —— 全可离线打桩（假 chat + 假 store），
见 tests/test_prd.py。
"""
import os

from . import config
from .llm import chat  # 单测会 monkeypatch 本模块的 chat 名字


def has_api_key():
    return bool((os.environ.get("DASHSCOPE_API_KEY", "") or "").strip())


# ---------- 输入清洗 ----------

def clean_input(payload):
    """归一化 + 校验入参。非法抛 ValueError（端点映射 400）。"""
    payload = payload or {}
    company = (payload.get("company") or "").strip()
    if not company:
        raise ValueError("请填写公司名称")
    company = company[:config.PRD_COMPANY_MAX]

    industry = (payload.get("industry") or "").strip()[:config.PRD_INDUSTRY_MAX]

    business = (payload.get("business") or "").strip()
    if len(business) < config.PRD_BIZ_MIN:
        raise ValueError("业务介绍太短，请至少写几个字描述客户是做什么的")
    business = business[:config.PRD_BIZ_MAX]

    mode = (payload.get("mode") or "").strip()
    if mode not in ("guide", "normalize"):
        mode = "guide"

    raw = (payload.get("raw_requirements") or "").strip()[:config.PRD_RAW_MAX]
    if mode == "normalize" and not raw:
        raise ValueError("规范化模式需要粘贴客户的原始需求")

    return {
        "company": company,
        "industry": industry,
        "business": business,
        "mode": mode,
        "raw_requirements": raw,
    }


# ---------- 提示词 ----------

_ROLE = (
    "你是一名资深的智能制造行业数字化转型顾问，同时精通企业级 AI 智能体（Agent）平台的"
    "产品设计与售前方案撰写。你的任务是根据客户信息，产出一份专业、可落地、结构清晰的"
    "《AI 智能体平台功能需求 PRD》。输出使用规范的中文 Markdown。"
)

_TEMPLATE = (
    "请严格按以下章节结构输出（用 Markdown 标题层级，缺信息处合理推断并标注『（待确认）』）：\n"
    "1. 文档信息（客户名称、行业、生成模式、日期，并注明『本 PRD 由 AI 生成，需人工复核』）\n"
    "2. 客户与业务背景\n"
    "3. AI 智能体平台转型目标（以业务价值/降本增效为导向）\n"
    "4. 目标用户与角色\n"
    "5. 核心智能体（Agent）功能需求清单（用表格：智能体名称 / 应用场景 / 输入 / 输出 / 业务价值）\n"
    "6. 平台功能需求（知识库、对话与多轮、工作流编排、与 ERP/MES/PLM 等系统集成、权限与安全、运营看板等）\n"
    "7. 非功能需求（性能、安全合规、可用性、可维护性）\n"
    "8. 技术架构建议\n"
    "9. 实施路线图（分期：PoC 验证 → MVP 上线 → 规模推广）\n"
    "10. 行业参考与案例（若提供了参考资料，请引用并标注来源）\n"
    "11. 待客户确认的问题清单\n"
)

_GUIDE_NOTE = (
    "当前是【引导模式】：客户尚不清楚自己需要什么。你要主动替他设想智能制造场景下最"
    "有价值的智能体组合，给出一版完整方案草稿，并在第 11 节列出用于引导客户进一步澄清的"
    "关键问题（例如现有系统、数据现状、优先痛点、预算与周期等）。"
)

_NORMALIZE_NOTE = (
    "当前是【规范化模式】：客户已经给了一些原始需求（见下方『客户原始需求』）。你要把这些"
    "零散诉求梳理、去重、补齐成规范的 PRD，识别其中的缺口与歧义，并在第 11 节列出需要与客户"
    "进一步确认的点。不要遗漏客户明确提出的诉求。"
)


def build_system_prompt(mode):
    parts = [_ROLE, _TEMPLATE]
    parts.append(_NORMALIZE_NOTE if mode == "normalize" else _GUIDE_NOTE)
    return "\n\n".join(parts)


def format_kb_context(hits):
    """把知识库命中片段拼成『行业参考』上下文。空命中返回空串。"""
    if not hits:
        return ""
    lines = []
    for i, h in enumerate(hits, 1):
        doc = h.get("doc") or {}
        title = (doc.get("title") or "").strip() or "未命名资料"
        text = (h.get("text") or "").strip()
        if not text:
            continue
        lines.append("【资料%d】%s\n%s" % (i, title, text[:600]))
    return "\n\n".join(lines)


def build_user_prompt(company, industry, business, mode, raw_requirements, context):
    seg = [
        "【客户名称】%s" % company,
        "【所属行业】%s" % (industry or "（未提供，请从业务描述推断）"),
        "【业务介绍】%s" % business,
    ]
    if mode == "normalize" and raw_requirements:
        seg.append("【客户原始需求】\n%s" % raw_requirements)
    if context:
        seg.append("【行业参考资料（来自知识库，请在第 10 节引用并标注来源）】\n%s" % context)
    seg.append("请据此生成完整的 PRD。")
    return "\n\n".join(seg)


def build_prd_messages(company, industry, business, mode, raw_requirements, context):
    return [
        {"role": "system", "content": build_system_prompt(mode)},
        {"role": "user", "content": build_user_prompt(
            company, industry, business, mode, raw_requirements, context)},
    ]


# ---------- 主流程 ----------

def _extract_sources(hits):
    out = []
    for h in hits or []:
        doc = h.get("doc") or {}
        title = (doc.get("title") or "").strip()
        url = (doc.get("url") or "").strip()
        if title or url:
            out.append({"title": title or "未命名资料", "url": url})
    return out


def generate_prd(store, payload):
    """校验 -> 知识库接地检索(容错) -> 组提示词 -> 调 LLM -> 返回契约结构。

    chat 异常向上抛（端点映射 502）；store.search 异常吞掉降级为不接地。
    """
    data = clean_input(payload)

    hits = []
    if store is not None:
        query = " ".join(x for x in (data["company"], data["industry"], data["business"][:120]) if x)
        try:
            hits = store.search(query, top_k=config.PRD_TOP_K) or []
        except Exception:
            hits = []

    context = format_kb_context(hits)
    messages = build_prd_messages(
        company=data["company"], industry=data["industry"], business=data["business"],
        mode=data["mode"], raw_requirements=data["raw_requirements"], context=context,
    )
    prd_text = chat(messages, temperature=config.PRD_TEMPERATURE, timeout=config.PRD_TIMEOUT)

    return {
        "prd": (prd_text or "").strip(),
        "mode": data["mode"],
        "grounded": bool(context),
        "hits": len(hits),
        "sources": _extract_sources(hits),
        "model": config.PRD_MODEL,
    }
