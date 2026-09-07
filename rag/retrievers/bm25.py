# -*- coding: utf-8 -*-
# DEPRECATED(W4 2026-09): 能力已由 WeKnora 引擎（rag/engine.py）接管；本版仅作 WEKNORA_ENABLED=false 回退保留，下一版删除。
"""BM25 关键词检索：jieba 中文分词 + rank_bm25。

对精确数字、专有名词（如"营业收入""研发费用"）比纯向量更稳，与向量互补。
语料以 {chunk_id: text} 注入，可脱离 store/FAISS 单测。
"""
import numpy as np

from .base import Retriever, RETRIEVERS


@RETRIEVERS.register("bm25")
class BM25Retriever(Retriever):
    def __init__(self, corpus):
        """corpus: dict {id: text}（只放已入库/审核通过的块）。"""
        import jieba
        from rank_bm25 import BM25Okapi

        self.ids = list(corpus.keys())
        self._jieba = jieba
        tokenized = [list(jieba.cut(corpus[i])) for i in self.ids]
        self._bm25 = BM25Okapi(tokenized) if self.ids else None

    def search(self, query, top_k=5):
        if self._bm25 is None or not (query or query.strip()):
            return []
        tokens = list(self._jieba.cut(query))
        scores = self._bm25.get_scores(tokens)
        order = np.argsort(scores)[::-1]
        out = []
        for idx in order:
            s = float(scores[idx])
            if s <= 1e-9:
                break                      # 之后都是 0 分，不相关
            out.append({"id": self.ids[idx], "score": s})
            if len(out) >= top_k:
                break
        return out
