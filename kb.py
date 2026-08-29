# -*- coding: utf-8 -*-
"""知识库引擎：百炼（DashScope 兼容模式）嵌入/LLM + FAISS 文件型向量索引。

数据文件（全部在 data/ 下，随挂载卷持久化）：
- kb_docs.json    文档元数据列表 [{id, type, title, url, status, created_at, chunk_ids, chars}]
- kb_chunks.json  分块文本 {chunk_id(str): {doc_id, text}}
- kb_index.faiss  FAISS 向量索引（IndexIDMap2(IndexFlatIP)，id=chunk_id）
- kb_meta.json    自增 id 计数

状态流转：
- 用户上传  -> pending  -> 管理员通过(approved，此时才嵌入向量入索引) / 拒绝(rejected)
- 管理员采集(URL/友情链接) -> 直接 approved 入库
- 删除：从索引 remove_ids + 清理元数据
"""
import os
import re
import json
import threading
import secrets
from datetime import datetime

import requests
import numpy as np
import faiss

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None

DASHSCOPE_BASE = os.environ.get("DASHSCOPE_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
EMBED_MODEL = os.environ.get("KB_EMBED_MODEL", "text-embedding-v3")
CHAT_MODEL = os.environ.get("KB_CHAT_MODEL", "qwen-plus")
EMBED_DIM = int(os.environ.get("KB_EMBED_DIM", "1024"))

CHUNK_SIZE = 600    # 每块约 600 字符
CHUNK_OVERLAP = 80  # 相邻块重叠
TOP_K = 5           # 问答检索条数


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


def chat(messages, temperature=0.3):
    data = _dashscope("/chat/completions", {
        "model": CHAT_MODEL,
        "messages": messages,
        "temperature": temperature,
    })
    return data["choices"][0]["message"]["content"]


def split_text(text):
    """按 ~600 字符切块，尽量在句读处断开，块间重叠 80 字符。"""
    text = re.sub(r"\n{3,}", "\n\n", (text or "")).strip()
    if not text:
        return []
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            # 在后半段找一个自然断点（换行/句号等）
            for sep in ("\n", "。", "！", "？", "；", "，", " "):
                pos = text.rfind(sep, start + CHUNK_SIZE // 2, end)
                if pos > start:
                    end = pos + 1
                    break
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def fetch_url_text(url, timeout=25):
    """抓取网页并提取正文文本，返回 (title, text)。"""
    if BeautifulSoup is None:
        raise RuntimeError("服务器缺少 beautifulsoup4 依赖")
    r = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
        timeout=timeout,
        verify=False,
    )
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript", "iframe", "form"]):
        tag.decompose()
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"[ \t\u3000]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text


def extract_pdf_text(fileobj):
    from pypdf import PdfReader
    reader = PdfReader(fileobj)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


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

    def add_text(self, text, title, url="", doc_type="upload", status="pending"):
        """切块并登记文档。status=approved 时立即嵌入入索引。返回 doc。"""
        chunks = split_text(text)
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
