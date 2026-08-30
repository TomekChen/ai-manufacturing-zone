# -*- coding: utf-8 -*-
"""通用注册表（轻量工厂）。

三个可插拔维度（chunker / retriever / reranker）共用这一套，避免各写一份样板。
用法：
    CHUNKERS = Registry("分块策略")

    @CHUNKERS.register("fixed")
    class FixedChunker(Chunker): ...

    ck = CHUNKERS.get("fixed")(**opts)
"""


class Registry:
    def __init__(self, kind):
        self.kind = kind
        self._m = {}

    def register(self, name):
        """类装饰器：把实现登记到注册表。"""
        def deco(cls):
            cls.name = name
            self._m[name] = cls
            return cls
        return deco

    def get(self, name):
        if name not in self._m:
            raise KeyError("未注册的%s：%r（可选 %s）" % (self.kind, name, list(self._m)))
        return self._m[name]

    def names(self):
        return list(self._m)
