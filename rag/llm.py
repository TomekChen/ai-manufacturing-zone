# -*- coding: utf-8 -*-
"""对话生成封装（复用 embedding 里的低层 _dashscope 请求器）。"""
from .config import CHAT_MODEL
from .embedding import _dashscope


def chat(messages, temperature=0.3, timeout=60):
    data = _dashscope("/chat/completions", {
        "model": CHAT_MODEL,
        "messages": messages,
        "temperature": temperature,
    }, timeout=timeout)
    return data["choices"][0]["message"]["content"]
