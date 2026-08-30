# -*- coding: utf-8 -*-
"""Slice 4 · 在线问答看板遥测（telemetry）。

职责：
  1) 每次真实问答落一条日志（US-20）：时间/问题/实际检索策略/命中数/最高得分/是否拒答/答案长度/耗时/反馈。
  2) 👍/👎 反馈写回对应日志（US-21）。
  3) 聚合出看板指标（US-22/23）：总量、拒绝率、各策略并排、时间趋势、未命中问题清单。
  4) 日志滚动上限，超限丢最旧（US-24）。

设计取舍：
  - 聚合是**纯函数** summarize(records, days, now)——不读盘、不碰网络/LLM，便于离线确定性单测（Seam S4）。
  - 落盘用单个 JSON 文件（kb_telemetry.json）+ 线程锁，写一次读-改-写全量。有上限（默认几千条）故体量很小，
    与项目既有「文件型 + 全量 load」风格一致，不引入 DB。
  - top_score 是「当前检索策略返回的原始首位分数」，不同策略量纲不可直接比较（vector≈余弦、bm25 无界、hybrid 是 RRF 融合值），
    因此只在**同一策略内**用它看趋势，聚合里也按策略分组给出 avg_top_score，不做跨策略拉平。
"""
import os
import re
import json
import threading
import logging
from datetime import datetime, timedelta

from . import config

logger = logging.getLogger(__name__)

_WS = re.compile(r"\s+")


def normalize_question(text):
    """归一化问题文本用于『未命中清单』去重分组：去首尾空白、折叠内部空白、转小写。"""
    return _WS.sub("", (text or "").strip()).lower()


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _in_window(rec, cutoff):
    dt = _parse_ts(rec.get("ts"))
    return dt is not None and dt >= cutoff


def summarize(records, days=30, now=None):
    """把问答日志聚合成看板数据。纯函数，不产生副作用。

    days：统计窗口（含今天，往前 days 天）。now：基准『现在』（默认 datetime.now()，测试可注入以确定性）。
    返回：total / refused / refuse_rate / feedback_up / feedback_down / up_rate / avg_hits /
          by_strategy{...} / trend[{date,count}] / unanswered[{question,count,last_ts}]
    """
    now = now or datetime.now()
    cutoff = now - timedelta(days=days)
    rows = [r for r in records if _in_window(r, cutoff)]

    total = len(rows)
    refused = sum(1 for r in rows if r.get("refused"))
    refuse_rate = (refused / total) if total else 0.0
    fb_up = sum(1 for r in rows if r.get("feedback") == "up")
    fb_down = sum(1 for r in rows if r.get("feedback") == "down")
    up_rate = (fb_up / (fb_up + fb_down)) if (fb_up + fb_down) else 0.0
    avg_hits = (sum(r.get("hits", 0) or 0 for r in rows) / total) if total else 0.0

    # 各策略并排对比（同策略内可比）
    strat = {}
    for r in rows:
        name = r.get("retrieval") or "unknown"
        b = strat.setdefault(name, {
            "count": 0, "refused": 0, "top_sum": 0.0, "top_n": 0, "up": 0, "down": 0,
        })
        b["count"] += 1
        if r.get("refused"):
            b["refused"] += 1
        ts_score = r.get("top_score")
        if ts_score is not None:
            b["top_sum"] += ts_score
            b["top_n"] += 1
        if r.get("feedback") == "up":
            b["up"] += 1
        elif r.get("feedback") == "down":
            b["down"] += 1
    by_strategy = {}
    for name, b in strat.items():
        cnt = b["count"]
        by_strategy[name] = {
            "count": cnt,
            "refused": b["refused"],
            "refuse_rate": (b["refused"] / cnt) if cnt else 0.0,
            "avg_top_score": (b["top_sum"] / b["top_n"]) if b["top_n"] else 0.0,
            "up": b["up"],
            "down": b["down"],
        }

    # 时间趋势：铺满 days 个自然日桶（升序，最后一天=今天），无数据日计 0
    today = now.date()
    buckets = {}
    for i in range(days):
        day = today - timedelta(days=days - 1 - i)
        buckets[day] = 0
    for r in rows:
        dt = _parse_ts(r.get("ts"))
        if dt is not None and dt.date() in buckets:
            buckets[dt.date()] += 1
    trend = [{"date": d.strftime("%Y-%m-%d"), "count": c} for d, c in buckets.items()]

    # 未命中/被拒问题清单：按归一化问题去重计数，频次降序（同频按最近时间降序）
    groups = {}
    for r in rows:
        if not r.get("refused"):
            continue
        key = normalize_question(r.get("question"))
        if not key:
            continue
        g = groups.setdefault(key, {"question": r.get("question", ""), "count": 0, "last_dt": None})
        g["count"] += 1
        dt = _parse_ts(r.get("ts"))
        if dt is not None and (g["last_dt"] is None or dt > g["last_dt"]):
            g["last_dt"] = dt
            g["question"] = r.get("question", "")
    unanswered = [
        {"question": g["question"].strip() or key, "count": g["count"],
         "last_ts": g["last_dt"].isoformat() if g["last_dt"] else None}
        for key, g in groups.items()
    ]
    # 主排序按频次降序；稳定排序保证同频次内按最近提问时间倒序（先排时间再排次数）
    unanswered.sort(key=lambda x: x["last_ts"] or "", reverse=True)
    unanswered.sort(key=lambda x: x["count"], reverse=True)
    unanswered = unanswered[:100]  # 最多展示 100 条，避免超长响应

    return {
        "days": days,
        "total": total,
        "refused": refused,
        "refuse_rate": round(refuse_rate, 4),
        "feedback_up": fb_up,
        "feedback_down": fb_down,
        "up_rate": round(up_rate, 4),
        "avg_hits": round(avg_hits, 3),
        "by_strategy": by_strategy,
        "trend": trend,
        "unanswered": unanswered,
    }


def _load_list(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


class Telemetry:
    """问答遥测日志：文件落盘 + 反馈写回 + 聚合读数 + 滚动上限。线程安全。"""

    def __init__(self, data_dir, max_records=None):
        self.file = os.path.join(data_dir, "kb_telemetry.json")
        self.max_records = int(max_records or getattr(config, "TELEM_MAX", 5000))
        self.lock = threading.Lock()

    def load(self):
        return _load_list(self.file)

    def _save(self, rows):
        tmp = self.file + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False)
            os.replace(tmp, self.file)
        except Exception as e:  # 遥测写失败绝不能拖垮问答
            logger.warning("遥测日志写入失败：%s", e)

    def record(self, entry):
        """追加一条问答日志；超过上限则丢弃最旧（滚动，US-24）。"""
        with self.lock:
            rows = self.load()
            rows.append(entry)
            if len(rows) > self.max_records:
                rows = rows[-self.max_records:]
            self._save(rows)

    def set_feedback(self, ask_id, rating):
        """把 👍/👎 写回对应 ask_id 的记录。找到并更新返回 True，找不到 False。"""
        if rating not in ("up", "down"):
            return False
        with self.lock:
            rows = self.load()
            for r in rows:
                if r.get("id") == ask_id:
                    r["feedback"] = rating
                    self._save(rows)
                    return True
        return False

    def aggregate(self, days=None, now=None):
        days = int(days or getattr(config, "TELEM_TREND_DAYS", 30))
        return summarize(self.load(), days=days, now=now)
