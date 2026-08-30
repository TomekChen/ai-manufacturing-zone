# -*- coding: utf-8 -*-
"""Reciprocal Rank Fusion（RRF）。

给定多路已按相关性降序排好的 id 列表，用公式 score(d)=Σ 1/(k+rank_i(d)) 融合排名。
k=60 是经验值。互补两路（如向量 vs BM25）各自的召回盲区。

设计原则：纯函数、无副作用、只吃 id 列表，方便独立测。
"""
from collections import defaultdict


def reciprocal_rank_fusion(rank_lists, k=60):
    """
    rank_lists: list[list[id]]，每一路是 id 的降序排名（rank 从 1 起）。
    返回：[{"id": id, "score": float}]，按 score 降序；同分按首次出现顺序稳定排序。
    """
    scores = defaultdict(float)
    first_seen = {}
    for order, ids in enumerate(rank_lists):
        for rank, id_ in enumerate(ids, 1):
            scores[id_] += 1.0 / (k + rank)
            if id_ not in first_seen:
                first_seen[id_] = (order, rank)
    # 稳定排序：主键 score 降序，次键首次出现（哪一路、第几）升序
    ordered = sorted(scores.keys(), key=lambda x: (-scores[x], first_seen[x]))
    return [{"id": i, "score": scores[i]} for i in ordered]
