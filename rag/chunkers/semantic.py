# -*- coding: utf-8 -*-
"""语义（段落）分块：以空行为段落边界，尽量整段合并到 max_size 以内，
不切断段落；单段超长时回落固定窗口，保证块不超标。

比纯固定窗口更"保语义"——一块就是一个或几个完整自然段，检索命中后给 LLM 的上下文不碎。
"""
import re

from .base import Chunker, CHUNKERS
from .fixed import FixedChunker


@CHUNKERS.register("semantic")
class SemanticChunker(Chunker):
    def __init__(self, max_size=800, min_size=100, overlap=80):
        self.max_size = max_size
        self.min_size = min_size
        self.overlap = overlap

    def chunk(self, text):
        text = re.sub(r"\n{3,}", "\n\n", (text or "")).strip()
        if not text:
            return []
        if len(text) <= self.max_size:
            return [text]

        paras = re.split(r"\n\s*\n", text)
        fallback = FixedChunker(size=self.max_size, overlap=self.overlap)
        out, buf, blen = [], [], 0

        def flush():
            nonlocal buf, blen
            if not buf:
                return
            c = "\n\n".join(buf)
            if len(c) >= self.min_size or not out:
                out.append(c)
            buf, blen = [], 0

        for p in paras:
            p = p.strip()
            if not p:
                continue
            if len(p) > self.max_size:        # 单段超长：先冲缓冲，再固定窗口拆这段
                flush()
                out.extend(fallback.chunk(p))
                continue
            if blen + len(p) > self.max_size and buf:
                flush()
            buf.append(p)
            blen += len(p) + 2

        flush()
        out = [c for c in out if c.strip()]
        return out or fallback.chunk(text)     # 全被 min_size 过滤则保底不吞内容
