# -*- coding: utf-8 -*-
"""rag/ 包纯逻辑单元测试（离线、不碰网络/LLM/FAISS）。

覆盖 Slice 1 的可插拔地基 seam：
  S1 fusion.reciprocal_rank_fusion  —— 期望值手工算，独立于实现
  S2 chunkers fixed / semantic      —— 断言块数、边界、重叠、超长段回落

运行：py test_rag_unit.py     （或 pytest）
期望值来源：RRF 公式 1/(k+rank) 手算 + 固定窗口滑动手工推演。
"""
import os
import sys

# 把项目根（tests/ 的上一级）加入 sys.path，使 `import rag` 可用
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from rag.fusion import reciprocal_rank_fusion
from rag.chunkers import build_chunker, CHUNKERS


# ── S1：RRF 融合 ────────────────────────────────────────────────────────────

def test_rrf_two_way_order():
    # vec: a b c   bm25: b c a   （k=60）
    # rrf(a)=1/61+1/63=0.032266  rrf(b)=1/62+1/61=0.032522  rrf(c)=1/63+1/62=0.032002
    # 手算结论：b > a > c
    out = reciprocal_rank_fusion([["a", "b", "c"], ["b", "c", "a"]], k=60)
    ids = [item["id"] for item in out]
    assert ids == ["b", "a", "c"], ids

    scores = {item["id"]: item["score"] for item in out}
    assert abs(scores["a"] - (1/61 + 1/63)) < 1e-9
    assert abs(scores["b"] - (1/62 + 1/61)) < 1e-9
    assert abs(scores["c"] - (1/63 + 1/62)) < 1e-9


def test_rrf_single_list_no_dupes():
    out = reciprocal_rank_fusion([["x", "y", "z"]], k=60)
    ids = [item["id"] for item in out]
    assert ids == ["x", "y", "z"], ids          # 单路保持原序
    assert len(set(ids)) == 3                    # 不重复


def test_rrf_id_that_only_appears_once_counts():
    # "solo" 只在第二路 rank1 -> 1/61，应排最前
    out = reciprocal_rank_fusion([["a", "b"], ["solo", "a"]], k=60)
    # solo=1/61=0.016393  a=1/62+1/62=0.032258  b=1/63=0.015873
    ids = [item["id"] for item in out]
    assert ids == ["a", "solo", "b"], ids


# ── S2a：固定窗口分块（等价旧 split_text 行为） ───────────────────────────────

def test_fixed_empty():
    ck = build_chunker("fixed", size=100, overlap=20)
    assert ck.chunk("") == []
    assert ck.chunk("   \n  ") == []


def test_fixed_short_single():
    ck = build_chunker("fixed", size=100, overlap=20)
    assert ck.chunk("短文本") == ["短文本"]


def test_fixed_window_slide_counts():
    # "啊"*250，size=100 overlap=20，无分隔符 -> 手工推演 [0:100][80:180][160:250]
    ck = build_chunker("fixed", size=100, overlap=20)
    text = "啊" * 250
    out = ck.chunk(text)
    assert len(out) == 3, len(out)
    assert out[0] == text[0:100]
    assert out[1] == text[80:180]
    assert out[2] == text[160:250]
    assert all(len(c) <= 100 for c in out)


def test_fixed_breaks_at_sentence_end():
    # 让窗口尾部靠近句号时应回缩到句号后，块不超过 size，且覆盖完整不丢字
    sents = "。".join("句子%02d内容" % i for i in range(40)) + "。"
    ck = build_chunker("fixed", size=60, overlap=10)
    out = ck.chunk(sents)
    assert len(out) >= 2
    assert all(len(c) <= 60 for c in out)
    # 拼接去重叠后仍包含所有句子（不吞内容）
    joined = "".join(out)
    for i in range(40):
        assert ("句子%02d内容" % i) in joined, i


# ── S2b：语义（段落）分块 ───────────────────────────────────────────────────

def test_semantic_merges_short_paragraphs():
    # 三个 100 字段落，max_size=250 -> [P1,P2] 合成一块，P3 单独一块
    P1, P2, P3 = "x" * 100, "y" * 100, "z" * 100
    text = "\n\n".join([P1, P2, P3])
    ck = build_chunker("semantic", max_size=250, min_size=1, overlap=20)
    out = ck.chunk(text)
    assert len(out) == 2, [len(c) for c in out]
    assert P1 in out[0] and P2 in out[0]
    assert P3 in out[1]
    assert all(len(c) <= 250 for c in out)


def test_semantic_splits_oversized_paragraph():
    # 单段 400 字 > max_size=250，应回落固定窗口，拆成多块且每块 <=250
    text = "w" * 400
    ck = build_chunker("semantic", max_size=250, min_size=1, overlap=20)
    out = ck.chunk(text)
    assert len(out) >= 2
    assert all(len(c) <= 250 for c in out)
    assert "".join(out).count("w") >= 400        # 覆盖全部字符


def test_semantic_short_single():
    ck = build_chunker("semantic", max_size=800, min_size=100, overlap=80)
    assert ck.chunk("就一句话。") == ["就一句话。"]


# ── 注册表 ──────────────────────────────────────────────────────────────────

def test_registry_names_and_factory():
    assert set(CHUNKERS.names()) >= {"fixed", "semantic"}
    assert isinstance(build_chunker("fixed"), type(build_chunker("fixed")))
    try:
        build_chunker("不存在的策略")
        assert False, "未知策略应抛错"
    except KeyError:
        pass


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print("PASS  %s" % t.__name__)
            passed += 1
        except AssertionError as e:
            print("FAIL  %s -> %s" % (t.__name__, e))
        except Exception as e:
            print("ERROR %s -> %r" % (t.__name__, e))
    print("\n%d/%d passed" % (passed, len(tests)))
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
