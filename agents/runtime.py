# -*- coding: utf-8 -*-
"""智能体运行时上下文：app.py 启动时注入共享对象，避免 agents 反向依赖 app。

store 为 KnowledgeStore 实例，仅 WeKnora 引擎关闭时的回退检索会用到
（WeKnora 开启时 PRD 接地直走 rag/engine，不碰 store）。
kb_ask 为问答共享内核（app.kb_ask_core），知识管家智能体经此提问，
与 /api/kb/ask 视图完全同一条链路（意图路由 + WeKnora/旧链路）。
"""

store = None
kb_ask = None
