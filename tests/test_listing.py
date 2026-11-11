# -*- coding: utf-8 -*-
"""上架物料流水线（A11）单测：四阶段流水线 + 账本 + 审批 + 导出（离线、不触发真 LLM）。

运行：py tests/test_listing.py

打桩说明：
- listing.chat → 假文案（商品文案阶段）；
- order_catcher / scene_director 的 chat → 假实现（实测与分镜阶段真跑 agent.run 链路）；
- 数据目录重定向到临时目录，不污染本地 data/；
- 流水线走后台线程，测试轮询等待终态。
"""
import json
import os
import sys
import tempfile
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

for mod in ("faiss", "bs4", "bs4.BeautifulSoup"):
    try:
        __import__(mod)
    except ImportError:
        sys.modules[mod] = type(sys)("fake_" + mod)
if "bs4" in sys.modules and not hasattr(sys.modules["bs4"], "BeautifulSoup"):
    sys.modules["bs4.BeautifulSoup"] = type(sys)("fake_bs")
    sys.modules["bs4"].BeautifulSoup = object

import app  # noqa: E402
import listing as ls  # noqa: E402
import agents.order_catcher as oc  # noqa: E402
import agents.scene_director as sd  # noqa: E402

_TMP = tempfile.mkdtemp(prefix="listing_test_")
ls._data_dir = _TMP
ls._load_json = app.load_json
ls._save_json = app.save_json

c = app.app.test_client()
PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  -", name)
    else:
        FAIL += 1
        print("  FAIL-", name, extra)


def H():
    TOKEN = app.hash_password(app.ADMIN_ACCOUNT + app.ADMIN_PASSWORD
                              + app.SECRET_KEY)[:32]
    return {"Authorization": "Bearer " + TOKEN}


GOOD_ORDER = {"order_no": "PO-1", "customer": "华阳汽车零部件", "contact": "李工 138",
              "products": [{"name": "法兰盘", "spec": "DN50", "qty": "2000", "unit": "件"}],
              "delivery_date": "2026-12-20", "notes": "木箱包装", "missing": []}

GOOD_SCENES = {"brand": "华阳汽车零部件", "style": "等距蓝白",
               "scenes": [{"no": "01", "title": "厂区", "desc": "鸟瞰", "still_prompt": "p1", "camera_move": "俯冲"},
                          {"no": "02", "title": "产线", "desc": "机械臂", "still_prompt": "p2", "camera_move": "穿入"},
                          {"no": "03", "title": "质检", "desc": "视觉检测", "still_prompt": "p3", "camera_move": "推近"},
                          {"no": "04", "title": "仓储", "desc": "AGV", "still_prompt": "p4", "camera_move": "拉出"}]}

GOOD_COPY = {"title": "AI 订单自动录入智能体", "tagline": "粘贴即出工单，防漏单",
             "features": ["邮件订单抽取", "缺失字段提示"],
             "usage": ["粘贴订单原文", "点击抽取工单", "核对缺失字段"],
             "scenarios": ["汽车零部件厂销售内勤", "电子组装厂计划员", "模具厂接单员"],
             "audience": "50-500 人制造企业"}

oc.kb_prd.has_api_key = lambda: True
sd.kb_prd.has_api_key = lambda: True

_ROUTES = {"order": json.dumps(GOOD_ORDER, ensure_ascii=False),
           "scene": json.dumps(GOOD_SCENES, ensure_ascii=False)}


def fake_chat(messages, temperature=0.3, timeout=60):
    sys_txt = messages[0]["content"]
    if "分镜师" in sys_txt:
        return _ROUTES["scene"]
    if "订单录入助手" in sys_txt:
        return _ROUTES["order"]
    return json.dumps(GOOD_COPY, ensure_ascii=False)


oc.chat = fake_chat
sd.chat = fake_chat
ls.chat = fake_chat


def wait_done(lid, timeout=10):
    for _ in range(int(timeout * 10)):
        row = ls._find(lid)
        if row and row.get("status") in ("done", "failed"):
            return row
        time.sleep(0.1)
    return ls._find(lid)


def run_all():
    print("== 1. 权限与入参校验 ==")
    r = c.get("/api/admin/listings")
    check("未带 token 401", r.status_code == 401)
    r = c.post("/api/admin/listings", json={}, headers=H())
    check("缺 agent_id 400", r.status_code == 400)
    r = c.post("/api/admin/listings", json={"agent_id": "ghost"}, headers=H())
    check("幽灵产品 404", r.status_code == 404)

    print("== 2. 流水线四阶段 ==")
    r = c.post("/api/admin/listings", json={"agent_id": "order-catcher"}, headers=H())
    check("创建 202", r.status_code == 202, r.get_data(as_text=True)[:200])
    lid = r.get_json()["listing"]["id"]
    check("初始状态 running", r.get_json()["listing"]["status"] == "running")
    row = wait_done(lid)
    check("流水线 done", row["status"] == "done", json.dumps(row.get("stages"), ensure_ascii=False)[:200])
    st = row["stages"]
    check("四阶段全 done", all(st[k]["status"] == "done" for k in ls._STAGES))
    check("体检通过", st["health"]["data"]["ok"] is True)
    m = st["metrics"]["data"]
    check("实测 3 组全成功", m["total"] == 3 and m["success"] == 3)
    check("成功率 1.0", m["success_rate"] == 1.0)
    check("平均置信度取到值", isinstance(m["avg_confidence"], (int, float)))
    check("平均耗时字段为整数（打桩即时，允许 0）", isinstance(m["avg_latency_ms"], int) and m["avg_latency_ms"] >= 0)
    check("输出完整度在 0-1", 0 < m["avg_coverage"] <= 1.0)
    check("样例明细留摘要", len(m["samples"]) == 3 and "input" in m["samples"][0])
    check("文案落库", st["copy"]["data"]["title"] == GOOD_COPY["title"])
    check("分镜 4 场景", len(st["storyboard"]["data"]["scenes"]) == 4)

    print("== 3. 账本与详情 ==")
    led = json.load(open(os.path.join(_TMP, "listings.json"), encoding="utf-8"))
    check("账本落了 1 条", len(led) == 1 and led[0]["agent_id"] == "order-catcher")
    r = c.get("/api/admin/listings", headers=H())
    check("列表 200 且带阶段状态", r.status_code == 200 and
          r.get_json()[0]["stages"]["metrics"] == "done")
    r = c.get("/api/admin/listings/" + lid, headers=H())
    check("详情 200 含 stages 数据", r.status_code == 200 and
          r.get_json()["stages"]["copy"]["data"]["tagline"] == GOOD_COPY["tagline"])
    check("详情带导出地址", r.get_json()["export_url"].endswith("/export"))
    r = c.get("/api/admin/listings/nope", headers=H())
    check("详情不存在 404", r.status_code == 404)

    print("== 4. 审批闸门 ==")
    r = c.post("/api/admin/listings/%s/review" % lid, json={"action": "maybe"}, headers=H())
    check("非法 action 400", r.status_code == 400)
    r = c.post("/api/admin/listings/%s/review" % lid, json={"action": "reject"}, headers=H())
    check("驳回无理由 400", r.status_code == 400)
    r = c.post("/api/admin/listings/%s/review" % lid, json={"action": "reject", "note": "数据口径要改"}, headers=H())
    check("驳回成功", r.status_code == 200 and r.get_json()["listing"]["status"] == "rejected")
    r = c.post("/api/admin/listings/%s/review" % lid, json={"action": "approve"}, headers=H())
    check("已决不可重复审批 409", r.status_code == 409)
    r = c.get("/api/admin/listings/%s/export" % lid, headers=H())
    check("未通过审批不可导出 409", r.status_code == 409)

    print("== 5. 通过审批并导出 ==")
    r = c.post("/api/admin/listings", json={"agent_id": "scene-director"}, headers=H())
    lid2 = r.get_json()["listing"]["id"]
    row2 = wait_done(lid2)
    check("第二个产品流水线 done", row2["status"] == "done",
          json.dumps(row2.get("error"), ensure_ascii=False))
    r = c.post("/api/admin/listings/%s/review" % lid2, json={"action": "approve", "note": "可用"}, headers=H())
    check("审批通过", r.get_json()["listing"]["status"] == "approved")
    r = c.get("/api/admin/listings/%s/export" % lid2, headers=H())
    check("导出 200", r.status_code == 200)
    md = r.get_data(as_text=True)
    check("导出是 Markdown 物料包", md.startswith("# ") and "上架物料包" in md)
    check("含体验地址", "47.115.223.159:8804" in md)
    check("含效果数据表", "成功率" in md and "平均置信度" in md)
    check("含文案三段", "核心功能" in md and "操作说明" in md and "应用场景" in md)
    check("含分镜脚本", "宣传视频分镜脚本" in md and "静帧提示词" in md)
    check("含审批留痕", "approve" in md)
    check("数据口径免责声明在文内", "非客户产线数据" in md)
    check("附件名带产品 id", "scene-director" in r.headers.get("Content-Disposition", ""))

    print("== 6. 阶段失败收敛 ==")
    def broken_chat(messages, temperature=0.3, timeout=60):
        return "模型抽风，不是 JSON"
    ls.chat = broken_chat
    r = c.post("/api/admin/listings", json={"agent_id": "order-catcher"}, headers=H())
    lid3 = r.get_json()["listing"]["id"]
    row3 = wait_done(lid3)
    check("文案阶段 failed", row3["stages"]["copy"]["status"] == "failed")
    check("前序阶段仍保留数据", row3["stages"]["metrics"]["data"]["success"] == 3)
    check("非致命阶段不影响整单完成", row3["status"] == "done")
    ls.chat = fake_chat

    class DeadAgent:
        id = "order-catcher"
        name = "订单机器人"
        role = "x"
        desc = "y"
        caps = []
        def available(self):
            return False
        def run(self, payload):
            raise AssertionError("不应被调")
    row4 = {"id": "t4", "agent_id": "order-catcher", "agent_name": "订单机器人",
            "status": "running", "created_at": ls._now(), "stages": {}}
    ls.run_pipeline(row4, agent=DeadAgent())
    check("引擎不可用 → 整单 failed", row4["status"] == "failed", json.dumps(row4, ensure_ascii=False)[:250])
    check("体检记录了不可用", any(c2["ok"] is False for c2 in row4["stages"]["health"]["data"]["checks"]))
    check("后续阶段标记 skipped", row4["stages"]["copy"]["status"] == "skipped"
          and row4["stages"]["storyboard"]["status"] == "skipped")
    check("失败原因写成人话", "体检未通过" in (row4.get("error") or ""))

    print("== 7. 样例集覆盖 ==")
    from agents.registry import list_agents
    ids = [a["id"] for a in list_agents(only_live=True)]
    check("五个 live 产品都有内置样例集", all(i in ls.SAMPLES for i in ids), str(ids))
    check("每产品至少 3 组样例", all(len(ls.SAMPLES[i]) >= 3 for i in ids))


if __name__ == "__main__":
    run_all()
    print("\n%d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
