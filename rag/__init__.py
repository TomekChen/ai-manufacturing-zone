# -*- coding: utf-8 -*-
"""rag 包：知识库引擎的可插拔组件集合。

Slice 1 只放：registry + fusion + chunkers(fixed/semantic)。
后续切片增量补：retrievers(vector/bm25/hybrid)、rerankers、embedding、llm、ingest、store、telemetry、evaluate。
"""
