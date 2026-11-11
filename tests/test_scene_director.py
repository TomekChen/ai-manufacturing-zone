# -*- coding: utf-8 -*-
"""场景分镜师（第五个上线智能体）单测：注册表 + 分镜契约 + 通用 run 端点 + dispatch 路由（离线、不触发真 LLM）。

运行：py tests/test_scene_director.py

打桩：把 agents.scene_director.chat 换成假实现；LLM 失败/坏 JSON/超量场景的收敛行为也要覆盖。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

# 本机缺库兜底（faiss/bs4）
for mod in ("faiss", "bs4", "bs4.BeautifulSoup"):
    try:
        __import__(mod)
    except ImportError:
        sys.modules[mod] = type(sys)("fake_" + mod)
if "bs4" in sys.modules and not hasattr(sys.modules["bs4"], "BeautifulSoup"):
    sys.modules["bs4.BeautifulSoup"] = type(sys)("fake_bs")
    sys.modules["bs4"].BeautifulSoup = object

import agents  # noqa: E402  import 即注册
import app  # noqa: E402
import agents.scene_director as sd  # noqa: E402
from agents.registry import get_agent, route_task  # noqa: E402

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  -", name)
    else:
        FAIL += 1
        print("  FAIL-", name, extra)


GOOD = {"brand": "华阳精工", "style": "白灰基调等距立体，蓝色点缀，柔和摄影棚光",
        "scenes": [
            {"no": "01", "title": "厂区全貌", "desc": "智能制造园区鸟瞰", "still_prompt": "isometric park overview", "camera_move": "高空俯冲进场"},
            {"no": "02", "title": "研发设计中心", "desc": "工程师与大屏", "still_prompt": "isometric R&D interior", "camera_move": "穿入研发楼内部"},
            {"no": "03", "title": "智能产线", "desc": "机械臂产线", "still_prompt": "isometric production line", "camera_move": "滑入车间"},
            {"no": "04", "title": "AI 质检工位", "desc": "缺陷检测大屏", "still_prompt": "isometric inspection", "camera_move": "推近质检工位"},
        ]}

GOOD_JSON = __import__("json").dumps(GOOD, ensure_ascii=False)

# available() 走 rag.prd.has_api_key，与 app 同一模块对象，桩一处生效
sd.kb_prd.has_api_key = lambda: True

FENCED = "```json\n%s\n```" % GOOD_JSON

c = app.app.test_client()


def run_all():
    print("== 1. 注册表与元数据 ==")
    ag = get_agent("scene-director")
    check("已注册", ag is not None)
    check("status=live", ag.status == "live")
    check("meta.ui=scenes", ag.meta().get("ui") == "scenes")
    check("endpoint 指向通用 run", ag.endpoint == "/api/agents/scene-director/run")
    check("list_agents(only_live) 含 scene-director",
          any(x["id"] == "scene-director" for x in agents.list_agents(only_live=True)))
    check("route_task：'分镜' → scene-director", route_task("帮华阳精工做品牌分镜") is ag)

    print("== 2. run 契约（打桩 chat） ==")
    sd.chat = lambda messages, temperature=0.4, timeout=60: GOOD_JSON
    r = ag.run({"text": "华阳精工，汽车零部件精密制造"})
    check("ok=True", r["ok"] is True)
    check("agent_id", r["agent_id"] == "scene-director")
    check("brand 透传", r["result"]["brand"] == "华阳精工")
    check("4 场景", len(r["result"]["scenes"]) == 4)
    check("置信度 0.8（场景数在 4-8）", r["confidence"] == 0.8)

    print("== 3. 入参校验 ==")
    try:
        ag.run({"text": "   "})
        check("空输入 ValueError", False)
    except ValueError as e:
        check("空输入 ValueError", "品牌" in str(e) or "内容" in str(e))

    print("== 4. LLM 异常收敛 ==")
    sd.chat = lambda messages, temperature=0.4, timeout=60: "抱歉，我无法输出 JSON"
    try:
        ag.run({"text": "华阳精工"})
        check("非 JSON 收敛 RuntimeError", False)
    except RuntimeError as e:
        check("非 JSON 收敛 RuntimeError", "未产出" in str(e) or "结构化" in str(e))
    sd.chat = lambda messages, temperature=0.4, timeout=60: FENCED
    r = ag.run({"text": "华阳精工"})
    check("```json 围栏可解析", len(r["result"]["scenes"]) == 4)

    class Boom(Exception):
        pass

    def boom(messages, temperature=0.4, timeout=60):
        raise Boom("网络炸了")

    sd.chat = boom
    try:
        ag.run({"text": "华阳精工"})
        check("chat 抛异常收敛 RuntimeError", False)
    except RuntimeError as e:
        check("chat 抛异常收敛 RuntimeError", "网络炸了" in str(e))

    print("== 5. 超量场景截断 ==")
    many = dict(GOOD)
    many["scenes"] = GOOD["scenes"] * 3
    sd.chat = lambda messages, temperature=0.4, timeout=60: __import__("json").dumps(many, ensure_ascii=False)
    r = ag.run({"text": "华阳精工"})
    check("12 场景截到 8", len(r["result"]["scenes"]) == 8)
    check("截断后 8 场景仍在 4-8 区间，置信度 0.8", r["confidence"] == 0.8)

    print("== 5b. 场景数不足 → 置信度降档 ==")
    few = dict(GOOD)
    few["scenes"] = GOOD["scenes"][:3]
    sd.chat = lambda messages, temperature=0.4, timeout=60: __import__("json").dumps(few, ensure_ascii=False)
    r = ag.run({"text": "华阳精工"})
    check("3 场景保留", len(r["result"]["scenes"]) == 3)
    check("3 场景置信度 0.5", r["confidence"] == 0.5)

    print("== 6. 通用 run 端点 ==")
    sd.chat = lambda messages, temperature=0.4, timeout=60: GOOD_JSON
    r = c.post("/api/agents/scene-director/run", json={"text": "华阳精工"})
    check("端点 200", r.status_code == 200, r.get_data(as_text=True)[:200])
    check("契约形状", r.get_json()["result"]["brand"] == "华阳精工")
    r = c.post("/api/agents/scene-director/run", json={})
    check("空 payload 400", r.status_code == 400)
    r = c.post("/api/agents/ghost/run", json={"text": "x"})
    check("幽灵 agent 404", r.status_code == 404)
    r = c.post("/api/agents/dispatch", json={"task": "请给华阳精工写一版漫游分镜脚本"})
    check("dispatch 路由命中 scene-director", r.status_code == 200 and
          r.get_json().get("routed") == "scene-director" or
          (r.status_code == 200 and "scene-director" in r.get_data(as_text=True)))


if __name__ == "__main__":
    run_all()
    print("\n%d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
