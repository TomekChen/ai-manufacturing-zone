# -*- coding: utf-8 -*-
"""百炼（DashScope 兼容模式）底层请求 + 文本嵌入。

embed_texts：批量嵌入（每批最多 10 条，API 硬限制），返回已 L2 归一化的 float32 矩阵。
_dashscope 是共用的低层请求器，llm.chat 也复用它。
"""
import os

import numpy as np
import requests

from .config import DASHSCOPE_BASE, EMBED_MODEL, EMBED_DIM


def _api_key():
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY 环境变量")
    return key


def _dashscope(path, payload, timeout=60):
    r = requests.post(
        DASHSCOPE_BASE + path,
        json=payload,
        headers={"Authorization": "Bearer " + _api_key()},
        timeout=timeout,
    )
    try:
        data = r.json()
    except Exception:
        raise RuntimeError("百炼 API 返回异常（HTTP %s）" % r.status_code)
    if r.status_code != 200:
        msg = (data.get("error") or {}).get("message") or ("HTTP %s" % r.status_code)
        raise RuntimeError("百炼 API 错误：%s" % msg)
    return data


def embed_texts(texts):
    """批量嵌入（每批最多 10 条），返回已归一化的 float32 矩阵 (n, dim)。"""
    if not texts:
        return np.zeros((0, EMBED_DIM), dtype="float32")
    vecs = []
    for i in range(0, len(texts), 10):
        batch = [t if t.strip() else " " for t in texts[i:i + 10]]
        data = _dashscope("/embeddings", {"model": EMBED_MODEL, "input": batch})
        batch_vecs = [None] * len(batch)
        for item in data["data"]:
            batch_vecs[item["index"]] = item["embedding"]
        if any(v is None for v in batch_vecs):
            raise RuntimeError("百炼嵌入返回不完整")
        vecs.extend(batch_vecs)
    arr = np.array(vecs, dtype="float32")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms
