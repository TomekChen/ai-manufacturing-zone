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

# 在线问答看板（Slice 4）：日志滚动上限（超限丢最旧）+ 趋势默认统计天数
TELEM_MAX = int(os.environ.get("KB_TELEM_MAX", "5000"))
TELEM_TREND_DAYS = int(os.environ.get("KB_TELEM_DAYS", "30"))

# 多轮对话（Slice 5）：随请求携带的最大历史条数（user+assistant 各计一条），防 prompt 膨胀
HISTORY_MAX = int(os.environ.get("KB_HISTORY_MAX", "12"))

# 离线评测（Slice 6 · RAGAS-lite）：
# - EVAL_MAX_RESULTS：评测历史落盘滚动上限（超限丢最旧），管理员手动「重跑评测」才写入
# - EVAL_JUDGE_MODEL：裁判 LLM 使用的模型，默认与问答模型一致；env 可独立切换（比如换更便宜的）
# - EVAL_METRICS：四指标顺序，后端聚合格式与前端条形渲染共享的唯一定义源
EVAL_MAX_RESULTS = int(os.environ.get("KB_EVAL_MAX", "20"))
EVAL_JUDGE_MODEL = os.environ.get("KB_EVAL_JUDGE_MODEL", CHAT_MODEL)
EVAL_METRICS = ("faithfulness", "answer_relevance", "context_precision", "context_recall")

# PRD 生成器（对齐老板新方向，售前工具）：
# - PRD_MODEL：生成 PRD 用的对话模型，默认与问答模型一致
# - PRD_TOP_K：生成前从知识库检索多少条行业参考做接地（空库则不接地）
# - PRD_TEMPERATURE：兼顾专业与稳定，取中等偏高
# - 输入长度上限：company / industry / business / raw_requirements，防 prompt 膨胀
PRD_MODEL = os.environ.get("KB_PRD_MODEL", CHAT_MODEL)
PRD_TOP_K = int(os.environ.get("KB_PRD_TOP_K", "4"))
PRD_TEMPERATURE = float(os.environ.get("KB_PRD_TEMPERATURE", "0.5"))
PRD_COMPANY_MAX = int(os.environ.get("KB_PRD_COMPANY_MAX", "60"))
PRD_INDUSTRY_MAX = int(os.environ.get("KB_PRD_INDUSTRY_MAX", "40"))
PRD_BIZ_MIN = int(os.environ.get("KB_PRD_BIZ_MIN", "5"))
PRD_BIZ_MAX = int(os.environ.get("KB_PRD_BIZ_MAX", "4000"))
PRD_RAW_MAX = int(os.environ.get("KB_PRD_RAW_MAX", "6000"))


def chunker_opts(name):
    return dict(CHUNKER_OPTS.get(name, {}))
