# -*- coding: utf-8 -*-
"""兼容层：RAG 知识库真实实现已拆分到 rag/ 包。

保留本文件仅为不改动 app.py 的 `import kb`。新代码请直接 `from rag import ...`。
  - 存储/检索/问答  -> rag.store.KnowledgeStore
  - 网页/文档解析   -> rag.ingest
  - 嵌入/生成        -> rag.embedding / rag.llm
  - 分块策略         -> rag.chunkers（fixed / semantic）
"""
from rag.store import KnowledgeStore
from rag import ingest as _ingest
from rag import embedding as _embedding
from rag import llm as _llm
from rag import config as _config
from rag.chunkers import build_chunker as _build_chunker

# 采集 / 解析
fetch_url_text = _ingest.fetch_url_text
looks_like_nav_page = _ingest.looks_like_nav_page
extract_pdf_text = _ingest.extract_pdf_text

# 嵌入 / 生成
embed_texts = _embedding.embed_texts
chat = _llm.chat

# 常量（旧代码可能引用）
CHUNK_SIZE = _config.CHUNK_SIZE
CHUNK_OVERLAP = _config.CHUNK_OVERLAP
TOP_K = _config.TOP_K
EMBED_DIM = _config.EMBED_DIM
EMBED_MODEL = _config.EMBED_MODEL
CHAT_MODEL = _config.CHAT_MODEL


def split_text(text):
    """向后兼容：等价于固定窗口分块（默认参数）。新代码请用 rag.chunkers。"""
    return _build_chunker("fixed", **_config.chunker_opts("fixed")).chunk(text)


__all__ = [
    "KnowledgeStore", "fetch_url_text", "looks_like_nav_page", "extract_pdf_text",
    "embed_texts", "chat", "split_text",
    "CHUNK_SIZE", "CHUNK_OVERLAP", "TOP_K", "EMBED_DIM", "EMBED_MODEL", "CHAT_MODEL",
]
