# -*- coding: utf-8 -*-
"""IntentHandler 接口 + 意图处理策略注册表（Slice 5）。

一个意图处理器 = 「拿到问题（可能带多轮历史）后，决定用什么方式作答」。
统一入口 `answer(store, question, history, retrieval) -> dict`，返回约定字段：
    answer, sources, retrieval, hits, top_score, refused, rewritten(可选)
新增一种意图 = 注册一个 handler，store.ask 主流程不用改（沿用 chunker/retriever 的注册表套路）。
"""
from abc import ABC, abstractmethod

from ..registry import Registry

INTENTS = Registry("意图处理策略")


class IntentHandler(ABC):
    name = ""

    @abstractmethod
    def answer(self, store, question, history, retrieval=None):
        raise NotImplementedError
