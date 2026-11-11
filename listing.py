# -*- coding: utf-8 -*-
"""上架物料流水线（A11）：一个智能体产品 → 体检 → 样例实测出数据 → 文案 → 视频分镜 → 审批出包。

背景：老板要上架淘宝/京东/社媒，缺的不是流量而是「体验地址 + 效果数据 + 操作/宣传视频脚本」，
客户咨询多但拿不出案例材料。本模块把这套物料的生产过程固化成一条可重跑的工作流
（学 OpenMuse durable tasks：任务落库、分阶段记账、人工闸门后才算成品）。

四个阶段（后台线程跑，逐阶段写回账本，前端轮询看进度）：
  1. health      体检：产品是否已注册、引擎是否可用、样例集是否齐备
  2. metrics     实测：内置样例集逐个真跑 agent.run()，统计成功率/平均置信度/耗时/字段覆盖
  3. copy        文案：LLM 产出商品标题、一句话卖点、核心功能/操作说明/应用场景三段
  4. storyboard  分镜：调用场景分镜师智能体，产出宣传视频的镜头脚本（录制仍由人工完成）

Blueprint + 依赖注入（同 order_mail 模式）：本模块不 import app，
app.py 装配时 init(data_dir, load_json, save_json, require_admin) 注入设施。

存储：data/listings.json——[{id, agent_id, status, stages:{...}, ...}]，留最近 100 条。
      data/showcase_candidates.json——{agent_id: {样例序号: 最新一次输入与输出}}，实测留档（A12）。
      data/showcases.json——对外示例，后台从候选池挑选后写入（A12）。
状态机：running → done|failed → approved|rejected（人工闸门，reject 必填理由）。
"""
import json
import os
import re
import secrets
import threading
import time
import traceback
from datetime import datetime

from flask import Blueprint, Response, request, jsonify

from rag.llm import chat  # 单测 monkeypatch 本模块的 chat 名字

bp = Blueprint("listing", __name__)

MAX_LISTINGS = 100
SAMPLE_TIMEOUT_SEC = 120     # 单阶段最长跑多久（样例多时防挂死）

PORTAL_BASE_URL = (os.environ.get("PORTAL_BASE_URL")
                   or "http://47.115.223.159:8804").rstrip("/")

# 依赖注入槽（app.py 装配时填充）
_data_dir = None
_load_json = None
_save_json = None
_require_admin = None

# ---------- 内置样例集（每产品 3 组真实制造场景输入） ----------
SAMPLES = {
    "prd-advisor": [
        {"company": "华阳汽车零部件", "industry": "汽车零部件", "business": "304不锈钢法兰盘精加工，5000件月产能，交期紧", "mode": "guide"},
        {"company": "精工模具", "industry": "模具制造", "business": "注塑模具设计与CNC加工一体，小批量多品种", "mode": "guide"},
        {"company": "宏泰电子", "industry": "电子组装", "business": "SMT贴片+DIP插件，年产能200万套，客户要求全流程追溯",
         "mode": "normalize", "raw_requirements": "想要个能自动录订单的东西，最好财务对账也能一起管，我们用的是金蝶ERP。"},
    ],
    "kb-assistant": [
        {"question": "MES 系统和 ERP 系统的区别是什么"},
        {"question": "智能制造能力成熟度分几个等级"},
        {"question": "AI 视觉检测在产线上怎么落地"},
        # 第 4 组故意问知识库里没有的内容：演示「查不到就明说不知道」这条卖点
        {"question": "我们公司的差旅报销流程是什么"},
    ],
    "order-catcher": [
        {"text": "李经理 13800000000：我司（华阳汽车零部件）需订购 304 不锈钢法兰盘 DN50 带颈对焊 2000 件，订单号 PO-2026-1105，2026-12-20 前交货到苏州仓库，木箱包装。"},
        {"text": "询盘：精密轴 φ20x100mm 5000 支，报价请发 sales@example.com，交期 11 月底。"},
        {"text": "王工：上次那批齿轮泵再补 30 台，客户是北方重工，走物流到沈阳，发票开专票。"},
    ],
    "reconciler": [
        {"statement": "2026-10-08 华阳汽车零部件 收 50,000.00\n2026-10-12 精工模具 收 30,000.00\n2026-10-15 宏泰电子 收 19,900.00",
         "ledger": "华阳汽车零部件 应收 50,000.00\n精工模具 应收 30,000.00\n宏泰电子 应收 20,000.00"},
        {"statement": "2026-10-09 北方重工 收 120,000.00\n2026-10-20 中远机械 收 45,000.00",
         "ledger": "北方重工 应收 120,000.00\n中远机械 应收 45,600.00"},
        {"statement": "2026-10-11 蓝海装配 收 8,800.00\n2026-10-18 蓝海装配 收 12,000.00",
         "ledger": "蓝海装配 应收 20,800.00"},
    ],
    "scene-director": [
        {"text": "华阳精工——汽车零部件精密制造企业，展示从研发设计、智能产线、AI 质检到仓储物流"},
        {"text": "智慧电子厂——SMT 贴片与整机组装，突出 MES 追溯与自动检测"},
        {"text": "精工模具——小批量多品种模具车间，突出柔性产线与快速换型"},
    ],
}

_STAGES = ("health", "metrics", "copy", "storyboard")

_SYSTEM_COPY = """你是智能制造 AI 产品的电商上架文案撰写助手。根据给定的产品信息与实测数据，只输出一个 JSON 对象，不要输出任何其他文字：
{
  "title": "商品标题，20 字内，含品类词（如：AI 订单自动录入智能体）",
  "tagline": "一句话卖点，20 字内，讲客户收益",
  "features": ["核心功能 3-5 条，每条不超过 20 字"],
  "usage": ["操作说明 3 条，写清用户实际怎么点，如：粘贴订单原文→点击抽取→核对缺失字段"],
  "scenarios": ["应用场景 3 条，写明行业+岗位+解决的问题"],
  "audience": "适合客户画像，一句话"
}
要求：卖点必须与实测数据一致，不许编造没跑出来的数字；语言面向制造业老板与部门负责人，通俗不堆术语。"""


def init(data_dir, load_json_fn, save_json_fn, require_admin_dec):
    """装配注入并注册 admin 路由——require_admin 到此时才可用。"""
    global _data_dir, _load_json, _save_json, _require_admin
    _data_dir = data_dir
    _load_json = load_json_fn
    _save_json = save_json_fn
    _require_admin = require_admin_dec
    bp.add_url_rule("/api/admin/listings", "api_listing_create",
                    view_func=_require_admin(_api_create), methods=["POST"])
    bp.add_url_rule("/api/admin/listings", "api_listing_list",
                    view_func=_require_admin(_api_list), methods=["GET"])
    bp.add_url_rule("/api/admin/listings/<lid>", "api_listing_detail",
                    view_func=_require_admin(_api_detail), methods=["GET"])
    bp.add_url_rule("/api/admin/listings/<lid>/review", "api_listing_review",
                    view_func=_require_admin(_api_review), methods=["POST"])
    bp.add_url_rule("/api/admin/listings/<lid>/export", "api_listing_export",
                    view_func=_require_admin(_api_export), methods=["GET"])


# ---------- 存储 ----------

def _file():
    return os.path.join(_data_dir, "listings.json")


def read_listings():
    rows = _load_json(_file(), []) or []
    return [r for r in rows if isinstance(r, dict)]


def _find(lid):
    return next((r for r in read_listings() if r.get("id") == lid), None)


def _save(row):
    rows = read_listings()
    for i, r in enumerate(rows):
        if r.get("id") == row["id"]:
            rows[i] = row
            break
    else:
        rows.append(row)
    _save_json(_file(), rows[-MAX_LISTINGS:])


def _now():
    return datetime.now().isoformat(timespec="seconds")


# ---------- 示例候选池（A12：实测输出留档，供后台挑选为对外示例） ----------

def _cand_file():
    return os.path.join(_data_dir, "showcase_candidates.json")


def read_candidates(agent_id):
    """某产品每个样例序号的最新一次输出，序号小的在前；没留下输出的不列。"""
    book = _load_json(_cand_file(), {}) or {}
    per = book.get(agent_id) or {}
    out = [per[k] for k in sorted(per, key=lambda x: int(x)) if isinstance(per[k], dict)]
    return [r for r in out if r.get("output")]


def _save_candidate(agent_id, rec):
    """按 (产品, 样例序号) 覆盖为最新一轮，重跑不膨胀。"""
    book = _load_json(_cand_file(), {}) or {}
    book.setdefault(agent_id, {})[str(rec["no"])] = rec
    _save_json(_cand_file(), book)


# ---------- 阶段实现 ----------

def _stage_health(row, agent):
    """体检：注册、可用、样例齐备。返回 {ok, checks:[...]}，不通过则整单 failed。"""
    checks = []
    if agent is None:
        checks.append({"name": "产品已注册", "ok": False, "detail": "注册表里找不到该智能体"})
        return {"ok": False, "checks": checks}
    checks.append({"name": "产品已注册", "ok": True, "detail": agent.id})
    try:
        avail = bool(agent.available())
    except Exception as e:
        avail = False
        checks.append({"name": "引擎可用性", "ok": False, "detail": str(e)[:120]})
        return {"ok": False, "checks": checks}
    checks.append({"name": "引擎可用性", "ok": avail,
                   "detail": "API Key 已配置" if avail else "未配置依赖的模型 API Key"})
    samples = SAMPLES.get(agent.id) or []
    checks.append({"name": "实测样例集", "ok": len(samples) >= 1,
                   "detail": "%d 组样例" % len(samples)})
    return {"ok": avail and len(samples) >= 1, "checks": checks}


def _coverage(result):
    """结果字段覆盖率：非空值占比（衡量「跑出来的东西有多完整」）。"""
    inner = (result or {}).get("result")
    if not isinstance(inner, dict) or not inner:
        return 0.0
    vals = list(inner.values())
    filled = 0
    for v in vals:
        if isinstance(v, (list, dict)):
            filled += 1 if v else 0
        elif isinstance(v, str):
            filled += 1 if v.strip() else 0
        else:
            filled += 1 if v is not None else 0
    return round(filled / len(vals), 2)


def _stage_metrics(agent, lid=None):
    """样例实测：逐个真跑，统计成功率/平均置信度/耗时/覆盖率。

    跑通的样例输出同时写入候选池（A12），供管理后台挑选为对外示例。
    """
    samples = SAMPLES.get(agent.id) or []
    rows = []
    for i, payload in enumerate(samples, 1):
        t0 = time.time()
        item = {"no": i, "input": _brief(payload)}
        try:
            res = agent.run(dict(payload))
            item["ok"] = bool(isinstance(res, dict) and res.get("ok", True))
            item["confidence"] = res.get("confidence") if isinstance(res, dict) else None
            item["coverage"] = _coverage(res)
        except Exception as e:
            item["ok"] = False
            item["confidence"] = None
            item["coverage"] = 0.0
            item["error"] = str(e)[:160]
        item["latency_ms"] = int((time.time() - t0) * 1000)
        rows.append(item)
        if item["ok"] and lid:
            _save_candidate(agent.id, {
                "no": i,
                "input": dict(payload),
                "output": (res or {}).get("result"),
                "confidence": item["confidence"],
                "coverage": item["coverage"],
                "latency_ms": item["latency_ms"],
                "listing_id": lid,
                "ts": _now(),
            })

    ok_rows = [r for r in rows if r["ok"]]
    confs = [r["confidence"] for r in ok_rows if isinstance(r["confidence"], (int, float))]
    covs = [r["coverage"] for r in ok_rows if r["coverage"]]
    return {
        "ok": len(ok_rows) > 0,
        "total": len(rows),
        "success": len(ok_rows),
        "success_rate": round(len(ok_rows) / len(rows), 2) if rows else 0.0,
        "avg_confidence": round(sum(confs) / len(confs), 2) if confs else None,
        "avg_coverage": round(sum(covs) / len(covs), 2) if covs else None,
        "avg_latency_ms": int(sum(r["latency_ms"] for r in rows) / len(rows)) if rows else 0,
        "samples": rows,
    }


def _brief(payload):
    """样例输入摘要（账本里只留一行，不把整段原文灌进去）。"""
    for k in ("text", "question", "business", "statement"):
        v = payload.get(k)
        if v:
            return "%s：%s" % (k, str(v)[:60])
    return json.dumps(payload, ensure_ascii=False)[:60]


def _stage_copy(agent, metrics):
    """LLM 出上架文案（带实测数据，禁止编造数字）。"""
    conf = metrics.get("avg_confidence")
    facts = ("产品：%s（%s）\n简介：%s\n能力：%s\n实测：%d 组样例成功 %d 组（成功率 %s%%），"
             "平均置信度 %s，平均输出完整度 %s，平均耗时 %d ms") % (
        agent.name, agent.role, agent.desc,
        "、".join(agent.caps),
        metrics.get("total", 0), metrics.get("success", 0),
        int(metrics.get("success_rate", 0) * 100),
        ("%.0f%%" % (conf * 100)) if isinstance(conf, (int, float)) else "—",
        ("%.0f%%" % (metrics["avg_coverage"] * 100)) if metrics.get("avg_coverage") else "—",
        metrics.get("avg_latency_ms", 0))
    raw = chat([{"role": "system", "content": _SYSTEM_COPY},
                {"role": "user", "content": facts}], temperature=0.4)
    return _parse_json_obj(raw, "文案")


def _stage_storyboard(agent):
    """复用场景分镜师出宣传视频分镜（录制仍人工）。"""
    from agents.registry import get_agent
    director = get_agent("scene-director")
    if director is None:
        raise RuntimeError("分镜智能体未注册")
    brief = "%s——%s。%s。请为它在电商详情页的宣传视频产出滚动漫游分镜。" % (
        agent.name, agent.role, agent.desc)
    res = director.run({"text": brief})
    return res.get("result") if isinstance(res, dict) else None


def _parse_json_obj(raw, label):
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.strip("`").lstrip("json").strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        raise RuntimeError("%s生成失败：模型未返回结构化结果" % label)
    try:
        out = json.loads(s[start:end + 1])
    except ValueError:
        raise RuntimeError("%s生成失败：结果解析出错" % label)
    if not isinstance(out, dict):
        raise RuntimeError("%s生成失败：结果形状异常" % label)
    return out


# ---------- 流水线（后台线程） ----------

def run_pipeline(row, agent=None):
    """顺序跑四阶段，逐阶段写回账本。异常只影响当前阶段，其余照常记账。"""
    from agents.registry import get_agent
    if agent is None:
        agent = get_agent(row["agent_id"])
    stages = row.setdefault("stages", {})
    for name in _STAGES:
        stages[name] = {"status": "running", "ts": _now()}
        _save(row)
        try:
            if name == "health":
                data = _stage_health(row, agent)
            elif name == "metrics":
                data = _stage_metrics(agent, row.get("id"))
            elif name == "copy":
                data = _stage_copy(agent, stages.get("metrics", {}).get("data") or {})
            else:
                data = _stage_storyboard(agent)
            stages[name] = {"status": "done", "ts": _now(), "data": data}
            # 体检与实测是硬闸门：不通过就没有继续跑的必要
            if name in ("health", "metrics") and not (data or {}).get("ok"):
                for rest in _STAGES[_STAGES.index(name) + 1:]:
                    stages.setdefault(rest, {"status": "skipped", "ts": _now()})
                row["status"] = "failed"
                row["error"] = _stage_failure_note(name, data)
                _save(row)
                return row
        except Exception as e:
            stages[name] = {"status": "failed", "ts": _now(), "error": str(e)[:200]}
            if name in ("health", "metrics"):
                row["status"] = "failed"
                row["error"] = "%s 阶段失败：%s" % (name, str(e)[:160])
                _save(row)
                return row
        _save(row)
    row["status"] = "done"
    row["updated_at"] = _now()
    _save(row)
    return row


def _stage_failure_note(name, data):
    """硬闸门未通过时的人话原因。"""
    if name == "health":
        bad = [c for c in (data or {}).get("checks", []) if not c.get("ok")]
        return "体检未通过：" + "；".join("%s（%s）" % (c["name"], c.get("detail", "")) for c in bad)
    return "实测阶段无一条样例跑通，无法产出效果数据"


def _run_in_thread(lid):
    row = _find(lid)
    if row is None:
        return
    try:
        run_pipeline(row)
    except Exception:
        row["status"] = "failed"
        row["error"] = traceback.format_exc()[-300:]
        _save(row)


# ---------- 物料包导出 ----------

def export_markdown(row):
    """物料包（Markdown）：体验地址 + 效果数据 + 文案 + 分镜 + 审批状态。"""
    st = row.get("stages", {})
    metrics = (st.get("metrics") or {}).get("data") or {}
    copy = (st.get("copy") or {}).get("data") or {}
    board = (st.get("storyboard") or {}).get("data") or {}
    conf = metrics.get("avg_confidence")
    lines = [
        "# %s · 上架物料包" % (row.get("agent_name") or row.get("agent_id")),
        "",
        "- 产品 ID：%s" % row.get("agent_id"),
        "- 体验地址：%s（首页「已上线的智能体套件」→ 立即体验）" % PORTAL_BASE_URL,
        "- 生成时间：%s｜状态：%s" % (row.get("created_at"), row.get("status")),
        "",
        "## 一、效果数据（内置样例实测）",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        "| 实测样例 | %s 组 |" % metrics.get("total", 0),
        "| 成功 | %s 组（成功率 %s%%） |" % (metrics.get("success", 0), int(metrics.get("success_rate", 0) * 100)),
        "| 平均置信度 | %s |" % (("%.0f%%" % (conf * 100)) if isinstance(conf, (int, float)) else "—"),
        "| 输出完整度 | %s |" % (("%.0f%%" % (metrics["avg_coverage"] * 100)) if metrics.get("avg_coverage") else "—"),
        "| 平均耗时 | %s ms |" % metrics.get("avg_latency_ms", 0),
        "",
        "> 数据来自本专区内置样例集实测，非客户产线数据；上架时请按此口径标注。",
        "",
        "## 二、商品文案",
        "",
        "**标题**：%s" % copy.get("title", "—"),
        "",
        "**卖点**：%s" % copy.get("tagline", "—"),
        "",
    ]
    for key, label in (("features", "核心功能"), ("usage", "操作说明"), ("scenarios", "应用场景")):
        items = copy.get(key) or []
        lines += ["**%s**：" % label] + ["- %s" % x for x in items] + [""]
    if copy.get("audience"):
        lines += ["**适合客户**：%s" % copy["audience"], ""]
    scenes = board.get("scenes") or []
    lines += ["## 三、宣传视频分镜脚本（人工录制）", "",
              "美术方向：%s" % (board.get("style") or "—"), ""]
    for s in scenes:
        lines += ["### %s %s" % (s.get("no", ""), s.get("title", "")),
                  "- 画面：%s" % (s.get("desc") or "—"),
                  "- 镜头：%s" % (s.get("camera_move") or "—"),
                  "- 静帧提示词：%s" % (s.get("still_prompt") or "—"), ""]
    trail = row.get("trail") or []
    if trail:
        lines += ["## 四、审批留痕", ""]
        lines += ["- %s %s：%s" % (t.get("ts"), t.get("action"), t.get("note") or "") for t in trail]
    return "\n".join(lines)


# ---------- HTTP 视图 ----------

def _slim(row):
    st = row.get("stages", {})
    return {
        "id": row["id"], "agent_id": row["agent_id"], "agent_name": row.get("agent_name"),
        "status": row["status"], "created_at": row.get("created_at"),
        "error": row.get("error"),
        "stages": {k: (st.get(k) or {}).get("status") for k in _STAGES},
    }


def _api_create():
    p = request.get_json(force=True, silent=True) or {}
    agent_id = (p.get("agent_id") or "").strip()
    if not agent_id:
        return jsonify({"error": "请选择智能体产品"}), 400
    from agents.registry import get_agent
    agent = get_agent(agent_id)
    if agent is None:
        return jsonify({"error": "智能体不存在：%s" % agent_id}), 404
    row = {"id": secrets.token_hex(8), "agent_id": agent_id, "agent_name": agent.name,
           "status": "running", "created_at": _now(), "updated_at": _now(),
           "stages": {}}
    _save(row)
    threading.Thread(target=_run_in_thread, args=(row["id"],), daemon=True).start()
    return jsonify({"ok": True, "listing": _slim(row)}), 202


def _api_list():
    rows = [_slim(r) for r in read_listings()]
    rows.reverse()
    return jsonify(rows[:50])


def _api_detail(lid):
    row = _find(lid)
    if row is None:
        return jsonify({"error": "物料单不存在"}), 404
    out = dict(row)
    out["export_url"] = "/api/admin/listings/%s/export" % lid
    return jsonify(out)


def _api_review(lid):
    row = _find(lid)
    if row is None:
        return jsonify({"error": "物料单不存在"}), 404
    if row.get("status") in ("running",):
        return jsonify({"error": "流水线仍在执行，完成后再审批"}), 409
    p = request.get_json(force=True, silent=True) or {}
    action = (p.get("action") or "").strip()
    note = (p.get("note") or "").strip()
    if action not in ("approve", "reject"):
        return jsonify({"error": "action 只能是 approve 或 reject"}), 400
    if action == "reject" and not note:
        return jsonify({"error": "驳回必须填写理由"}), 400
    if row.get("status") in ("approved", "rejected"):
        return jsonify({"error": "该物料单已审批，不可重复操作"}), 409
    row.setdefault("trail", []).append(
        {"ts": _now(), "action": action, "note": note, "by": "admin"})
    row["status"] = "approved" if action == "approve" else "rejected"
    row["updated_at"] = _now()
    _save(row)
    return jsonify({"ok": True, "listing": _slim(row)})


def _api_export(lid):
    row = _find(lid)
    if row is None:
        return jsonify({"error": "物料单不存在"}), 404
    if row.get("status") not in ("approved", "done"):
        return jsonify({"error": "物料未就绪（需流水线完成并通过审批）"}), 409
    md = export_markdown(row)
    name = re.sub(r"[^\w\-]+", "_", "%s-%s" % (row.get("agent_id"), lid)) + ".md"
    return Response(md, mimetype="text/markdown", headers={
        "Content-Disposition": "attachment; filename=%s" % name})
