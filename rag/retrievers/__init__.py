# -*- coding: utf-8 -*-
"""检索策略子包。import 本包即触发 vector/bm25/hybrid 自注册。"""
from .base import Retriever, RETRIEVERS        # noqa: F401
from . import vector                           # noqa: F401 触发注册
from . import bm25                             # noqa: F401 触发注册
from . import hybrid                           # noqa: F401 触发注册
from .vector import VectorRetriever            # noqa: F401
from .bm25 import BM25Retriever                # noqa: F401
from .hybrid import HybridRetriever            # noqa: F401


def build_retriever(name, *, vec_search=None, bm25=None, k=60):
    """工厂：按名字组装一个 Retriever。

    bm25/hybrid 需要外部准备好的原料（向量排名函数 / BM25Retriever 实例），
    由 store 注入——这样既统一入口，又让 bm25/hybrid 能脱离 FAISS 单测。
    加一种检索策略 = 注册一个类 + 在此加一个分支即可（主流程 store 不改）。
    """
    RETRIEVERS.get(name)                        # 未知策略先抛 KeyError
    if name == "vector":
        return VectorRetriever(vec_search)
    if name == "bm25":
        return bm25
    if name == "hybrid":
        return HybridRetriever(vec_search, bm25, k=k)
    return RETRIEVERS.get(name)()               # 兜底：无参可构造的策略


__all__ = [
    "Retriever", "RETRIEVERS", "build_retriever",
    "VectorRetriever", "BM25Retriever", "HybridRetriever",
]
