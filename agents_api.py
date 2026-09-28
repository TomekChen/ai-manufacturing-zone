# -*- coding: utf-8 -*-
"""智能体公开域（R5 自 app.py 拆出）：注册表查询、planner 派发、直跑、后台 PRD 生成。

一个变更理由：智能体怎么被调用。实现在 agents/ 包，本模块只是 HTTP 门面。
"""
from flask import Blueprint, request, jsonify

from core import require_admin, rate_limited, limiter
from rag import prd as kb_prd
import agents  # import 即注册（agents/registry.py 底部挂载所有智能体实现）

bp = Blueprint("agents_api", __name__)

_kb = None  # rag.store.KnowledgeStore（后台 PRD 生成接地用，装配注入）


def init(kb):
    global _kb
    _kb = kb


def _run_agent(agent, payload):
    """执行智能体并把异常收敛为带状态码的 Response，公开运行端点共用。

    注意：必须把状态码写回 Response 本体再返回——调用方若只拿 Response，
    元组里的 400/502/500 会被吞成 200（测试抓到过）。
    """
    try:
        out, status = jsonify(agent.run(payload)), 200
    except ValueError as e:
        out, status = jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        out, status = jsonify({"error": "执行失败：%s" % str(e)[:160]}), 502
    except Exception as e:
        out, status = jsonify({"error": "执行失败：%s" % str(e)[:160]}), 500
    out.status_code = status
    return out


@bp.route("/api/admin/prd/generate", methods=["POST"])
@require_admin
@limiter(6, 60, message="生成太频繁，请稍后再试")
def api_admin_prd_generate():
    """填「公司 + 业务介绍」→ 生成一份面向该客户的《AI 智能体平台功能需求 PRD》。

    mode=guide 引导（客户不懂，先给草稿+澄清问题）；mode=normalize 规范化（整理客户原始需求）。
    生成前会用知识库检索做行业接地（空库自动降级）。LLM 调用较慢，前端需 loading。
    """
    if not kb_prd.has_api_key():
        return jsonify({"error": "未配置 DASHSCOPE_API_KEY 环境变量，无法生成 PRD"}), 400
    payload = request.get_json(force=True, silent=True) or {}
    try:
        result = kb_prd.generate_prd(_kb, payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": "生成失败：%s" % str(e)[:160]}), 502
    except Exception as e:
        return jsonify({"error": "生成失败：%s" % str(e)[:160]}), 500
    return jsonify(result)


@bp.route("/api/agents", methods=["GET"])
def api_agents():
    """公开智能体注册表：status=live 的会被首页渲染成可体验入口。"""
    return jsonify(agents.list_agents(only_live=True))


@bp.route("/api/agents/dispatch", methods=["POST"])
@limiter(5, 3600, bucket="agent_dispatch", message="请求太频繁，请稍后再试")
def api_agents_dispatch():
    """planner 派发：任务文本 → triggers 关键词路由到 live 智能体。

    body: {task, auto_run?, payload?}；auto_run=true 时代为执行并带回结果。
    """
    payload = request.get_json(force=True, silent=True) or {}
    task = (payload.get("task") or "").strip()
    if not task:
        return jsonify({"error": "task 不能为空"}), 400
    agent = agents.route_task(task)
    if agent is None:
        return jsonify({"ok": False, "matched": None,
                        "message": "暂无可处理该任务的智能体"}), 404
    out = {"ok": True, "matched": agent.id, "agent": agent.meta()}
    if payload.get("auto_run"):
        # 代跑结果作为子对象内嵌（代跑失败时 run 里是 {"error": ...}，外层仍 200）
        out["run"] = _run_agent(agent, payload.get("payload") or {}).get_json()
    return jsonify(out), 200


@bp.route("/api/agents/<agent_id>/run", methods=["POST"])
def api_agent_run(agent_id):
    """通用公开运行端点：注册表里 status=live 的智能体均可经此调用，按 agent 限流。"""
    agent = agents.get_agent(agent_id)
    if agent is None or agent.status != "live":
        return jsonify({"error": "智能体不存在或未上线"}), 404
    if rate_limited(request.remote_addr, limit=5, window=3600,
                    bucket="agent_%s" % agent_id):
        return jsonify({"error": "体验次数已达上限（每 IP 每小时 5 次），请稍后再试"}), 429
    if not agent.available():
        return jsonify({"error": "智能体暂不可用，请稍后再试"}), 503
    payload = request.get_json(force=True, silent=True) or {}
    return _run_agent(agent, payload)


@bp.route("/api/agents/prd/run", methods=["POST"])
def api_agents_prd_run_legacy():
    """A1 兼容路径：旧前端包硬编码此地址；返回 A1 的扁平结果形状。"""
    agent = agents.get_agent("prd-advisor")
    if agent is None or agent.status != "live":
        return jsonify({"error": "智能体不存在或未上线"}), 404
    if rate_limited(request.remote_addr, limit=5, window=3600, bucket="agent_prd"):
        return jsonify({"error": "体验次数已达上限（每 IP 每小时 5 次），请稍后再试"}), 429
    if not agent.available():
        return jsonify({"error": "智能体暂不可用，请稍后再试"}), 503
    payload = request.get_json(force=True, silent=True) or {}
    res = _run_agent(agent, payload)
    flat = res.get_json()
    if res.status_code == 200 and isinstance(flat, dict) and "result" in flat:
        flat = dict(flat["result"]) if isinstance(flat["result"], dict) else flat["result"]
    return jsonify(flat), res.status_code
