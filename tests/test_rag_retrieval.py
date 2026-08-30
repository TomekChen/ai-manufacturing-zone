# -*- coding: utf-8 -*-
"""Slice 2：检索层（BM25 + 混合 RRF）单元测试。

只测纯逻辑，不碰网络/FAISS：
  S3 bm25：给定小语料 + 查询 -> 断言命中排序（期望值来自人工判断，独立于实现）
  S3b hybrid：注入"假向量/假bm25"排名 -> 断言 RRF 融合顺序（1/(k+rank) 手算）

运行：py test_rag_retrieval.py
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from rag.retrievers.bm25 import BM25Retriever
from rag.retrievers.hybrid import HybridRetriever
from rag.retrievers import build_retriever, RETRIEVERS


CORPUS = {
    "1": "贵州茅台2023年营业收入1476亿元，同比增长15%",
    "2": "宁德时代2021年研发费用占营业收入比例较高",
    "3": "五粮液2022年毛利率与净利率对比分析",
    "4": "今天天气晴朗适合外出春游踏青活动",
}


# ── S3：BM25 ────────────────────────────────────────────────────────────────

def test_bm25_hits_expected_doc():
    r = BM25Retriever(CORPUS)
    top = r.search("茅台 营业收入", top_k=2)
    assert top, "应有命中"
    assert top[0]["id"] == "1", [t["id"] for t in top]   # 茅台营收 -> 文档1


def test_bm25_rnd_expense():
    r = BM25Retriever(CORPUS)
    top = r.search("研发费用", top_k=3)
    assert top[0]["id"] == "2", [t["id"] for t in top]


def test_bm25_scores_descending():
    r = BM25Retriever(CORPUS)
    top = r.search("营业收入", top_k=4)
    scores = [t["score"] for t in top]
    assert scores == sorted(scores, reverse=True), scores


def test_bm25_no_match_returns_empty():
    r = BM25Retriever(CORPUS)
    assert r.search("火星恐龙灭绝", top_k=5) == []        # 语料里没有这些词


def test_bm25_respects_top_k():
    r = BM25Retriever(CORPUS)
    assert len(r.search("年", top_k=1)) <= 1


# ── S3b：混合 RRF 融合 ────────────────────────────────────────────────────────

class _FakeBM25:
    def __init__(self, ranked_ids):
        self._ids = ranked_ids

    def search(self, query, top_k):
        return [{"id": i, "score": 1.0} for i in self._ids[:top_k]]


def _vec(*ids):
    ranked = list(ids)
    return lambda query, top_k: [{"id": i, "score": 1.0} for i in ranked[:top_k]]


def test_hybrid_fusion_order():
    # vec: a b c   bm25: c a d   （k=60）
    # a=1/61+1/62=0.032522  c=1/63+1/61=0.032266  b=1/62=0.016129  d=1/63=0.015873
    # 手算结论：a > c > b > d
    h = HybridRetriever(vec_search=_vec("a", "b", "c"), bm25_retriever=_FakeBM25(["c", "a", "d"]), k=60)
    out = h.search("任意查询", top_k=5)
    ids = [item["id"] for item in out]
    assert ids == ["a", "c", "b", "d"], ids


def test_hybrid_covers_both_sides():
    # 只在 bm25 出现的 e 也要进结果（覆盖两路并集）
    h = HybridRetriever(vec_search=_vec("a", "b"), bm25_retriever=_FakeBM25(["e"]), k=60)
    ids = [item["id"] for item in h.search("q", top_k=5)]
    assert set(ids) == {"a", "b", "e"}, ids


def test_hybrid_top_k_truncates():
    h = HybridRetriever(vec_search=_vec("a", "b", "c"), bm25_retriever=_FakeBM25(["a", "b", "c"]), k=60)
    assert len(h.search("q", top_k=2)) == 2


# ── 注册表 ──────────────────────────────────────────────────────────────────

def test_retriever_registry_names():
    assert set(RETRIEVERS.names()) >= {"bm25", "hybrid", "vector"}
    try:
        build_retriever("不存在")
        assert False
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
