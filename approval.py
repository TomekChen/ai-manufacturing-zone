# -*- coding: utf-8 -*-
"""审批留痕中间层（A10）：智能体产出先审后用——提交即 pending，人工批准/驳回后回执归档。

场景（学 OpenMuse 的 durable tasks + approval gate，不搬码）：财务/质量类智能体
的建议（对账分录、工单录入）不能 AI 直接生效，须人工批准；ISO 体系要求"谁、何时、
批了什么"可追溯。每次状态流转 append 进 trail，已决事项不可改不可删（409）。

Blueprint + 依赖注入（同 prd_sessions/order_mail 模式）：本模块不 import app，
app.py 装配时 init(data_dir, load_json, save_json, require_admin) 注入设施。

存储：data/approvals.json（挂载卷内，不入 git），留最近 500 条。
智能体执行复用注册表 agent.run()，本模块不碰 LLM 细节。
"""
import secrets
from datetime import datetime

from flask import Blueprint, request, jsonify

from core import rate_limited

bp = Blueprint("approval", __name__)

MAX_APPROVALS = 500


class AlreadyDecided(Exception):
    """审批单已处理：留痕不可变更（ISO 审计要求）。"""

# 依赖注入槽（app.py 装配时填充）
_data_dir = None
_load_json = None
_save_json = None
_require_admin = None


def init(data_dir, load_json_fn, save_json_fn, require_admin_dec):
    global _data_dir, _load_json, _save_json, _require_admin
    _data_dir = data_dir
    _load_json = load_json_fn
    _save_json = save_json_fn
    _require_admin = require_admin_dec
    bp.add_url_rule("/api/approvals", "api_approval_submit",
                    view_func=_api_submit, methods=["POST"])
    bp.add_url_rule("/api/admin/approvals", "api_approval_list",
                    view_func=_require_admin(_api_list), methods=["GET"])
    bp.add_url_rule("/api/admin/approvals/<aid>", "api_approval_detail",
                    view_func=_require_admin(_api_detail), methods=["GET"])
    bp.add_url_rule("/api/admin/approvals/<aid>/approve", "api_approval_approve",
                    view_func=_require_admin(_api_decide("approved")), methods=["POST"])
    bp.add_url_rule("/api/admin/approvals/<aid>/reject", "api_approval_reject",
                    view_func=_require_admin(_api_decide("rejected")), methods=["POST"])


def _file():
    import os
    return os.path.join(_data_dir, "approvals.json")


def _items():
    rows = _load_json(_file(), []) or []
    return rows if isinstance(rows, list) else []


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _summarize(result):
    """结果压成一行人话摘要（列表页用）。按已知智能体的形状取数，兜底截断。"""
    if not isinstance(result, dict):
        return str(result)[:120]
    if "matched" in result:
        ub, ul = result.get("unmatched_bank") or [], result.get("unmatched_ledger") or []
        return ("完全匹配 %d · 疑似 %d · 未达 %d" % (
            len(result.get("matched") or []), len(result.get("suspected") or []),
            len(ub) + len(ul)))
    if "products" in result:
        return "客户 %s · 产品 %d 项 · 交期 %s" % (
            result.get("customer") or "未知", len(result.get("products") or []),
            result.get("delivery_date") or "未提供")
    return str(result)[:120]


def submit_for_approval(agent, payload, source="web"):
    """跑智能体并落一条 pending 审批。agent 可注入（测试桩）。
    ValueError/RuntimeError 由视图层按 400/502 收敛，不落账（失败的产出没有审批价值）。"""
    r = agent.run(payload or {})
    result = r.get("result")
    item = {
        "id": secrets.token_hex(8),
        "agent_id": agent.id,
        "agent_name": agent.name,
        "title": "%s · %s" % (agent.name, _now()),
        "summary": _summarize(result),
        "confidence": r.get("confidence"),
        "payload": payload or {},
        "result": result,
        "status": "pending",
        "created": _now(),
        "decided_at": None,
        "note": "",
        "source": source,
        "trail": [{"at": _now(), "action": "submitted",
                   "note": "由 %s 提交，AI 建议待人工审批" % source}],
    }
    items = _items()
    items.append(item)
    _save_json(_file(), items[-MAX_APPROVALS:])
    return item


def decide(aid, action, note=""):
    """批准/驳回。已决事项不可再改（留痕不可变）。找不到返回 None，已决抛 AlreadyDecided。"""
    items = _items()
    item = next((x for x in items if x.get("id") == aid), None)
    if item is None:
        return None
    if item.get("status") != "pending":
        raise AlreadyDecided()
    item["status"] = action
    item["decided_at"] = _now()
    item["note"] = (note or "").strip()[:500]
    item["trail"].append({"at": item["decided_at"], "action": action, "note": item["note"]})
    _save_json(_file(), items)
    return item


# ---------- HTTP 视图 ----------

def _api_submit():
    from agents.registry import get_agent
    p = request.get_json(force=True, silent=True) or {}
    agent = get_agent((p.get("agent_id") or "").strip())
    if agent is None or agent.status != "live":
        return jsonify({"error": "智能体不存在或未上线"}), 404
    if not agent.available():
        return jsonify({"error": "智能体暂不可用，请稍后再试"}), 503
    # 先校验后限流（同 agents_api 的通用 run 端点语义）：无效请求不占额度
    if rate_limited(request.remote_addr, limit=5, window=3600, bucket="approval_submit"):
        return jsonify({"error": "提交太频繁（每 IP 每小时 5 次），请稍后再试"}), 429
    payload = p.get("payload")
    if not isinstance(payload, dict) or not payload:
        return jsonify({"error": "payload 不能为空（智能体运行的原始入参）"}), 400
    try:
        item = submit_for_approval(agent, payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "提交失败：%s" % str(e)[:160]}), 502
    return jsonify({"ok": True, "id": item["id"], "status": item["status"],
                    "title": item["title"], "summary": item["summary"],
                    "created": item["created"]})


def _api_list():
    rows = []
    for x in reversed(_items()):
        rows.append({k: x.get(k) for k in
                     ("id", "agent_id", "agent_name", "title", "summary",
                      "confidence", "status", "created", "decided_at", "note")})
    return jsonify(rows[:200])


def _api_detail(aid):
    item = next((x for x in _items() if x.get("id") == aid), None)
    if item is None:
        return jsonify({"error": "审批单不存在"}), 404
    return jsonify(item)


def _api_decide(action):
    def view(aid):
        p = request.get_json(force=True, silent=True) or {}
        note = (p.get("note") or "").strip()
        if action == "rejected" and not note:
            return jsonify({"error": "驳回必须填写理由（留痕要求）"}), 400
        try:
            item = decide(aid, action, note)
        except AlreadyDecided:
            return jsonify({"error": "该审批单已处理，留痕不可变更"}), 409
        if item is None:
            return jsonify({"error": "审批单不存在"}), 404
        return jsonify({"ok": True, "id": aid, "status": item["status"],
                        "decided_at": item["decided_at"]})
    return view
