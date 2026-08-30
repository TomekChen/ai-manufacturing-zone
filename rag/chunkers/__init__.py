# -*- coding: utf-8 -*-
"""分块策略子包。import 本包即触发各具体 Chunker 自注册。"""
from .base import Chunker, CHUNKERS          # noqa: F401
from . import fixed                          # noqa: F401  触发注册
from . import semantic                       # noqa: F401  触发注册


def build_chunker(name="fixed", **opts):
    """工厂：按名字造一个 Chunker 实例。加新策略只需 register 一个类，不改这里。"""
    return CHUNKERS.get(name)(**opts)


__all__ = ["Chunker", "CHUNKERS", "build_chunker"]
