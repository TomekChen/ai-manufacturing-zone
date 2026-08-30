# -*- coding: utf-8 -*-
"""集中放配置常量与默认策略。env 变量在此读取，其它模块从这里 import。"""
import os

DASHSCOPE_BASE = os.environ.get("DASHSCOPE_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
EMBED_MODEL = os.environ.get("KB_EMBED_MODEL", "text-embedding-v3")
CHAT_MODEL = os.environ.get("KB_CHAT_MODEL", "qwen-plus")
EMBED_DIM = int(os.environ.get("KB_EMBED_DIM", "1024"))

# 分块默认：固定窗口（与旧 kb.py 完全一致），管理员可入库时改为 semantic
DEFAULT_CHUNKING = os.environ.get("KB_CHUNKING", "fixed")
CHUNK_SIZE = int(os.environ.get("KB_CHUNK_SIZE", "600"))
CHUNK_OVERLAP = int(os.environ.get("KB_CHUNK_OVERLAP", "80"))
SEMANTIC_MAX = int(os.environ.get("KB_SEMANTIC_MAX", "800"))
SEMANTIC_MIN = int(os.environ.get("KB_SEMANTIC_MIN", "100"))

TOP_K = int(os.environ.get("KB_TOP_K", "5"))

# 检索默认策略：hybrid（向量+BM25+RRF）。缺 jieba/rank_bm25 时 store 自动回退 vector。
DEFAULT_RETRIEVAL = os.environ.get("KB_RETRIEVAL", "hybrid")
RRF_K = 60

# 各分块策略的默认参数（build_chunker 未显式传参时使用）
CHUNKER_OPTS = {
    "fixed": {"size": CHUNK_SIZE, "overlap": CHUNK_OVERLAP},
    "semantic": {"max_size": SEMANTIC_MAX, "min_size": SEMANTIC_MIN, "overlap": CHUNK_OVERLAP},
}


def chunker_opts(name):
    return dict(CHUNKER_OPTS.get(name, {}))
