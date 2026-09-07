# -*- coding: utf-8 -*-
# DEPRECATED(W4 2026-09, 部分): 文档管理/检索/问答已由 WeKnora 引擎（rag/engine.py）接管；links 管理、问答遥测与意图人设仍在使用。本版仅作回退保留，下一版删除。
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
import time
import logging
import threading
import secrets
from datetime import datetime

import numpy as np
import faiss

from . import config
from .chunkers import build_chunker
from .retrievers import build_retriever, BM25Retriever
from .embedding import embed_texts
from .llm import chat
from .telemetry import Telemetry
from .intents import classify_intent, build_intent

logger = logging.getLogger(__name__)

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
        self.raw_file = os.path.join(data_dir, "kb_raw.json")
        self.index_file = os.path.join(data_dir, "kb_index.faiss")
        self.links_file = os.path.join(data_dir, "links.json")
        self.meta_file = os.path.join(data_dir, "kb_meta.json")
        self.lock = threading.Lock()

        self.docs = _load_json(self.docs_file, [])
        self.chunks = _load_json(self.chunks_file, {})
        self.raw = _load_json(self.raw_file, {})  # doc_id -> 原始全文（供换策略重建用）
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

        # BM25 索引缓存（惰性构建，chunk/审核状态变化时置脏重建）
        self._bm25_cache = None
        self._bm25_dirty = True

        # 问答遥测（Slice 4）：日志落盘 + 看板聚合，独立于文档锁，写失败不影响问答
        self.telemetry = Telemetry(data_dir)

    # ---------- 持久化 ----------

    def _persist_meta(self):
        _save_json(self.meta_file, {"next_id": self.next_id})

    def _persist_docs(self):
        _save_json(self.docs_file, self.docs)

    def _persist_chunks(self):
        _save_json(self.chunks_file, self.chunks)

    def _persist_raw(self):
        _save_json(self.raw_file, self.raw)

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
        chunker = build_chunker(name, **config.chunker_opts(name))  # 未知策略名此处即抛 KeyError
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
            self.raw[doc_id] = text  # 存原文，供换分块策略重建
            if status == "approved":
                self._embed_doc_locked(doc)
            self._bm25_dirty = True
            self._persist_docs()
            self._persist_chunks()
            self._persist_raw()
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
            self._bm25_dirty = True
            self._persist_docs()
            self._persist_index()
            return doc

    def reject(self, doc_id):
        with self.lock:
            doc = self.get_doc(doc_id)
            if not doc:
                raise RuntimeError("文档不存在")
            doc["status"] = "rejected"
            self._bm25_dirty = True
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
            self.raw.pop(doc_id, None)
            self._bm25_dirty = True
            self._persist_docs()
            self._persist_chunks()
            self._persist_raw()
            self._persist_index()
            return doc

    # ---------- 分块重建（Slice 3）----------

    def _new_chunk_ids(self, doc_id, pieces, into=None):
        """给切块分配自增 id 并写入 into（默认 self.chunks），返回 id 列表。调用方需已持锁。"""
        target = self.chunks if into is None else into
        cids = []
        for piece in pieces:
            cid = str(self.next_id)
            self.next_id += 1
            target[cid] = {"doc_id": doc_id, "text": piece}
            cids.append(cid)
        return cids

    def _rechunk_locked(self, doc, text, chunking):
        """按 chunking 重切 text 写进 self.chunks 并更新 doc 元数据；返回新块数。
        调用方需已持锁，且已清理该 doc 旧的块/向量。未知策略名由 build_chunker 抛 KeyError。"""
        chunker = build_chunker(chunking, **config.chunker_opts(chunking))
        pieces = chunker.chunk(text)
        if not pieces:
            raise RuntimeError("重新分块后内容为空")
        doc["chunk_ids"] = self._new_chunk_ids(doc["id"], pieces)
        doc["chunking"] = chunking
        doc["chars"] = sum(len(p) for p in pieces)
        return len(pieces)

    def rebuild_doc(self, doc_id, chunking=None):
        """单篇重建：可选换分块策略 -> 重切 -> 重嵌入（仅 approved 进索引）。

        历史文档若缺原始全文，只能按现有块原样重嵌入，不能换策略（换策略请重新上传/采集）。
        """
        with self.lock:
            doc = self.get_doc(doc_id)
            if not doc:
                raise RuntimeError("文档不存在")
            target = chunking or doc.get("chunking") or config.DEFAULT_CHUNKING
            was_approved = doc.get("status") == "approved"
            text = self.raw.get(doc_id)

            if not text:
                if chunking and chunking != doc.get("chunking"):
                    raise RuntimeError("该文档缺原始全文（历史数据），无法更换分块策略，请重新上传/采集")
                if was_approved:
                    self._remove_doc_vectors_locked(doc)
                    self._embed_doc_locked(doc)
                self._bm25_dirty = True
                self._persist_docs()
                self._persist_index()
                return {"doc": doc, "chunks": len(doc.get("chunk_ids", [])), "re_sharded": False}

            if was_approved:
                self._remove_doc_vectors_locked(doc)
            for cid in doc.get("chunk_ids", []):
                self.chunks.pop(cid, None)
            n = self._rechunk_locked(doc, text, target)
            if was_approved:
                self._embed_doc_locked(doc)
            self._bm25_dirty = True
            self._persist_docs()
            self._persist_chunks()
            self._persist_meta()
            self._persist_index()
            return {"doc": doc, "chunks": n, "re_sharded": True}

    def rebuild_all(self):
        """全库重建：逐篇按各自记录的分块策略重新切块 + 从零重建 FAISS 索引。

        历史无原文的文档保留其现有块（仅对 approved 的重新嵌入）。会重花 embedding 额度。
        """
        with self.lock:
            new_chunks = {}
            # 1) 先保留历史无原文文档的现有块
            for cid, ch in self.chunks.items():
                if not self.raw.get(ch["doc_id"]):
                    new_chunks[cid] = ch
            # 2) 重新切所有有原文的文档
            for doc in self.docs:
                text = self.raw.get(doc["id"])
                name = doc.get("chunking") or config.DEFAULT_CHUNKING
                if not text:
                    for cid in doc.get("chunk_ids", []):
                        if cid in self.chunks:
                            new_chunks[cid] = self.chunks[cid]
                    continue
                chunker = build_chunker(name, **config.chunker_opts(name))
                pieces = chunker.chunk(text)
                if not pieces:
                    for cid in doc.get("chunk_ids", []):
                        if cid in self.chunks:
                            new_chunks[cid] = self.chunks[cid]
                    continue
                doc["chunk_ids"] = self._new_chunk_ids(doc["id"], pieces, into=new_chunks)
                doc["chars"] = sum(len(p) for p in pieces)
            self.chunks = new_chunks
            # 3) 索引从空重建，仅嵌入 approved
            self.index = None
            for doc in self.docs:
                if doc.get("status") == "approved":
                    self._embed_doc_locked(doc)
            self._bm25_dirty = True
            self._persist_docs()
            self._persist_chunks()
            self._persist_meta()
            self._persist_index()
            vecs = self.index.ntotal if self.index is not None else 0
            return {"docs": len(self.docs), "chunks": len(self.chunks), "vectors": vecs}

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

    def _vector_rank_locked(self, query, top_k):
        """纯向量召回，返回 [{'id','score'}]（只含 approved）。调用方需已持锁。"""
        if self.index is None or self.index.ntotal == 0:
            return []
        qvec = embed_texts([query])
        k = min(top_k, self.index.ntotal)
        scores, ids = self.index.search(qvec, k)
        out = []
        for score, cid in zip(scores[0], ids[0]):
            if cid == -1:
                continue
            ch = self.chunks.get(str(int(cid)))
            if not ch:
                continue
            doc = self.get_doc(ch["doc_id"]) or {}
            if doc.get("status") != "approved":
                continue
            out.append({"id": str(int(cid)), "score": float(score)})
        return out

    def _get_bm25_locked(self):
        """返回缓存的 BM25Retriever（语料=已 approved 块）；缺依赖或无内容返回 None。"""
        if self._bm25_cache is not None and not self._bm25_dirty:
            return self._bm25_cache
        corpus = {
            cid: ch["text"] for cid, ch in self.chunks.items()
            if (self.get_doc(ch["doc_id"]) or {}).get("status") == "approved"
        }
        try:
            self._bm25_cache = BM25Retriever(corpus) if corpus else None
        except ImportError:
            logger.warning("缺少 jieba / rank_bm25，BM25 不可用，检索回退纯向量")
            self._bm25_cache = None
        except Exception as e:  # pragma: no cover
            logger.warning("BM25 索引构建失败：%s（回退纯向量）" % e)
            self._bm25_cache = None
        self._bm25_dirty = False
        return self._bm25_cache

    def search(self, query, top_k=TOP_K, retrieval=None):
        """按所选检索策略召回，返回 [{'score','text','doc','retrieval'}]。

        retrieval: vector | bm25 | hybrid（默认 config.DEFAULT_RETRIEVAL）。
        bm25/hybrid 在缺依赖时自动降级为 vector，不报错。
        """
        name = retrieval or config.DEFAULT_RETRIEVAL
        with self.lock:
            bm = None
            if name in ("bm25", "hybrid"):
                bm = self._get_bm25_locked()
                if bm is None:
                    name = "vector"
            vec_fn = self._vector_rank_locked
            retriever = build_retriever(name, vec_search=vec_fn, bm25=bm, k=config.RRF_K)
            ranked = retriever.search(query, top_k)
            hits = []
            for item in ranked:
                ch = self.chunks.get(str(item["id"]))
                if not ch:
                    continue
                doc = self.get_doc(ch["doc_id"]) or {}
                hits.append({
                    "score": item["score"], "text": ch["text"], "doc": doc,
                    "retrieval": name,
                })
            return hits

    def _log_ask(self, ask_id, question, retrieval, hits, top_score, refused, answer, t0,
                 intent=None, rewritten=False, turns=0):
        """记录一条问答遥测（Slice 4/5）。任何异常都吞掉——遥测绝不能拖垮正常回答。"""
        try:
            self.telemetry.record({
                "id": ask_id,
                "ts": datetime.now().isoformat(),
                "question": (question or "").strip()[:200],
                "retrieval": retrieval,
                "hits": hits,
                "top_score": top_score,
                "refused": refused,
                "answer_len": len(answer or ""),
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "feedback": None,
                "intent": intent or "knowledge",
                "rewritten": bool(rewritten),
                "turns": turns,
            })
        except Exception:
            logger.warning("问答遥测记录失败（不影响回答）", exc_info=True)

    def log_weknora_ask(self, ask_id, question, hits, refused, answer, t0, turns=0):
        """W3：WeKnora 引擎作答的遥测记录（retrieval 固定标 weknora，看板可分辨引擎）。
        分数尺度与自建链路不同，top_score 不记录（None）。任何异常吞掉。"""
        self._log_ask(ask_id, question, "weknora", hits, None, refused, answer, t0,
                      intent="knowledge", rewritten=False, turns=turns)

    def _clean_history(self, history):
        """清洗前端带来的多轮历史：只留 user/assistant、去空、按 HISTORY_MAX 截最近若干条。"""
        out = []
        for h in (history or []):
            if not isinstance(h, dict):
                continue
            role = h.get("role")
            content = (h.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                out.append({"role": role, "content": content[:1000]})
        if len(out) > config.HISTORY_MAX:
            out = out[-config.HISTORY_MAX:]
        return out

    def ask(self, question, history=None, retrieval=None):
        """意图路由问答（Slice 5）：先判意图，再交对应策略处理。

        - knowledge：按需用上下文改写 -> 检索 -> 拼上下文 -> 生成（无历史时与旧单轮完全一致）
        - smalltalk：轻量人设直接作答（不检索）
        - offtopic：礼貌拒答引导（不调 LLM，零 token）
        返回含 intent / retrieval（实际策略，非知识问答为 None）/ ask_id（供 👍/👎 回填）。
        """
        if not question or not question.strip():
            raise RuntimeError("问题不能为空")
        hist = self._clean_history(history)
        t0 = time.perf_counter()
        intent = classify_intent(question, has_history=bool(hist))
        handler = build_intent(intent)
        res = handler.answer(
            self, question, hist,
            retrieval=(retrieval if intent == "knowledge" else None),
        )
        ask_id = secrets.token_hex(8)
        self._log_ask(
            ask_id, question, res.get("retrieval"), res.get("hits", 0),
            res.get("top_score"), res.get("refused", False), res.get("answer", ""), t0,
            intent=intent, rewritten=res.get("rewritten", False), turns=len(hist),
        )
        return {
            "answer": res["answer"], "sources": res["sources"],
            "retrieval": res["retrieval"], "intent": intent, "ask_id": ask_id,
        }

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
