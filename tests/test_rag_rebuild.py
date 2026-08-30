# -*- coding: utf-8 -*-
"""Slice 3：分块可选 + 重建（rebuild_doc / rebuild_all）单元测试。

只测纯逻辑，不碰网络/LLM：
  注入「假 faiss + 假嵌入」，让 store 在无原生依赖环境下跑通重建：
  - 入库记录原始全文（换策略重建的前提）
  - 单篇重建换分块策略 -> 重新切块、chunk_ids 全部重分配、策略标签更新
  - 历史无原文文档：不能换策略（抛错），只能原样重嵌入
  - 全库重建 -> 索引向量数 = 所有 approved 文档块数之和（pending 不进索引）

运行：py test_rag_rebuild.py
"""
import os
import sys
import types
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


# ── 假 faiss：只用 ntotal/add/remove 计数，不做真实相似运算 ──────────────────
class _FakeIndex:
    def __init__(self, dim=None):
        self._ids = []

    def add_with_ids(self, vecs, ids):
        self._ids.extend(int(i) for i in ids)

    def remove_ids(self, ids):
        drop = {int(i) for i in ids}
        self._ids = [x for x in self._ids if x not in drop]

    def search(self, q, k):
        k = max(int(k), 1)
        return (np.zeros((1, k), dtype="float32"),
                -np.ones((1, k), dtype="int64"))

    @property
    def ntotal(self):
        return len(self._ids)


if "faiss" not in sys.modules:
    _fa = types.ModuleType("faiss")
    _fa.IndexFlatIP = lambda dim: _FakeIndex(dim)
    _fa.IndexIDMap2 = lambda base: _FakeIndex()
    _fa.write_index = lambda idx, path: None
    _fa.read_index = lambda path: _FakeIndex()
    sys.modules["faiss"] = _fa

if "bs4" not in sys.modules:
    _bs = types.ModuleType("bs4")
    _bs.BeautifulSoup = object
    sys.modules["bs4"] = _bs

import rag.store as _st
from rag.store import KnowledgeStore

# 假嵌入：返回与文本条数等量的零向量（重建只关心分块/索引计数）
_embed_log = []


def _fake_embed(texts):
    _embed_log.append(len(texts))
    return np.zeros((len(texts), _st.EMBED_DIM), dtype="float32")


_st.embed_texts = _fake_embed


# 足够长的多段文本，让 fixed 与 semantic 切出的块数不同
LONG_TEXT = "\n\n".join(
    ["第%d段，" % i + "智能制造是制造业转型升级的主攻方向，涉及传感网络与数据分析。" * 3 for i in range(1, 9)]
)


def _new_store():
    return KnowledgeStore(tempfile.mkdtemp())


def test_add_text_records_raw_text():
    s = _new_store()
    doc = s.add_text(LONG_TEXT, title="A", status="pending")
    assert s.raw.get(doc["id"]) == LONG_TEXT, "原始全文应被记录"
    assert doc["chunking"] == _st.config.DEFAULT_CHUNKING, doc["chunking"]


def test_rebuild_doc_switch_strategy_rechunks():
    s = _new_store()
    doc = s.add_text(LONG_TEXT, title="A", status="pending", chunking="fixed")
    old_ids = set(doc["chunk_ids"])
    res = s.rebuild_doc(doc["id"], chunking="semantic")
    assert res["doc"]["chunking"] == "semantic", res["doc"]["chunking"]
    assert res["re_sharded"] is True
    new_ids = set(res["doc"]["chunk_ids"])
    assert new_ids and new_ids.isdisjoint(old_ids), "重建应重分配块 id"
    # 新块 id 都能在 chunks 里取到文本
    for cid in new_ids:
        assert cid in s.chunks and s.chunks[cid]["text"]
    # 旧块已被清除
    for cid in old_ids:
        assert cid not in s.chunks, "旧块应被删除"


def test_rebuild_doc_unknown_strategy_raises():
    s = _new_store()
    doc = s.add_text(LONG_TEXT, title="A", status="pending")
    try:
        s.rebuild_doc(doc["id"], chunking="不存在的策略")
        assert False, "未知策略应抛 KeyError"
    except KeyError:
        pass


def test_legacy_doc_without_raw_cannot_change_strategy():
    s = _new_store()
    doc = s.add_text(LONG_TEXT, title="A", status="approved", chunking="fixed")
    # 模拟历史数据：抹掉原文
    s.raw.pop(doc["id"], None)
    try:
        s.rebuild_doc(doc["id"], chunking="semantic")
        assert False, "缺原文又换策略应抛 RuntimeError"
    except RuntimeError:
        pass
    # 不换策略时只重嵌入，re_sharded=False，块不变
    before = list(doc["chunk_ids"])
    res = s.rebuild_doc(doc["id"])
    assert res["re_sharded"] is False
    assert res["doc"]["chunk_ids"] == before


def test_rebuild_all_index_matches_approved_chunks():
    s = _new_store()
    s.add_text(LONG_TEXT, title="已批1", status="approved", chunking="fixed")
    s.add_text(LONG_TEXT, title="已批2", status="approved", chunking="semantic")
    s.add_text(LONG_TEXT, title="草稿", status="pending", chunking="fixed")  # 不进索引
    out = s.rebuild_all()
    assert out["docs"] == 3, out
    expected = sum(len(d["chunk_ids"]) for d in s.docs if d["status"] == "approved")
    assert out["vectors"] == expected, (out["vectors"], expected)
    assert out["chunks"] == sum(len(d["chunk_ids"]) for d in s.docs)
    # 重建后每个块 id 都真实存在
    for d in s.docs:
        for cid in d["chunk_ids"]:
            assert cid in s.chunks


def test_rebuild_all_preserves_legacy_blocks():
    s = _new_store()
    legacy = s.add_text(LONG_TEXT, title="历史", status="approved", chunking="fixed")
    legacy_ids = list(legacy["chunk_ids"])
    s.raw.pop(legacy["id"], None)  # 历史无原文
    s.add_text(LONG_TEXT, title="新", status="approved", chunking="semantic")
    s.rebuild_all()
    got = [cid for cid in legacy_ids if cid in s.chunks]
    assert len(got) == len(legacy_ids), "无原文文档的块应被保留"


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
