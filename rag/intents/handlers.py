# -*- coding: utf-8 -*-
"""三种意图处理策略（Slice 5）：knowledge / smalltalk / offtopic。

- knowledge：走知识库——多轮时先按需「上下文改写」把追问补全成自足问题，再检索、拼上下文、LLM 生成。
  无历史时消息组装与旧版单轮完全一致（零回归）。
- smalltalk：寒暄/致谢——不调检索，直接用轻量人设 LLM 友好回应（LLM 不可用时降级为固定话术）。
- offtopic：明显超出行业范围——礼貌拒答并引导，不调 LLM（零 token）。
"""
from .. import config
from ..llm import chat
from .base import IntentHandler, INTENTS
from .rules import build_messages, needs_rewrite, pick_retrieval, KNOWLEDGE, SMALLTALK, OFFTOPIC

# 知识问答：与旧 store.ask 完全相同的系统人设，保证单轮零回归
KB_SYSTEM = (
    "你是「智能制造专区」的知识库助手。请仅根据用户提供的参考资料回答问题，"
    "用简体中文，条理清晰。参考资料中没有的内容不要编造；若资料不足以回答，"
    "请直接说明知识库暂无相关内容。回答末尾不要输出与回答无关的客套话。"
)
NO_CONTENT = (
    "知识库中暂无与该问题相关的内容。管理员可在后台上传资料或从友情链接采集行业信息后再次提问。"
)
SMALLTALK_SYSTEM = (
    "你是「智能制造专区」的智能助手。面对访客的问候或闲聊，请用简体中文友好、简洁地回应，"
    "可自然地把话题引导到智能制造、工业自动化、数字化转型等知识问答上。不要编造具体数据。"
)
SMALLTALK_FALLBACK = (
    "你好！我是智能制造专区助手，可以回答智能制造、工业自动化、数字化转型等相关问题，欢迎随时提问。"
)
OFFTOPIC_ANSWER = (
    "抱歉，这个问题超出了「智能制造专区」知识库的服务范围。我主要解答智能制造、工业自动化、"
    "数字化转型等行业的知识问题，你可以换个相关问题问我；也欢迎上传相关资料或从友情链接采集行业信息。"
)

REWRITE_SYSTEM = (
    "你是查询改写助手。请结合下面的对话历史，把用户最新的追问补全/改写成一个不依赖上下文、"
    "可独立检索的简体中文问题。只输出改写后的问题本身，不要解释、不要引号、不要多余换行。"
    "若无需改写，则原样输出该问题。"
)


def _rewrite_query(question, history):
    """用 LLM 把追问改写成自足检索问题；失败（含无 API Key）时返回 None，交调用方回退原问题。"""
    try:
        msgs = build_messages(REWRITE_SYSTEM, history, question, max_turns=6)
        out = (chat(msgs, temperature=0.0) or "").strip()
        out = out.strip('“”"').strip()
        return out or None
    except Exception:
        return None


def _dedup_sources(hits):
    seen, sources = set(), []
    for h in hits:
        doc = h["doc"]
        key = doc.get("url") or doc.get("title")
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "title": doc.get("title", ""),
            "url": doc.get("url", ""),
            "snippet": h["text"][:160],
        })
    return sources


@INTENTS.register(KNOWLEDGE)
class KnowledgeHandler(IntentHandler):
    def answer(self, store, question, history, retrieval=None):
        rewritten, did_rw = question, False
        if needs_rewrite(question, history):
            r = _rewrite_query(question, history)
            if r:
                rewritten, did_rw = r, True
        q_search = rewritten or question
        name = retrieval or pick_retrieval(q_search)
        hits = store.search(q_search, retrieval=name)
        used = hits[0]["retrieval"] if hits else (name or config.DEFAULT_RETRIEVAL)
        top_score = round(hits[0]["score"], 4) if hits else None
        if not hits:
            return {"answer": NO_CONTENT, "sources": [], "retrieval": used,
                    "hits": 0, "top_score": None, "refused": True, "rewritten": did_rw}
        ctx = "\n\n".join(
            "【资料%d】%s\n%s" % (i + 1, h["doc"].get("title", ""), h["text"])
            for i, h in enumerate(hits)
        )
        user_msg = "参考资料：\n" + ctx + "\n\n问题：" + (q_search or "").strip()
        messages = build_messages(KB_SYSTEM, history, user_msg, max_turns=config.HISTORY_MAX)
        answer = chat(messages)
        return {"answer": answer, "sources": _dedup_sources(hits), "retrieval": used,
                "hits": len(hits), "top_score": top_score, "refused": False, "rewritten": did_rw}


@INTENTS.register(SMALLTALK)
class SmalltalkHandler(IntentHandler):
    def answer(self, store, question, history, retrieval=None):
        messages = build_messages(SMALLTALK_SYSTEM, history, question, max_turns=config.HISTORY_MAX)
        try:
            answer = chat(messages, temperature=0.6)
        except Exception:
            answer = SMALLTALK_FALLBACK
        return {"answer": answer, "sources": [], "retrieval": None,
                "hits": 0, "top_score": None, "refused": False, "rewritten": False}


@INTENTS.register(OFFTOPIC)
class OfftopicHandler(IntentHandler):
    def answer(self, store, question, history, retrieval=None):
        return {"answer": OFFTOPIC_ANSWER, "sources": [], "retrieval": None,
                "hits": 0, "top_score": None, "refused": False, "rewritten": False}
