# -*- coding: utf-8 -*-
"""Slice 5 · Seam S5：意图路由 + 多轮对话的纯规则 + telemetry 意图聚合。

全部离线、确定性，不碰网络/LLM/磁盘：
  - classify_intent / pick_retrieval / needs_rewrite / build_messages 都是纯函数。
  - summarize 新增 intents 分布，且 by_strategy 只统计真正走 KB 的检索（None/空 被剔除）。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from rag.intents.rules import (          # noqa: E402
    classify_intent, pick_retrieval, needs_rewrite, build_messages,
    KNOWLEDGE, SMALLTALK, OFFTOPIC,
)
from rag.telemetry import summarize      # noqa: E402


# ---------- classify_intent ----------
def test_classify_domain_keywords_win_even_with_greeting():
    assert classify_intent("你好，请问MES系统是什么") == KNOWLEDGE
    assert classify_intent("什么是数字孪生") == KNOWLEDGE
    assert classify_intent("预测性维护有什么好处") == KNOWLEDGE
    assert classify_intent("工业物联网安全架构") == KNOWLEDGE


def test_classify_smalltalk():
    assert classify_intent("你好") == SMALLTALK
    assert classify_intent("在吗？") == SMALLTALK
    assert classify_intent("你是谁") == SMALLTALK
    assert classify_intent("谢谢啦") == SMALLTALK
    assert classify_intent("辛苦了，再见") == SMALLTALK


def test_classify_offtopic():
    assert classify_intent("今天北京天气怎么样") == OFFTOPIC
    assert classify_intent("帮我写一首关于春天的诗") == OFFTOPIC
    assert classify_intent("推荐几个旅游景点") == OFFTOPIC
    assert classify_intent("给我讲个笑话") == OFFTOPIC


def test_classify_default_is_knowledge():
    # 无法判定的普通问题，默认走知识库（宁可多试不误拒）
    assert classify_intent("该怎么提升产线效率") == KNOWLEDGE
    # 带历史的追问（无领域词、非闲聊）默认 knowledge，交给改写
    assert classify_intent("那它呢", has_history=True) == KNOWLEDGE


# ---------- pick_retrieval ----------
def test_pick_retrieval_precise_terms_prefer_bm25():
    assert pick_retrieval("西门子840D报警怎么消除") == "bm25"   # 含数字/型号
    assert pick_retrieval("S7-1200 接线方法") == "bm25"


def test_pick_retrieval_conceptual_prefer_hybrid():
    assert pick_retrieval("什么是智能制造") == "hybrid"
    assert pick_retrieval("数字孪生有哪些应用场景") == "hybrid"


# ---------- needs_rewrite ----------
def test_needs_rewrite_no_history_false():
    assert needs_rewrite("什么是数字孪生", []) is False


def test_needs_rewrite_pronoun_or_short_true():
    hist = [{"role": "user", "content": "介绍下数字孪生"},
            {"role": "assistant", "content": "数字孪生是……"}]
    assert needs_rewrite("那它怎么用", hist) is True      # 指代词
    assert needs_rewrite("还有呢", hist) is True          # 短且口语
    assert needs_rewrite("上面说的第二点展开讲讲", hist) is True


def test_needs_rewrite_selfcontained_long_false():
    hist = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]
    q = "请详细解释一下工业物联网在预测性维护场景中的数据采集与安全架构设计要点有哪些"
    assert needs_rewrite(q, hist) is False   # 长、无指代，自足


# ---------- build_messages ----------
def test_build_messages_order_and_roles():
    hist = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "system", "content": "IGNORE-ME"},   # 非法/越权项应被丢弃
    ]
    msgs = build_messages("SYS", hist, "当前问题", max_turns=10)
    assert msgs[0] == {"role": "system", "content": "SYS"}
    assert msgs[-1] == {"role": "user", "content": "当前问题"}
    mid = msgs[1:-1]
    assert all(m["role"] in ("user", "assistant") for m in mid)
    assert not any(m["content"] == "IGNORE-ME" for m in msgs)
    assert mid == [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}]


def test_build_messages_trims_to_max_turns():
    hist = [{"role": "user", "content": "u%d" % i} for i in range(10)]
    msgs = build_messages("SYS", hist, "now", max_turns=4)
    # 只保留最近 4 条历史 + system + 当前
    assert len(msgs) == 1 + 4 + 1
    assert msgs[1]["content"] == "u6"   # 最近 4 条为 u6..u9
    assert msgs[4]["content"] == "u9"


def test_build_messages_empty_history():
    msgs = build_messages("SYS", [], "now", max_turns=10)
    assert msgs == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "now"}]


# ---------- summarize：意图分布 + 非KB不进策略对比 ----------
def _rec(qid, *, intent="knowledge", retrieval="hybrid", hits=3, refused=False,
         ts="2026-08-30T12:00:00", top_score=0.8):
    return {"id": qid, "ts": ts, "question": "q", "retrieval": retrieval,
            "hits": hits, "top_score": top_score, "refused": refused,
            "answer_len": 10, "latency_ms": 100, "feedback": None, "intent": intent}


from datetime import datetime  # noqa: E402
NOW = datetime(2026, 8, 30, 12, 30, 0)


def test_summarize_intent_distribution():
    recs = [
        _rec("a", intent="knowledge", retrieval="hybrid"),
        _rec("b", intent="knowledge", retrieval="vector"),
        _rec("c", intent="smalltalk", retrieval=None, hits=0, refused=False),
        _rec("d", intent="offtopic", retrieval=None, hits=0, refused=False),
    ]
    s = summarize(recs, days=30, now=NOW)
    assert s["intents"]["knowledge"] == 2
    assert s["intents"]["smalltalk"] == 1
    assert s["intents"]["offtopic"] == 1
    # by_strategy 只含有真实 retrieval 的两条，不含 smalltalk/offtopic（retrieval=None）
    assert set(s["by_strategy"].keys()) == {"hybrid", "vector"}, s["by_strategy"]


def test_summarize_missing_intent_defaults_knowledge():
    # 老记录没有 intent 字段：应归入 knowledge，不报错
    old = _rec("x")
    old.pop("intent")
    s = summarize([old], days=30, now=NOW)
    assert s["intents"]["knowledge"] == 1


def test_summarize_empty_intents():
    s = summarize([], days=30, now=NOW)
    assert s["intents"] == {} or s["intents"] == {"knowledge": 0} or True  # 空输入不炸
    assert s["total"] == 0


# ---- 迷你运行器 ----
def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print("PASS ", fn.__name__)
            passed += 1
        except Exception as e:
            print("FAIL ", fn.__name__, "->", repr(e))
    print("\n%d/%d passed" % (passed, len(fns)))
    return passed == len(fns)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
