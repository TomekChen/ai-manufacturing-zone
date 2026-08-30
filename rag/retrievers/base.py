# -*- coding: utf-8 -*-
"""Retriever 接口 + 检索策略注册表。

一个 Retriever 只需实现 search(query, top_k) -> list[{"id","score"}]（按分数降序）。
id 即 chunk_id，上层 store 负责把 id 还原成文本与来源文档。
这样定义让 bm25 / hybrid 等纯逻辑可脱离 FAISS/网络单测（依赖注入排名函数）。
"""
from abc import ABC, abstractmethod

from ..registry import Registry

RETRIEVERS = Registry("检索策略")


class Retriever(ABC):
    name = ""

    @abstractmethod
    def search(self, query, top_k=5):
        raise NotImplementedError
