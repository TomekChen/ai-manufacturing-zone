# -*- coding: utf-8 -*-
"""KnowledgeStore：文件型知识库（文档审核流转 + FAISS 向量检索 + RAG 问答）。

Slice 1 说明：本文件把旧 kb.py 的 KnowledgeStore 原样搬来，只做两处结构变化：
  1) 切块改走可插拔 chunker（默认 fixed，参数与旧 split_text 一致 -> 零行为变化）；
  2) 嵌入/生成从 embedding / llm 模块 import，不再自带。
检索仍是纯向量（retriever 抽象与 BM25/混合在 Slice 2 引入）。

数据文件（全在 data_dir 下，随挂载卷持久化）：
  kb_docs.json / kb_chunks.json / kb_index.faiss / links.json / kb_meta.json
"""
import os
import json
import threading
import secrets
from datetime import datetime

import numpy as np
import faiss

from . import config
from .chunkers import build_chunker
from .embedding import embed_texts
from .llm import chat

TOP_K = config.TOP_K
EMBED_DIM = config.EMBED_DIM


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# 默认友情链接（首次启动初始化，均为智能制造领域权威站点）
DEFAULT_LINKS = [
    {"name": "工业和信息化部", "url": "https://www.miit.gov.cn/", "desc": "国家智能制造政策与行业主管部门"},
    {"name": "e-works 智造网", "url": "https://www.e-works.net.cn/", "desc": "智能制造专业媒体与产业研究平台"},
    {"name": "中国工控网", "url": "https://www.gongkong.com/", "desc": "工业自动化与智能制造行业门户"},
    {"name": "中国智能制造网", "url": "https://www.gkzhan.com/", "desc": "智能制造装备行业信息平台"},
    {"name": "赛迪研究院", "url": "https://www.ccidgroup.com/", "desc": "工业和信息化部直属研究机构"},
    {"name": "中国电子技术标准化研究院", "url": "https://www.cesi.cn/", "desc": "智能制造标准化研究机构"},
]


class KnowledgeStore:
    """文件型知识库：文档审核流转 + FAISS 向量检索 + RAG 问答。"""

    def __init__(self, data_dir):
        self.docs_file = os.path.join(data_dir, "kb_docs.json")
        self.chunks_file = os.path.join(data_dir, "kb_chunks.json")
        self.index_file = os.path.join(data_dir, "kb_index.faiss")
        self.links_file = os.path.join(data_dir, "links.json")
        self.meta_file = os.path.join(data_dir, "kb_meta.json")
        self.lock = threading.Lock()

        self.docs = _load_json(self.docs_file, [])
        self.chunks = _load_json(self.chunks_file, {})
        self.links = _load_json(self.links_file, None)
        if self.links is None:
            self.links = [{"id": secrets.token_hex(8), **l} for l in DEFAULT_LINKS]
            _save_json(self.links_file, self.links)
        meta = _load_json(self.meta_file, {"next_id": 1})
        self.next_id = int(meta.get("next_id", 1))

        self.index = None
        if os.path.exists(self.index_file):
            try:
                self.index = faiss.read_index(self.index_file)
            except Exception:
                self.index = None

    # ---------- 持久化 ----------

    def _persist_meta(self):
        _save_json(self.meta_file, {"next_id": self.next_id})

    def _persist_docs(self):
        _save_json(self.docs_file, self.docs)

    def _persist_chunks(self):
        _save_json(self.chunks_file, self.chunks)

    def _persist_index(self):
        if self.index is not None:
            faiss.write_index(self.index, self.index_file)

    # ---------- 文档管理 ----------

    def list_docs(self):
        with self.lock:
            return sorted(self.docs, key=lambda d: d.get("created_at", ""), reverse=True)

    def add_text(self, text, title, url="", doc_type="upload", status="pending", chunking=None):
        """切块并登记文档。status=approved 时立即嵌入入索引。返回 doc。

        chunking=None 时用 config.DEFAULT_CHUNKING（默认 fixed，等价旧 split_text）。
        """
        name = chunking or config.DEFAULT_CHUNKING
        chunker = build_chunker(name, **config.chunker_opts(name))
        chunks = chunker.chunk(text)
        if not chunks:
            raise RuntimeError("内容为空，无法入库")
        with self.lock:
            doc_id = secrets.token_hex(8)
            chunk_ids = []
            for piece in chunks:
                cid = str(self.next_id)
                self.next_id += 1
                self.chunks[cid] = {"doc_id": doc_id, "text": piece}
                chunk_ids.append(cid)
            doc = {
                "id": doc_id,
                "type": doc_type,  # upload | url | link
                "title": title or "（无标题）",
                "url": url,
                "status": status,
                "created_at": datetime.now().isoformat(),
                "chunking": name,
                "chunk_ids": chunk_ids,
                "chars": sum(len(c) for c in chunks),
            }
            self.docs.append(doc)
            if status == "approved":
                self._embed_doc_locked(doc)
            self._persist_docs()
            self._persist_chunks()
            self._persist_meta()
            self._persist_index()
            return doc

    def _embed_doc_locked(self, doc):
        """把 doc 的所有 chunk 嵌入并加入索引（调用方需已持锁）。"""
        cids = doc.get("chunk_ids", [])
        texts = [self.chunks[c]["text"] for c in cids if c in self.chunks]
        if not texts:
            return
        vecs = embed_texts(texts)
        if self.index is None:
            self.index = faiss.IndexIDMap2(faiss.IndexFlatIP(EMBED_DIM))
        ids = np.array([int(c) for c in cids], dtype="int64")
        self.index.add_with_ids(vecs, ids)

    def _remove_doc_vectors_locked(self, doc):
        if self.index is not None and doc.get("chunk_ids"):
            ids = np.array([int(c) for c in doc["chunk_ids"]], dtype="int64")
            try:
                self.index.remove_ids(ids)
            except Exception:
                pass

    def get_doc(self, doc_id):
        for d in self.docs:
            if d["id"] == doc_id:
                return d
        return None

    def get_doc_detail(self, doc_id):
        """返回文档详情，包括完整分块文本（用于管理员预览）。"""
        with self.lock:
            doc = self.get_doc(doc_id)
            if not doc:
                raise RuntimeError("文档不存在")
            chunks = []
            for cid in doc.get("chunk_ids", []):
                ch = self.chunks.get(cid)
                if ch:
                    chunks.append({"id": cid, "text": ch.get("text", "")})
            detail = dict(doc)
            detail["chunks"] = chunks
            detail["chunk_count"] = len(chunks)
            return detail

    def approve(self, doc_id):
        with self.lock:
            doc = self.get_doc(doc_id)
            if not doc:
                raise RuntimeError("文档不存在")
            if doc["status"] == "approved":
                return doc  # 幂等
            doc["status"] = "approved"
            doc["approved_at"] = datetime.now().isoformat()
            self._embed_doc_locked(doc)
            self._persist_docs()
            self._persist_index()
            return doc

    def reject(self, doc_id):
        with self.lock:
            doc = self.get_doc(doc_id)
            if not doc:
                raise RuntimeError("文档不存在")
            doc["status"] = "rejected"
            self._persist_docs()
            return doc

    def delete(self, doc_id):
        with self.lock:
            doc = self.get_doc(doc_id)
            if not doc:
                raise RuntimeError("文档不存在")
            self._remove_doc_vectors_locked(doc)
            self.docs = [d for d in self.docs if d["id"] != doc_id]
            for cid in doc.get("chunk_ids", []):
                self.chunks.pop(cid, None)
            self._persist_docs()
            self._persist_chunks()
            self._persist_index()
            return doc

    def stats(self):
        with self.lock:
            return {
                "total": len(self.docs),
                "approved": sum(1 for d in self.docs if d["status"] == "approved"),
                "pending": sum(1 for d in self.docs if d["status"] == "pending"),
                "rejected": sum(1 for d in self.docs if d["status"] == "rejected"),
                "chunks": len(self.chunks),
            }

    # ---------- 检索与问答 ----------

    def search(self, query, top_k=TOP_K):
        """返回 [{score, text, doc}]，按余弦相似度降序。"""
        with self.lock:
            if self.index is None or self.index.ntotal == 0:
                return []
            qvec = embed_texts([query])
            k = min(top_k, self.index.ntotal)
            scores, ids = self.index.search(qvec, k)
            hits = []
            for score, cid in zip(scores[0], ids[0]):
                if cid == -1:
                    continue
                ch = self.chunks.get(str(int(cid)))
                if not ch:
                    continue
                doc = self.get_doc(ch["doc_id"]) or {}
                if doc.get("status") != "approved":
                    continue
                hits.append({"score": float(score), "text": ch["text"], "doc": doc})
            return hits

    def ask(self, question):
        """RAG 问答：检索 top-k -> 拼 prompt -> qwen-plus 生成。"""
        if not question or not question.strip():
            raise RuntimeError("问题不能为空")
        hits = self.search(question)
        if not hits:
            return {
                "answer": "知识库中暂无与该问题相关的内容。管理员可在后台上传资料或从友情链接采集行业信息后再次提问。",
                "sources": [],
            }
        ctx = "\n\n".join(
            "【资料%d】%s\n%s" % (i + 1, h["doc"].get("title", ""), h["text"])
            for i, h in enumerate(hits)
        )
        messages = [
            {
                "role": "system",
                "content": "你是「智能制造专区」的知识库助手。请仅根据用户提供的参考资料回答问题，"
                           "用简体中文，条理清晰。参考资料中没有的内容不要编造；若资料不足以回答，"
                           "请直接说明知识库暂无相关内容。回答末尾不要输出与回答无关的客套话。",
            },
            {"role": "user", "content": "参考资料：\n" + ctx + "\n\n问题：" + question.strip()},
        ]
        answer = chat(messages)
        seen, sources = set(), []
        for h in hits:
            doc = h["doc"]
            key = doc.get("url") or doc.get("title")
            if key in seen:
                continue
            seen.add(key)
            sources.append({
                "title": doc.get("title", ""),
                "url": doc.get("url", ""),
                "snippet": h["text"][:160],
            })
        return {"answer": answer, "sources": sources}

    # ---------- 友情链接 ----------

    def list_links(self):
        with self.lock:
            return list(self.links)

    def save_link(self, payload):
        with self.lock:
            name = (payload.get("name") or "").strip()
            url = (payload.get("url") or "").strip()
            if not name or not url:
                raise RuntimeError("名称和地址不能为空")
            if not url.startswith(("http://", "https://")):
                raise RuntimeError("地址必须以 http:// 或 https:// 开头")
            desc = (payload.get("desc") or "").strip()
            lid = payload.get("id")
            if lid and any(l["id"] == lid for l in self.links):
                self.links = [
                    {**l, "name": name, "url": url, "desc": desc} if l["id"] == lid else l
                    for l in self.links
                ]
            else:
                self.links.append({"id": lid or secrets.token_hex(8), "name": name, "url": url, "desc": desc})
            _save_json(self.links_file, self.links)
            return list(self.links)

    def delete_link(self, link_id):
        with self.lock:
            self.links = [l for l in self.links if l["id"] != link_id]
            _save_json(self.links_file, self.links)
            return list(self.links)
