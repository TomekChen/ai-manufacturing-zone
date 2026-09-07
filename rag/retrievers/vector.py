# -*- coding: utf-8 -*-
# DEPRECATED(W4 2026-09): 能力已由 WeKnora 引擎（rag/engine.py）接管；本版仅作 WEKNORA_ENABLED=false 回退保留，下一版删除。
"""向量检索的薄适配器。

真正的 FAISS + 百炼嵌入逻辑留在 store 里（要网络/索引），
本类只把 store 传进来的排名函数 vec_search(query, top_k)->[{"id","score"}] 包装成统一接口，
使三种检索策略（vector/bm25/hybrid）在上层可互换。
"""
from .base import Retriever, RETRIEVERS


@RETRIEVERS.register("vector")
class VectorRetriever(Retriever):
    def __init__(self, vec_search):
        self._vec = vec_search

    def search(self, query, top_k=5):
        if not self._vec:
            return []
        return list(self._vec(query, top_k))
