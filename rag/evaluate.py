# -*- coding: utf-8 -*-
"""Slice 6 · 离线 RAGAS-lite 评测。

设计要点（SPEC §3.4，US-30~32、US-34）：
- **手动触发才花额度**：只有 `start()` 被调用才跑；不引 ragas 重依赖，四段自写裁判提示词，
  每题 4 指标各一次 LLM 调用（`temperature=0`），18 题 = 72 次。
- **异步后台线程 + 状态轮询**：`start()` 立即返回，`get_state()` 给前端看进度；同时只允许一个
  评测在跑（模块级锁 + `_STATE["running"]` 布尔位）。
- **结果落盘滚动**：`data/kb_eval_results.json`，`EVAL_MAX_RESULTS`（默认 20）条上限，超限丢最旧。
  每次记录带当时**策略快照**（chunking / retrieval / top_k / embed_dim / chat_model / judge_model …），
  方便「换策略前后横向对比」。
- **对照组单列**：题集里 3 道 control 题（Q6/Q13/Q14）不进 `overall` 均值；只体现在 `by_type.control`
  里做敏感度自检。若 control 分数与 knowledge 均值接近，说明裁判提示词不够严。
- **无 API Key 直接拒绝启动**：`has_api_key()` 返 False 时 `start()` 抛 `RuntimeError`；前端按钮置灰。

W4（2026-09）：被测对象切到 WeKnora——`WEKNORA_ENABLED` 开启时，knowledge 意图题的
回答走 `engine.chat()`（每题独立会话，防跨题串上下文）、检索上下文走 `engine.search_context()`；
问候/跑题等非知识意图仍走旧意图人设（与线上 /api/kb/ask 的路由行为一致）。
四指标打分逻辑零改动；策略快照新增 `engine` 字段（weknora-lite / legacy）标注被测底座。

Seam S5（本文件的可测边界）：`load_questions / parse_score / build_judge_messages / judge_one /
strategy_snapshot / run_one_question / summarize_items / EvalStore / has_api_key / start / get_state`
——全部纯函数或可用假 chat/假 store 完全打桩，见 `tests/test_rag_eval.py`。
"""
import os
import re
import json
import time
import secrets
import threading
from datetime import datetime

from . import config
from . import engine as wk_engine
from .intents import classify_intent
from .llm import chat  # noqa: F401  —— 单测会 monkeypatch 本模块的 chat 名字

# 题集文件与本模块同目录；随代码走版本控制，不进 .gitignore
_HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_QUESTIONS_PATH = os.path.join(_HERE, "eval_questions.json")
EVAL_RESULTS_FILE = "kb_eval_results.json"


# ──────────────────────────────────────────────────────────────────────────────
# 题集加载
# ──────────────────────────────────────────────────────────────────────────────
_REQUIRED_FIELDS = ("id", "question", "reference", "category", "type")


def load_questions(path=EVAL_QUESTIONS_PATH):
    """读取小标准题集（18 题）；文件缺失/字段不齐时抛 RuntimeError。"""
    if not os.path.exists(path):
        raise FileNotFoundError("找不到评测题集：%s" % path)
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError("评测题集 JSON 解析失败：%s" % e)
    items = doc.get("items")
    if not isinstance(items, list) or not items:
        raise RuntimeError("评测题集缺少 items 数组")
    seen = set()
    for q in items:
        for k in _REQUIRED_FIELDS:
            if not q.get(k):
                raise RuntimeError("题目 %r 缺少字段 %s" % (q.get("id", "?"), k))
        if q["type"] not in ("knowledge", "control"):
            raise RuntimeError("题目 %s 的 type 非法：%s" % (q["id"], q["type"]))
        if q["id"] in seen:
            raise RuntimeError("题目 id 重复：%s" % q["id"])
        seen.add(q["id"])
    return items


# ──────────────────────────────────────────────────────────────────────────────
# 分数解析
# ──────────────────────────────────────────────────────────────────────────────
_SCORE_LABELED = re.compile(
    r'(?:分数|得分|评分|最终得分|总分|score|rating)[^0-9\-]{0,5}(-?\d+(?:\.\d+)?)',
    re.IGNORECASE,
)
_SCORE_ANY = re.compile(r'(-?\d+(?:\.\d+)?)')


def parse_score(text):
    """从裁判 LLM 自然语言输出里抠出 0–1 分数；找不到返回 None；越界夹到 [0,1]。"""
    if not text:
        return None
    m = _SCORE_LABELED.search(text) or _SCORE_ANY.search(text)
    if not m:
        return None
    try:
        val = float(m.group(1))
    except ValueError:
        return None
    if val < 0:
        return 0.0
    if val > 1:
        return 1.0
    return val


# ──────────────────────────────────────────────────────────────────────────────
# 裁判提示词（4 段，一 metric 一段）
# ──────────────────────────────────────────────────────────────────────────────
METRIC_LABELS = {
    "faithfulness": "忠实度",
    "answer_relevance": "答案相关性",
    "context_precision": "上下文精确率",
    "context_recall": "上下文召回率",
}

# 注意：字典可变（单测会往里追加标记以便打桩分派），所以这里用普通 dict 而不是 MappingProxy。
JUDGE_PROMPTS = {
    "faithfulness": (
        "你是 RAG 评测裁判，负责判断『模型回答』是否**忠实**于『检索到的上下文』——"
        "回答里的每一个具体事实都必须能在上下文中找到依据，不允许编造上下文里没有的内容。"
        "评分维度：（1）是否有上下文未提及但回答当作事实的具体数据/型号/机构；"
        "（2）是否曲解上下文；（3）拒答类回答若上下文确实无相关内容视为忠实。"
        "请用 0.0–1.0 打分，1.0=完全忠实，0.0=完全捏造。"
        "先简要给出中文理由（不超 100 字），最后一行必须以『分数：X.XX』结尾（保留两位小数）。"
    ),
    "answer_relevance": (
        "你是 RAG 评测裁判，负责判断『模型回答』与『问题』的**相关性**——"
        "回答是否切题、是否覆盖问题的核心意图、有没有答非所问或过度发散。"
        "不判断事实对错（那是忠实度的事）。若回答明确说明『知识库暂无相关内容』，视拒答是否恰当而定分。"
        "请用 0.0–1.0 打分，1.0=完全切题且回答充分，0.0=完全跑题。"
        "先简要给出中文理由（不超 100 字），最后一行必须以『分数：X.XX』结尾。"
    ),
    "context_precision": (
        "你是 RAG 评测裁判，负责判断『检索到的上下文』的**精确率**——"
        "上下文中有多少段落是真正与问题相关、能被用来支撑回答的；无关噪声越多分越低。"
        "如果上下文条目都相关但每段里只有部分有用，给 0.5–0.8；如果所有段落都相关且每段都紧凑，给 0.9–1.0；"
        "如果上下文完全为空或与问题毫无关系，给 0.0。"
        "请用 0.0–1.0 打分。先简要给出中文理由（不超 100 字），最后一行必须以『分数：X.XX』结尾。"
    ),
    "context_recall": (
        "你是 RAG 评测裁判，负责判断『检索到的上下文』对『参考标准答案』关键要点的**召回率**——"
        "标准答案里列的关键概念/数字/因果链，被上下文覆盖了多少。"
        "若标准答案说这是『不该回答』的对照题（预期低分），上下文越空反而召回率越接近 1.0（因为正确拒答）；"
        "此时按『上下文是否合理为空』评估。"
        "请用 0.0–1.0 打分，1.0=完全覆盖所有要点，0.0=完全未覆盖。"
        "先简要给出中文理由（不超 100 字），最后一行必须以『分数：X.XX』结尾。"
    ),
}

# 用户消息固定四段结构，让裁判 LLM 每次都看到全量信息；不同 metric 靠 system 提示词区分。
_USER_TEMPLATE = (
    "【问题】\n{question}\n\n"
    "【参考标准答案要点】\n{reference}\n\n"
    "【检索到的上下文】\n{context}\n\n"
    "【模型回答】\n{answer}\n\n"
    "请按系统提示词的评分维度输出理由与分数。"
)


def build_judge_messages(metric, question, reference, context, answer):
    """组装裁判消息；system 用 metric 专属提示词，user 用固定四段模板。"""
    if metric not in JUDGE_PROMPTS:
        raise KeyError("未知评测指标：%s" % metric)
    user_msg = _USER_TEMPLATE.format(
        question=(question or "").strip(),
        reference=(reference or "").strip(),
        context=(context or "").strip() or "（无检索结果）",
        answer=(answer or "").strip() or "（无回答）",
    )
    return [
        {"role": "system", "content": JUDGE_PROMPTS[metric]},
        {"role": "user", "content": user_msg},
    ]


def judge_one(metric, question, reference, context, answer):
    """单次裁判调用；LLM 挂了或返回不含数字 → None（上层按缺失处理，不阻断整轮评测）。"""
    try:
        msgs = build_judge_messages(metric, question, reference, context, answer)
        raw = chat(msgs, temperature=0.0)
        return parse_score(raw)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 策略快照
# ──────────────────────────────────────────────────────────────────────────────
def strategy_snapshot():
    """读当前 config 关键项，写进每次评测记录，便于换策略前后横向对比。
    engine 字段标注被测底座（W4）：weknora-lite = WeKnora 引擎，legacy = 旧自建链路。"""
    return {
        "engine": "weknora-lite" if wk_engine.is_enabled() else "legacy",
        "chunking": config.DEFAULT_CHUNKING,
        "retrieval": config.DEFAULT_RETRIEVAL,
        "top_k": config.TOP_K,
        "embed_dim": config.EMBED_DIM,
        "chunk_size": config.CHUNK_SIZE,
        "chunk_overlap": config.CHUNK_OVERLAP,
        "rrf_k": config.RRF_K,
        "chat_model": config.CHAT_MODEL,
        "judge_model": config.EVAL_JUDGE_MODEL,
        "history_max": config.HISTORY_MAX,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 单题评测：ask → search 拿上下文 → 四段裁判
# ──────────────────────────────────────────────────────────────────────────────
def _format_context(hits):
    return "\n\n".join(
        "【资料%d】%s\n%s" % (i + 1, h.get("doc", {}).get("title", ""), h.get("text", ""))
        for i, h in enumerate(hits)
    )


def run_one_question(store, item):
    """跑一题：拿答案 + 拿检索上下文，再跑四段裁判。

    W4：WEKNORA_ENABLED 开启且判为 knowledge 意图时，回答走 WeKnora 会话问答
    （每题新会话，防跨题串上下文）、上下文走 WeKnora 直查；非知识意图（问候/跑题）
    仍走旧 store.ask 意图人设，与线上 /api/kb/ask 路由口径一致。
    注意：本函数**只走单轮**——多轮改写和意图路由的完整覆盖交给 Slice 5 的测试；
    这里专注「给定当前策略下，本题能否答对」，避免评测本身引入随机性。
    """
    q = item["question"]
    t0 = time.perf_counter()
    if wk_engine.is_enabled() and classify_intent(q, has_history=False) == "knowledge":
        try:
            answer, refs, _sid = wk_engine.chat(q)
            refused = not refs  # 拒答口径与线上一致：0 引用才算拒
        except Exception:
            answer, refs, refused = "", [], True
        try:
            hits = wk_engine.search_context(q, top_k=config.TOP_K)
        except Exception:
            hits = []
        try:  # 遥测与线上口径一致（吞异常：评测不能被遥测拖垮）
            store.log_weknora_ask(secrets.token_hex(8), q, len(refs), refused, answer, t0)
        except Exception:
            pass
        intent, retrieval = "knowledge", "weknora"
        sources = [{"title": r.get("title", "")} for r in refs]
    else:
        ask_res = store.ask(q) or {}
        answer = ask_res.get("answer", "") or ""
        intent = ask_res.get("intent") or "knowledge"
        retrieval = ask_res.get("retrieval")
        sources = ask_res.get("sources", []) or []
        try:
            hits = store.search(q) or []
        except Exception:
            hits = []
    context = _format_context(hits)
    scores = {m: judge_one(m, q, item["reference"], context, answer) for m in config.EVAL_METRICS}
    _top = hits[0].get("score") if hits else None
    return {
        "id": item["id"],
        "category": item.get("category", ""),
        "type": item["type"],
        "question": q,
        "answer": answer,
        "answer_len": len(answer),
        "intent": intent,
        "retrieval": retrieval,
        "hits_count": len(hits),
        "top_score": round(_top, 4) if isinstance(_top, (int, float)) else None,
        "context_len": len(context),
        "sources_count": len(sources),
        "scores": scores,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 聚合：overall 只算 knowledge；by_type 单列 control 做敏感度自检
# ──────────────────────────────────────────────────────────────────────────────
def _avg(vals):
    xs = [v for v in vals if v is not None]
    if not xs:
        return None
    return round(sum(xs) / len(xs), 4)


def summarize_items(items, metrics=None):
    metrics = tuple(metrics or config.EVAL_METRICS)
    know = [it for it in items if it.get("type") == "knowledge"]
    ctl = [it for it in items if it.get("type") == "control"]

    def agg(subset):
        return {m: _avg([it["scores"].get(m) for it in subset]) for m in metrics}

    skipped = {m: sum(1 for it in items if it["scores"].get(m) is None) for m in metrics}
    return {
        "counts": {
            "total": len(items),
            "knowledge": len(know),
            "control": len(ctl),
            "skipped": skipped,
        },
        "overall": agg(know),           # 主指标：只算 knowledge，避免对照组拉低
        "by_type": {
            "knowledge": agg(know),
            "control": agg(ctl),
        },
        "per_question": [
            {
                "id": it.get("id"),
                "category": it.get("category"),
                "type": it.get("type"),
                "intent": it.get("intent"),
                "retrieval": it.get("retrieval"),
                "hits_count": it.get("hits_count"),
                "top_score": it.get("top_score"),
                "scores": it.get("scores"),
                "answer_len": it.get("answer_len"),
            }
            for it in items
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# 结果落盘：滚动上限，独立锁
# ──────────────────────────────────────────────────────────────────────────────
def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class EvalStore:
    def __init__(self, data_dir, max_results=None):
        self.path = os.path.join(data_dir, EVAL_RESULTS_FILE)
        self.max = max_results or config.EVAL_MAX_RESULTS
        self.lock = threading.Lock()

    def load(self):
        with self.lock:
            data = _load_json(self.path, [])
            return data if isinstance(data, list) else []

    def _save(self, records):
        _save_json(self.path, records)

    def append(self, record):
        """写入一条评测记录，返回补全了 id/ts 的记录本体；超上限丢最旧。"""
        rec = dict(record)
        rec.setdefault("id", secrets.token_hex(8))
        rec.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
        with self.lock:
            data = _load_json(self.path, [])
            if not isinstance(data, list):
                data = []
            data.append(rec)
            if len(data) > self.max:
                data = data[-self.max:]
            self._save(data)
        return rec

    def latest(self):
        data = self.load()
        return data[-1] if data else None


# ──────────────────────────────────────────────────────────────────────────────
# API Key 检查
# ──────────────────────────────────────────────────────────────────────────────
def has_api_key():
    return bool(os.environ.get("DASHSCOPE_API_KEY"))


# ──────────────────────────────────────────────────────────────────────────────
# 后台评测：模块级状态 + 锁 + 单线程 runner
# ──────────────────────────────────────────────────────────────────────────────
_STATE = {
    "running": False,
    "current": 0,
    "total": 0,
    "current_qid": "",
    "error": None,
    "started_at": None,
    "finished_at": None,
    "last_record_id": None,
    "last_summary": None,   # 上一次跑完的 overall/by_type 快照，前端刷新页面也能立即显示
}
_LOCK = threading.Lock()


def reset_state():
    with _LOCK:
        _STATE["running"] = False
        _STATE["current"] = 0
        _STATE["total"] = 0
        _STATE["current_qid"] = ""
        _STATE["error"] = None
        _STATE["started_at"] = None
        _STATE["finished_at"] = None


def get_state():
    with _LOCK:
        return {
            "running": _STATE["running"],
            "current": _STATE["current"],
            "total": _STATE["total"],
            "current_qid": _STATE["current_qid"],
            "error": _STATE["error"],
            "started_at": _STATE["started_at"],
            "finished_at": _STATE["finished_at"],
            "last_record_id": _STATE["last_record_id"],
            "last_summary": _STATE["last_summary"],
        }


def start(store, data_dir):
    """触发一次后台评测。返回启动快照；已在跑 or 无 API Key 抛 RuntimeError。"""
    if not has_api_key():
        raise RuntimeError("未配置 DASHSCOPE_API_KEY 环境变量，无法启动评测")
    with _LOCK:
        if _STATE["running"]:
            raise RuntimeError("已有评测正在运行中，请等待完成")
        # 提前读题集，读到就锁定 total；文件缺失/非法直接抛到这里（前端能立刻收到 400）
        questions = load_questions()
        snap = strategy_snapshot()
        _STATE["running"] = True
        _STATE["current"] = 0
        _STATE["total"] = len(questions)
        _STATE["current_qid"] = ""
        _STATE["error"] = None
        _STATE["started_at"] = datetime.now().isoformat(timespec="seconds")
        _STATE["finished_at"] = None
    t = threading.Thread(
        target=_run_in_background, args=(store, data_dir, questions, snap), daemon=True,
    )
    t.start()
    return {"started": True, "total": len(questions), "snapshot": snap}


def _set(**kv):
    with _LOCK:
        _STATE.update(kv)


def _run_in_background(store, data_dir, questions, snap):
    t0 = time.perf_counter()
    items = []
    try:
        for i, q in enumerate(questions):
            _set(current=i, current_qid=q["id"])
            try:
                r = run_one_question(store, q)
            except Exception as e:
                r = {
                    "id": q["id"], "category": q.get("category"), "type": q["type"],
                    "question": q["question"], "answer": "", "answer_len": 0,
                    "intent": None, "retrieval": None, "hits_count": 0, "top_score": None,
                    "context_len": 0, "sources_count": 0,
                    "scores": {m: None for m in config.EVAL_METRICS},
                    "error": str(e)[:160],
                }
            items.append(r)
        _set(current=len(questions), current_qid="")
        summary = summarize_items(items)
        elapsed = round(time.perf_counter() - t0, 2)
        record = {
            "elapsed": elapsed,
            "strategy_snapshot": snap,
            "counts": summary["counts"],
            "overall": summary["overall"],
            "by_type": summary["by_type"],
            "per_question": summary["per_question"],
        }
        saved = EvalStore(data_dir).append(record)
        _set(
            running=False,
            finished_at=datetime.now().isoformat(timespec="seconds"),
            last_record_id=saved["id"],
            last_summary={"overall": saved["overall"], "by_type": saved["by_type"], "counts": saved["counts"]},
        )
    except Exception as e:
        _set(running=False, error=str(e)[:200],
             finished_at=datetime.now().isoformat(timespec="seconds"))
