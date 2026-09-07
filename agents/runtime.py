# -*- coding: utf-8 -*-
"""智能体运行时上下文：app.py 启动时注入共享对象，避免 agents 反向依赖 app。

store 为 KnowledgeStore 实例，仅 WeKnora 引擎关闭时的回退检索会用到
（WeKnora 开启时 PRD 接地直走 rag/engine，不碰 store）。
"""

store = None
