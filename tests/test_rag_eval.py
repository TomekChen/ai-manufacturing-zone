# -*- coding: utf-8 -*-
"""Slice 6 · Seam S5：离线 RAGAS-lite 评测（题集加载 + 4 指标裁判 + 汇总 + 落盘）。

全部离线、确定性：不打网络，不碰真 LLM / 真 faiss / 真磁盘 data/。
把 chat 打桩成按 metric 分支的假裁判，把 store.ask / store.search 打桩成固定命中，
就可以完整跑通 run_one_question → summarize_items → EvalStore 全链路。

运行：py test_rag_eval.py
"""
import os
import sys
import types
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# 假 faiss / 假 bs4 —— evaluate 不直接用，但同链上会 import rag.store；提前塞进去避免原生依赖
class _FakeIndex:
    def __init__(self, dim=None): self._ids = []
    def add_with_ids(self, vecs, ids): self._ids.extend(int(i) for i in ids)
    def remove_ids(self, ids):
        drop = {int(i) for i in ids}; self._ids = [x for x in self._ids if x not in drop]
    def search(self, q, k):
        k = max(int(k), 1)
        return (np.zeros((1, k), dtype="float32"), -np.ones((1, k), dtype="int64"))
    @property
    def ntotal(self): return len(self._ids)

if "faiss" not in sys.modules:
    _fa = types.ModuleType("faiss")
    _fa.IndexFlatIP = lambda dim: _FakeIndex(dim)
    _fa.IndexIDMap2 = lambda base: _FakeIndex()
    _fa.write_index = lambda idx, path: None
    _fa.read_index = lambda path: _FakeIndex()
    sys.modules["faiss"] = _fa
if "bs4" not in sys.modules:
    _bs = types.ModuleType("bs4"); _bs.BeautifulSoup = object
    sys.modules["bs4"] = _bs

import rag.store as _st  # noqa: E402
_st.embed_texts = lambda texts: np.zeros((len(texts), _st.EMBED_DIM), dtype="float32")

import rag.evaluate as ev  # noqa: E402
from rag import config     # noqa: E402


# ---------- 1) 题集加载 ----------
def test_load_questions_shape():
    qs = ev.load_questions()
    assert len(qs) == 30, "题集应为 30 题（W4 扩容：q19-q30 数字孪生新语料）"
    ids = [q["id"] for q in qs]
    assert ids == ["q%02d" % i for i in range(1, 31)], ids
    for q in qs:
        for field in ("id", "question", "reference", "category", "type"):
            assert field in q and q[field], "缺少字段 %s @ %s" % (field, q.get("id"))
        assert q["type"] in ("knowledge", "control"), q["type"]
    know = sum(1 for q in qs if q["type"] == "knowledge")
    ctl = sum(1 for q in qs if q["type"] == "control")
    assert (know, ctl) == (27, 3), (know, ctl)


def test_load_questions_missing_file(tmp=None):
    try:
        ev.load_questions(path=os.path.join(tempfile.gettempdir(), "no_such_eval_%d.json" % os.getpid()))
        raise AssertionError("missing file should raise")
    except (FileNotFoundError, RuntimeError):
        pass


# ---------- 2) 分数解析（裁判 LLM 返回文本 → 0~1 float） ----------
def test_parse_score_plain_float():
    assert ev.parse_score("0.85") == 0.85
    assert ev.parse_score("1") == 1.0
    assert ev.parse_score("0") == 0.0


def test_parse_score_with_chinese_and_context():
    # 中文场景：分数：0.62 / 1.00 —— 期望抓出 0.62
    assert abs(ev.parse_score("评分理由略。得分：0.62 / 1.00") - 0.62) < 1e-9
    # 前带说明、后有单位
    assert abs(ev.parse_score("The score is 0.75.") - 0.75) < 1e-9


def test_parse_score_clamps_out_of_range():
    assert ev.parse_score("1.8") == 1.0     # 上限夹到 1
    assert ev.parse_score("-0.3") == 0.0    # 下限夹到 0


def test_parse_score_returns_none_on_garbage():
    assert ev.parse_score("") is None
    assert ev.parse_score("完全没提分数") is None
    assert ev.parse_score(None) is None


# ---------- 3) 裁判消息组装 ----------
def test_build_judge_messages_structure():
    msgs = ev.build_judge_messages(
        "faithfulness", question="什么是智能制造", reference="基于物联网…",
        context="【资料1】白皮书\n智能制造…", answer="智能制造是…",
    )
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == ev.JUDGE_PROMPTS["faithfulness"]
    assert msgs[-1]["role"] == "user"
    user = msgs[-1]["content"]
    # 用户消息里四要素都要齐
    for token in ("什么是智能制造", "基于物联网", "白皮书", "智能制造是"):
        assert token in user, token


def test_judge_prompts_have_all_four():
    assert set(ev.JUDGE_PROMPTS.keys()) == set(config.EVAL_METRICS)


def test_metric_labels_exist():
    # 前端展示要用中文名；后端一处定义，保证四指标各自有标签
    for m in config.EVAL_METRICS:
        assert m in ev.METRIC_LABELS
        assert ev.METRIC_LABELS[m], m


# ---------- 4) judge_one：假 chat → 分数 ----------
def test_judge_one_parses_fake_llm_output():
    calls = []
    def fake_chat(messages, temperature=0.0):
        calls.append((messages[0]["content"][:12], temperature))
        return "0.83"
    old = ev.chat; ev.chat = fake_chat
    try:
        s = ev.judge_one("faithfulness", "q?", "ref", "ctx", "ans")
    finally:
        ev.chat = old
    assert abs(s - 0.83) < 1e-9
    assert calls and calls[0][1] == 0.0    # 裁判固定 temperature=0


def test_judge_one_llm_error_returns_none():
    def boom(*a, **k):
        raise RuntimeError("network down")
    old = ev.chat; ev.chat = boom
    try:
        assert ev.judge_one("answer_relevance", "q?", "ref", "ctx", "ans") is None
    finally:
        ev.chat = old


# ---------- 5) 策略快照 ----------
def test_strategy_snapshot_keys_and_defaults():
    snap = ev.strategy_snapshot()
    for k in ("chunking", "retrieval", "top_k", "embed_dim", "chunk_size", "chunk_overlap", "rrf_k", "chat_model", "judge_model", "history_max"):
        assert k in snap, k
    assert snap["chunking"] == config.DEFAULT_CHUNKING
    assert snap["retrieval"] == config.DEFAULT_RETRIEVAL
    assert snap["top_k"] == config.TOP_K
    assert snap["embed_dim"] == config.EMBED_DIM
    assert snap["judge_model"] == config.EVAL_JUDGE_MODEL


# ---------- 6) run_one_question：串起 store.ask + store.search + 四次裁判 ----------
def _fake_store(question_to_answer=None, hits=None, intent="knowledge"):
    """构造一个够用的 store 桩：ask 返回 answer+sources+intent，search 返回 hits。"""
    hits = hits if hits is not None else [{
        "score": 0.9, "text": "智能制造基于物联网、大数据与 AI…",
        "doc": {"title": "白皮书", "url": "http://x"}, "retrieval": "hybrid",
    }]
    class _S:
        def ask(self, q, history=None, retrieval=None):
            return {"answer": "ANS:" + q, "sources": [{"title": h["doc"]["title"], "url": h["doc"]["url"], "snippet": h["text"]} for h in hits],
                    "retrieval": hits[0]["retrieval"] if hits else "hybrid",
                    "intent": intent, "ask_id": "a" * 16}
        def search(self, q, top_k=5, retrieval=None):
            return list(hits)
    return _S()


def _stub_chat_scores(score_map):
    """按 metric 名（隐藏在 system 提示词里的标记 __METRIC__）返回指定分数。"""
    def _chat(messages, temperature=0.0):
        sys = messages[0]["content"]
        for m, v in score_map.items():
            if ("__%s__" % m) in sys:
                return v
        return "0.5"
    return _chat


def test_run_one_question_returns_four_metric_scores():
    # 让四段提示词各自带上 __metric__ 标记，方便桩 chat 匹配（这是 evaluate.py 的实现约定）
    old_prompts = {k: ev.JUDGE_PROMPTS[k] for k in ev.JUDGE_PROMPTS}
    try:
        for m in ev.JUDGE_PROMPTS:
            ev.JUDGE_PROMPTS[m] = ev.JUDGE_PROMPTS[m] + ("  __%s__" % m)
        ev.chat = _stub_chat_scores({
            "faithfulness": "0.9",
            "answer_relevance": "0.8",
            "context_precision": "0.7",
            "context_recall": "0.6",
        })
        item = {"id": "q01", "question": "什么是智能制造", "reference": "基于物联网…", "type": "knowledge", "category": "概念定义"}
        r = ev.run_one_question(_fake_store(), item)
    finally:
        ev.JUDGE_PROMPTS = old_prompts
        # 恢复 chat（下一个测试会自己打桩）
        if hasattr(ev, "_chat_default"):
            ev.chat = ev._chat_default
    assert r["id"] == "q01"
    assert r["type"] == "knowledge"
    assert r["scores"]["faithfulness"] == 0.9
    assert r["scores"]["answer_relevance"] == 0.8
    assert r["scores"]["context_precision"] == 0.7
    assert r["scores"]["context_recall"] == 0.6
    assert r["intent"] == "knowledge"
    assert r["hits_count"] == 1


def test_run_one_question_no_hits_context_empty_still_scores():
    # 无检索命中时也要跑完四段裁判（context=""），不能崩；意图 = offtopic 时 store.ask 返回固定引导话术
    store = _fake_store(hits=[], intent="offtopic")
    old_prompts = {k: ev.JUDGE_PROMPTS[k] for k in ev.JUDGE_PROMPTS}
    try:
        for m in ev.JUDGE_PROMPTS:
            ev.JUDGE_PROMPTS[m] = ev.JUDGE_PROMPTS[m] + ("  __%s__" % m)
        ev.chat = _stub_chat_scores({
            "faithfulness": "0.2", "answer_relevance": "0.3",
            "context_precision": "0.0", "context_recall": "0.0",
        })
        item = {"id": "q06", "question": "明天上海天气", "reference": "不该回答", "type": "control", "category": "对照"}
        r = ev.run_one_question(store, item)
    finally:
        ev.JUDGE_PROMPTS = old_prompts
    assert r["hits_count"] == 0
    assert r["intent"] == "offtopic"
    assert r["scores"]["context_recall"] == 0.0
    assert r["scores"]["faithfulness"] == 0.2


# ---------- 7) 聚合：主指标只算 knowledge，control 单列 ----------
def test_summarize_items_overall_excludes_control():
    items = [
        {"id": "q01", "type": "knowledge", "scores": {"faithfulness": 0.8, "answer_relevance": 0.9, "context_precision": 0.7, "context_recall": 0.6}},
        {"id": "q02", "type": "knowledge", "scores": {"faithfulness": 0.6, "answer_relevance": 0.7, "context_precision": 0.5, "context_recall": 0.4}},
        {"id": "q06", "type": "control", "scores": {"faithfulness": 0.1, "answer_relevance": 0.1, "context_precision": 0.0, "context_recall": 0.0}},
    ]
    s = ev.summarize_items(items)
    assert s["counts"]["total"] == 3
    assert s["counts"]["knowledge"] == 2
    assert s["counts"]["control"] == 1
    # overall = knowledge 平均：faithfulness (0.8+0.6)/2=0.7
    assert abs(s["overall"]["faithfulness"] - 0.7) < 1e-9
    assert abs(s["overall"]["context_recall"] - 0.5) < 1e-9
    # by_type.control 也要能看到（用于敏感度自检）
    assert s["by_type"]["control"]["faithfulness"] == 0.1
    assert s["by_type"]["knowledge"]["answer_relevance"] == 0.8


def test_summarize_items_tolerates_none_scores():
    # 某题某指标 None（LLM 失败），跳过不计入均值，不炸
    items = [
        {"id": "q01", "type": "knowledge", "scores": {"faithfulness": 0.8, "answer_relevance": None, "context_precision": 0.6, "context_recall": 0.7}},
        {"id": "q02", "type": "knowledge", "scores": {"faithfulness": 0.4, "answer_relevance": 0.5, "context_precision": None, "context_recall": 0.3}},
    ]
    s = ev.summarize_items(items)
    assert abs(s["overall"]["faithfulness"] - 0.6) < 1e-9
    assert s["overall"]["answer_relevance"] == 0.5      # 只有一个非 None
    assert s["overall"]["context_precision"] == 0.6
    assert s["counts"]["skipped"]["answer_relevance"] == 1
    assert s["counts"]["skipped"]["context_precision"] == 1


def test_summarize_items_empty():
    s = ev.summarize_items([])
    assert s["counts"]["total"] == 0
    # 空集合不炸，overall 每项都是 None
    for m in config.EVAL_METRICS:
        assert s["overall"][m] is None


# ---------- 8) EvalStore 落盘 + 滚动上限 ----------
def test_eval_store_append_and_cap():
    tmp = tempfile.mkdtemp()
    es = ev.EvalStore(tmp, max_results=3)
    for i in range(5):
        es.append({"tag": "run%d" % i, "overall": {"faithfulness": 0.5}})
    hist = es.load()
    assert len(hist) == 3, "超上限要丢最旧"
    assert [h["tag"] for h in hist] == ["run2", "run3", "run4"], [h["tag"] for h in hist]


def test_eval_store_appends_id_and_ts():
    tmp = tempfile.mkdtemp()
    es = ev.EvalStore(tmp, max_results=10)
    rec = es.append({"overall": {}, "items": []})
    assert rec.get("id"), "append 要生成 id"
    assert rec.get("ts"), "append 要写时间戳"


def test_eval_store_latest():
    tmp = tempfile.mkdtemp()
    es = ev.EvalStore(tmp, max_results=5)
    es.append({"tag": "a"})
    es.append({"tag": "b"})
    assert es.latest()["tag"] == "b"


# ---------- 9) API Key 检查 + 并发锁 ----------
def test_has_api_key_env_driven(monkey=None):
    saved = os.environ.get("DASHSCOPE_API_KEY")
    try:
        os.environ.pop("DASHSCOPE_API_KEY", None)
        assert ev.has_api_key() is False
        os.environ["DASHSCOPE_API_KEY"] = "sk-test"
        assert ev.has_api_key() is True
    finally:
        os.environ.pop("DASHSCOPE_API_KEY", None)
        if saved: os.environ["DASHSCOPE_API_KEY"] = saved


def test_start_refuses_without_api_key():
    ev.reset_state()
    saved = os.environ.get("DASHSCOPE_API_KEY")
    try:
        os.environ.pop("DASHSCOPE_API_KEY", None)
        try:
            ev.start(_fake_store(), tempfile.mkdtemp())
            raise AssertionError("should raise without API key")
        except RuntimeError as e:
            assert "DASHSCOPE_API_KEY" in str(e) or "未配置" in str(e)
        assert ev.get_state()["running"] is False
    finally:
        if saved: os.environ["DASHSCOPE_API_KEY"] = saved


def test_start_refuses_if_already_running():
    ev.reset_state()
    saved = os.environ.get("DASHSCOPE_API_KEY")
    try:
        os.environ["DASHSCOPE_API_KEY"] = "sk-test"
        ev._STATE["running"] = True
        try:
            ev.start(_fake_store(), tempfile.mkdtemp())
            raise AssertionError("should refuse when already running")
        except RuntimeError as e:
            assert "正在" in str(e) or "running" in str(e).lower()
    finally:
        ev._STATE["running"] = False
        os.environ.pop("DASHSCOPE_API_KEY", None)
        if saved: os.environ["DASHSCOPE_API_KEY"] = saved


def test_get_state_shape():
    ev.reset_state()
    st = ev.get_state()
    for k in ("running", "current", "total", "current_qid", "error"):
        assert k in st, k
    assert st["running"] is False
    assert st["current"] == 0


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
