# -*- coding: utf-8 -*-
# DEPRECATED(W4 2026-09): 能力已由 WeKnora 引擎（rag/engine.py）接管；本版仅作 WEKNORA_ENABLED=false 回退保留，下一版删除。
"""混合检索：向量 + BM25 两路召回，用 RRF 融合排名。

两路各取 top_n*2，融合后截断到 top_k，互补召回盲区。
k=60 为经验值（不暴露给管理员，YAGNI）。
"""
from ..fusion import reciprocal_rank_fusion
from .base import Retriever, RETRIEVERS


@RETRIEVERS.register("hybrid")
class HybridRetriever(Retriever):
    def __init__(self, vec_search, bm25_retriever, k=60):
        self._vec = vec_search
        self._bm25 = bm25_retriever
        self.k = k

    def search(self, query, top_k=5):
        wide = max(top_k * 2, top_k)
        vec_ids = [d["id"] for d in (self._vec(query, wide) if self._vec else [])]
        bm_ids = [d["id"] for d in (self._bm25.search(query, wide) if self._bm25 else [])]
        if not vec_ids and not bm_ids:
            return []
        fused = reciprocal_rank_fusion([vec_ids, bm_ids], k=self.k)
        return fused[:top_k]
