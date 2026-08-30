# -*- coding: utf-8 -*-
"""意图路由子包（Slice 5）。

对外：
  - 纯规则：classify_intent / pick_retrieval / needs_rewrite / build_messages
  - 意图处理策略注册表：INTENTS + build_intent（knowledge / smalltalk / offtopic）
import 本子包即触发三个 handler 自注册。
"""
from .rules import (                        # noqa: F401
    KNOWLEDGE, SMALLTALK, OFFTOPIC,
    classify_intent, pick_retrieval, needs_rewrite, build_messages,
)
from .base import IntentHandler, INTENTS    # noqa: F401
from . import handlers                      # noqa: F401  触发 knowledge/smalltalk/offtopic 注册


def build_intent(name):
    """工厂：按意图名取一个处理策略实例。未注册名抛 KeyError。"""
    return INTENTS.get(name)()


__all__ = [
    "KNOWLEDGE", "SMALLTALK", "OFFTOPIC",
    "classify_intent", "pick_retrieval", "needs_rewrite", "build_messages",
    "IntentHandler", "INTENTS", "build_intent",
]
