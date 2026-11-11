# -*- coding: utf-8 -*-
"""对外示例（A12）：客户点「立即体验」之后、自己输入之前，先看到一条真跑出来的结果。

背景：体验弹窗只有输入提示，客户不知道生成出来是什么玩意，就没有付费理由。示例内容
一律来自 listing.py 实测阶段的候选池（内置样例集真跑的输出），**不允许手写**——手写
的理想输出与「内置样例实测」口径冲突，客户一比就露馅。

数据来源单一：候选池只由 SAMPLES（全虚构输入）产生。严禁从 order_captures /
web_sources 取数，那里存的是客户真实原文。

存储：data/showcases.json——{agent_id: [{label, no, input, output, confidence,
coverage, latency_ms, ts}]}，每产品最多两格（「常规」「缺字段」），重复设置即覆盖。

Blueprint + 依赖注入（同 approval/listing 模式）：本模块不 import app，
app.py 装配时 init(data_dir, load_json, save_json, require_admin, read_candidates) 注入设施。
"""
import os
from datetime import datetime

from flask import Blueprint, request, jsonify

bp = Blueprint("showcase", __name__)

LABELS = ("常规", "缺字段")

# 依赖注入槽（app.py 装配时填充）
_data_dir = None
_load_json = None
_save_json = None
_require_admin = None
_read_candidates = None


def init(data_dir, load_json_fn, save_json_fn, require_admin_dec, read_candidates_fn):
    global _data_dir, _load_json, _save_json, _require_admin, _read_candidates
    _data_dir = data_dir
    _load_json = load_json_fn
    _save_json = save_json_fn
    _require_admin = require_admin_dec
    _read_candidates = read_candidates_fn
    bp.add_url_rule("/api/agents/<agent_id>/showcases", "api_showcase_public",
                    view_func=_api_public, methods=["GET"])
    bp.add_url_rule("/api/admin/showcases", "api_showcase_list",
                    view_func=_require_admin(_api_admin_list), methods=["GET"])
    bp.add_url_rule("/api/admin/showcases", "api_showcase_set",
                    view_func=_require_admin(_api_admin_set), methods=["POST"])


def _file():
    return os.path.join(_data_dir, "showcases.json")


def _seed_file():
    """出厂种子（随部署包放进 data/）：新环境没挑选记录时也不至于空着。"""
    return os.path.join(_data_dir, "showcases_seed.json")


def _book(path):
    book = _load_json(path, {}) or {}
    return book if isinstance(book, dict) else {}


def _rows(book, agent_id):
    return [r for r in (book.get(agent_id) or []) if isinstance(r, dict) and r.get("output")]


def read_showcases(agent_id):
    """某产品已定稿的对外示例，「常规」在前；后台没挑过则回落到出厂种子。"""
    rows = _rows(_book(_file()), agent_id) or _rows(_book(_seed_file()), agent_id)
    return sorted(rows, key=lambda r: LABELS.index(r["label"])
                  if r.get("label") in LABELS else len(LABELS))


def set_showcase(agent_id, no, label):
    """从候选池取该序号最新一轮输出，写进对应标签格，返回写入的示例。

    ValueError 由视图层收敛为 400（标签非法 / 候选池没有这条）。
    """
    if label not in LABELS:
        raise ValueError("标签只能是：%s" % "、".join(LABELS))
    cand = next((c for c in (_read_candidates(agent_id) or [])
                 if c.get("no") == no), None)
    if cand is None:
        raise ValueError("这条样例还没有实测输出，请先在「上架物料」跑一次实测")
    item = {
        "label": label,
        "no": no,
        "input": cand.get("input") or {},
        "output": cand.get("output"),
        "confidence": cand.get("confidence"),
        "coverage": cand.get("coverage"),
        "latency_ms": cand.get("latency_ms"),
        "ts": cand.get("ts") or _now(),
    }
    book = _book(_file())
    # 后台第一次挑时以现有定稿（含出厂种子）为底，避免另一格被清空
    rows = _rows(book, agent_id) or _rows(_book(_seed_file()), agent_id)
    rows = [r for r in rows if r.get("label") != label]
    rows.append(item)
    book[agent_id] = sorted(rows, key=lambda r: LABELS.index(r["label"]))
    _save_json(_file(), book)
    return item


def _public_view(item):
    """对外只给展示需要的键，内部键（样例序号、来源 job）不出门。"""
    return {k: item.get(k) for k in
            ("label", "input", "output", "confidence", "coverage", "latency_ms")}


def _now():
    return datetime.now().isoformat(timespec="seconds")


# ---------- 视图 ----------

def _api_public(agent_id):
    from agents.registry import get_agent
    if get_agent(agent_id) is None:
        return jsonify({"error": "产品不存在"}), 404
    return jsonify({"agent_id": agent_id,
                    "showcases": [_public_view(r) for r in read_showcases(agent_id)]})


def _api_admin_list():
    from agents.registry import get_agent
    agent_id = (request.args.get("agent_id") or "").strip()
    if get_agent(agent_id) is None:
        return jsonify({"error": "产品不存在"}), 404
    used = {r.get("no") for r in read_showcases(agent_id)}
    cands = [dict(c, in_use=c.get("no") in used) for c in (_read_candidates(agent_id) or [])]
    return jsonify({"agent_id": agent_id, "labels": list(LABELS),
                    "showcases": read_showcases(agent_id), "candidates": cands})


def _api_admin_set():
    from agents.registry import get_agent
    body = request.get_json(silent=True) or {}
    agent_id = (body.get("agent_id") or "").strip()
    if get_agent(agent_id) is None:
        return jsonify({"error": "产品不存在"}), 404
    try:
        no = int(body.get("no"))
    except (TypeError, ValueError):
        return jsonify({"error": "请选择一条实测样例"}), 400
    try:
        item = set_showcase(agent_id, no, (body.get("label") or "").strip())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "showcase": item})
