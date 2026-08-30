# -*- coding: utf-8 -*-
"""固定窗口分块：滑动窗口 + 重叠，尾部尽量回缩到自然断点。

与旧 kb.py 的 split_text 行为完全一致（默认 size=600 / overlap=80），
所以把它设为默认策略即可保证重构零行为变化。
"""
import re

from .base import Chunker, CHUNKERS


@CHUNKERS.register("fixed")
class FixedChunker(Chunker):
    def __init__(self, size=600, overlap=80):
        self.size = size
        self.overlap = overlap

    def chunk(self, text):
        text = re.sub(r"\n{3,}", "\n\n", (text or "")).strip()
        if not text:
            return []
        size, overlap = self.size, self.overlap
        if len(text) <= size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                for sep in ("\n", "。", "！", "？", "；", "，", " "):
                    pos = text.rfind(sep, start + size // 2, end)
                    if pos > start:
                        end = pos + 1
                        break
            piece = text[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
        return chunks
