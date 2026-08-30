# -*- coding: utf-8 -*-
"""Slice 4 · Seam S4：问答看板 telemetry 聚合。

纯离线、确定性：直接喂「合成问答日志」给 summarize()，断言各项聚合口径正确。
不碰网络、不碰 LLM、不碰磁盘（聚合是纯函数）。
另附一个文件落盘 + 滚动上限的小用例（用临时目录）。
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from rag.telemetry import summarize, Telemetry, normalize_question  # noqa: E402

# 固定「现在」，让窗口计算可断言
NOW = datetime(2026, 8, 30, 12, 0, 0)


def _iso(dt):
    return dt.isoformat()


def rec(qid, *, when, question="q", retrieval="hybrid", hits=3,
        top_score=0.8, refused=None, answer_len=100, latency_ms=500, feedback=None):
    """构造一条问答日志（缺省即『正常命中且未拒答』）。"""
    if refused is None:
        refused = (hits == 0)
    return {
        "id": qid, "ts": _iso(when), "question": question, "retrieval": retrieval,
        "hits": hits, "top_score": top_score, "refused": refused,
        "answer_len": answer_len, "latency_ms": latency_ms, "feedback": feedback,
    }


def test_basic_totals_and_rates():
    d0 = NOW
    recs = [
        rec("a", when=d0, hits=3, top_score=0.9, refused=False),
        rec("b", when=d0, hits=0, top_score=None, refused=True),
        rec("c", when=d0, hits=5, top_score=0.7, refused=False, feedback="up"),
        rec("d", when=d0, hits=2, top_score=0.6, refused=False, feedback="down"),
        rec("e", when=d0, hits=0, top_score=None, refused=True, feedback="up"),
    ]
    s = summarize(recs, days=30, now=NOW)
    assert s["total"] == 5, s["total"]
    assert s["refused"] == 2, s["refused"]
    assert abs(s["refuse_rate"] - 0.4) < 1e-9, s["refuse_rate"]
    # 反馈：c=up,e=up 两个 up；d=down 一个
    assert s["feedback_up"] == 2 and s["feedback_down"] == 1
    assert abs(s["up_rate"] - round(2 / 3, 4)) < 1e-9, s["up_rate"]  # summarize 里 round 到 4 位
    # 平均命中数 = (3+0+5+2+0)/5 = 2.0
    assert abs(s["avg_hits"] - 2.0) < 1e-9, s["avg_hits"]


def test_window_filter_excludes_old():
    old = NOW - timedelta(days=45)
    recent = NOW - timedelta(days=2)
    recs = [
        rec("old1", when=old, hits=0, refused=True),
        rec("old2", when=old, hits=1, refused=False),
        rec("new1", when=recent, hits=2, refused=False),
    ]
    s = summarize(recs, days=30, now=NOW)
    assert s["total"] == 1, s["total"]  # 只剩 new1
    assert s["refused"] == 0


def test_boundary_exactly_at_cutoff_kept():
    # days=7：恰好 7 天整的记录应在窗口内（>= now-7d），再多 1 秒则被剔
    edge = NOW - timedelta(days=7)
    just_out = NOW - timedelta(days=7, seconds=1)
    assert summarize([rec("in", when=edge)], days=7, now=NOW)["total"] == 1
    assert summarize([rec("out", when=just_out)], days=7, now=NOW)["total"] == 0
    s = summarize([rec("in", when=edge), rec("out", when=just_out)], days=7, now=NOW)
    assert s["total"] == 1, s["total"]  # 只剩恰好压在边界的那条


def test_by_strategy_grouping():
    d0 = NOW
    recs = [
        rec("v1", when=d0, retrieval="vector", hits=3, top_score=0.9, refused=False, feedback="up"),
        rec("v2", when=d0, retrieval="vector", hits=0, top_score=None, refused=True),
        rec("h1", when=d0, retrieval="hybrid", hits=4, top_score=0.55, refused=False, feedback="down"),
    ]
    s = summarize(recs, days=30, now=NOW)
    by = s["by_strategy"]
    assert set(by.keys()) == {"vector", "hybrid"}, by.keys()
    assert by["vector"]["count"] == 2
    assert by["vector"]["refused"] == 1
    assert abs(by["vector"]["refuse_rate"] - 0.5) < 1e-9
    # vector 平均最高分：只算非 None 的 0.9 -> 0.9
    assert abs(by["vector"]["avg_top_score"] - 0.9) < 1e-9, by["vector"]
    assert by["vector"]["up"] == 1 and by["vector"]["down"] == 0
    assert abs(by["hybrid"]["avg_top_score"] - 0.55) < 1e-9
    assert by["hybrid"]["down"] == 1


def test_unanswered_list_grouped_and_sorted():
    d0 = NOW
    recs = [
        rec("a", when=d0, question="如何降低能耗", hits=0, refused=True),
        rec("b", when=d0, question="如何降低能耗", hits=0, refused=True),  # 重复
        rec("c", when=d0, question="  如何降低能耗  ", hits=0, refused=True),  # 归一化后同一条
        rec("d", when=d0 - timedelta(hours=1), question="数字孪生是什么", hits=0, refused=True),
        rec("e", when=d0, question="正常问题", hits=2, refused=False),  # 命中，不进清单
    ]
    s = summarize(recs, days=30, now=NOW)
    un = s["unanswered"]
    assert len(un) == 2, un
    assert un[0]["question"].strip().replace(" ", "") == "如何降低能耗"
    assert un[0]["count"] == 3, un[0]  # 归一化后三条并一起
    assert un[1]["count"] == 1
    # 按频次降序
    assert [x["count"] for x in un] == sorted([x["count"] for x in un], reverse=True)


def test_trend_buckets_days_and_order():
    d0 = NOW
    recs = [
        rec("a", when=d0),
        rec("b", when=d0 - timedelta(hours=5)),
        rec("c", when=d0 - timedelta(days=2)),
    ]
    s = summarize(recs, days=7, now=NOW)
    tr = s["trend"]
    assert len(tr) == 7, len(tr)
    # 升序，最后一天是 NOW 当天
    assert tr[-1]["date"] == NOW.strftime("%Y-%m-%d")
    assert tr[-1]["count"] == 2, tr[-1]  # a、b 同一天
    day2 = NOW - timedelta(days=2)
    assert tr[-3]["count"] == 1 and tr[-3]["date"] == day2.strftime("%Y-%m-%d"), tr[-3]
    # 日期升序
    dates = [x["date"] for x in tr]
    assert dates == sorted(dates)


def test_normalize_question():
    assert normalize_question("  如何 降低 能耗 ") == "如何降低能耗"
    assert normalize_question("ABC def") == "abcdef"


def test_empty_records():
    s = summarize([], days=30, now=NOW)
    assert s["total"] == 0
    assert s["refuse_rate"] == 0
    assert s["up_rate"] == 0
    assert s["by_strategy"] == {}
    assert s["unanswered"] == []
    assert len(s["trend"]) == 30  # 窗口天数照样铺满，计数为 0


def test_telemetry_cap_drops_oldest_on_disk():
    """文件落盘 + 滚动上限：超上限丢最旧（US-24）。"""
    tmp = tempfile.mkdtemp()
    t = Telemetry(tmp, max_records=3)
    for i in range(5):
        t.record({
            "id": "id%d" % i, "ts": _iso(NOW + timedelta(seconds=i)),
            "question": "q%d" % i, "retrieval": "vector", "hits": 1,
            "top_score": 0.5, "refused": False, "answer_len": 10,
            "latency_ms": 100, "feedback": None,
        })
    rows = t.load()
    assert len(rows) == 3, len(rows)
    assert [r["id"] for r in rows] == ["id2", "id3", "id4"], rows  # 最旧两条被丢


def test_set_feedback_persists():
    tmp = tempfile.mkdtemp()
    t = Telemetry(tmp, max_records=10)
    t.record({
        "id": "x1", "ts": _iso(NOW), "question": "q", "retrieval": "vector",
        "hits": 1, "top_score": 0.5, "refused": False, "answer_len": 10,
        "latency_ms": 100, "feedback": None,
    })
    assert t.set_feedback("x1", "up") is True
    assert t.set_feedback("nope", "down") is False
    rows = t.load()
    assert rows[0]["feedback"] == "up", rows


# ---- 迷你运行器 ----
def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print("PASS ", fn.__name__)
            passed += 1
        except Exception as e:
            print("FAIL ", fn.__name__, "->", repr(e))
    print("\n%d/%d passed" % (passed, len(fns)))
    return passed == len(fns)


if __name__ == "__main__":
    ok = _run_all()
    sys.exit(0 if ok else 1)
