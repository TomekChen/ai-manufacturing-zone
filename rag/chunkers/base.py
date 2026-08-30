# -*- coding: utf-8 -*-
"""Chunker 接口：把一段纯文本切成若干块（字符串列表）。

智能制造语料进来都是纯文本（网页正文 / PDF 提取），所以接口统一吃 str、吐 list[str]。
参考项目按"结构化 blocks"分块，那是年报有版面解析才做得到，这里不照搬。
"""
from abc import ABC, abstractmethod

from ..registry import Registry

# 分块策略注册表（全项目唯一一份），各具体 Chunker 通过装饰器登记进来。
CHUNKERS = Registry("分块策略")


class Chunker(ABC):
    name = ""

    @abstractmethod
    def chunk(self, text):
        """返回块列表（已去空白、可能为空）。"""
        raise NotImplementedError
