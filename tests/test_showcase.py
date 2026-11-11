# -*- coding: utf-8 -*-
"""对外示例（A12）单测：候选池留档 + 后台挑选 + 公开示例接口（离线，不触发真 LLM）。

运行：py tests/test_showcase.py

打桩说明：
- 数据目录重定向到临时目录，不污染本地 data/；
- showcase._read_candidates 换成假候选池（真实候选由 listing 实测阶段写入，
  本测试只验挑选与出网形状，不重跑流水线）；
- listing 候选池部分用真 _save_candidate/read_candidates，验覆盖式留档。
"""
import os
import sys
import tempfile

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
import showcase as sc  # noqa: E402

_TMP = tempfile.mkdtemp(prefix="showcase_test_")
sc._data_dir = _TMP
sc._load_json = app.load_json
sc._save_json = app.save_json
ls._data_dir = _TMP
ls._load_json = app.load_json
ls._save_json = app.save_json

AID = "order-catcher"
CANDS = {
    AID: [
        {"no": 1, "input": {"text": "订单原文一"}, "output": {"customer": "华阳", "products": []},
         "confidence": 0.8, "coverage": 1.0, "latency_ms": 2900, "ts": "2026-11-11T10:00:00"},
        {"no": 3, "input": {"text": "订单原文三"}, "output": {"customer": "北方重工", "products": []},
         "confidence": 0.4, "coverage": 0.5, "latency_ms": 3100, "ts": "2026-11-11T10:01:00"},
    ],
}
sc._read_candidates = lambda agent_id: CANDS.get(agent_id, [])

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


def _raises(fn):
    try:
        fn()
        return False
    except ValueError:
        return True


print("\n[1] 候选池：实测输出留档（listing 侧）")
ls._save_candidate(AID, {"no": 1, "input": {"text": "甲"}, "output": {"a": 1},
                         "confidence": 0.5, "coverage": 0.5, "latency_ms": 100,
                         "listing_id": "job1", "ts": "2026-11-11T09:00:00"})
ls._save_candidate(AID, {"no": 2, "input": {"text": "乙"}, "output": {"b": 2},
                         "confidence": 0.6, "coverage": 0.6, "latency_ms": 200,
                         "listing_id": "job1", "ts": "2026-11-11T09:05:00"})
ls._save_candidate(AID, {"no": 1, "input": {"text": "甲重跑"}, "output": {"a": 9},
                         "confidence": 0.9, "coverage": 1.0, "latency_ms": 300,
                         "listing_id": "job2", "ts": "2026-11-11T11:00:00"})
rows = ls.read_candidates(AID)
check("同序号重跑覆盖不膨胀", len(rows) == 2, str(len(rows)))
check("留的是最新一轮", rows[0]["output"] == {"a": 9} and rows[0]["listing_id"] == "job2",
      str(rows[0]))
check("按序号升序", [r["no"] for r in rows] == [1, 2], str([r["no"] for r in rows]))
ls._save_candidate(AID, {"no": 4, "input": {"text": "丁"}, "output": None,
                         "confidence": None, "coverage": 0.0, "latency_ms": 0,
                         "listing_id": "job2", "ts": "2026-11-11T11:05:00"})
check("没跑出来的不进候选池", len(ls.read_candidates(AID)) == 2,
      str(ls.read_candidates(AID)))

print("\n[2] 挑选：标签闸门与覆盖式写入")
check("非法标签报错", _raises(lambda: sc.set_showcase(AID, 1, "最佳")))
check("候选池没有的序号报错", _raises(lambda: sc.set_showcase(AID, 99, "常规")))
one = sc.set_showcase(AID, 1, "常规")
check("写入带回输入输出", one["output"] == {"customer": "华阳", "products": []}
      and one["input"] == {"text": "订单原文一"}, str(one))
two = sc.set_showcase(AID, 3, "缺字段")
check("两格都在", [r["label"] for r in sc.read_showcases(AID)] == ["常规", "缺字段"],
      str(sc.read_showcases(AID)))
sc.set_showcase(AID, 3, "常规")
after = sc.read_showcases(AID)
check("同标签重设是覆盖不是追加", len(after) == 2 and after[0]["no"] == 3, str(after))


print("\n[3] 公开接口：只给展示需要的键")
r = c.get("/api/agents/%s/showcases" % AID)
check("公开接口 200", r.status_code == 200, str(r.status_code))
data = r.get_json()
check("形状：agent_id + showcases", set(data) == {"agent_id", "showcases"}, str(data))
item = data["showcases"][0]
check("对外键收敛（无 no/ts）",
      set(item) == {"label", "input", "output", "confidence", "coverage", "latency_ms"},
      str(sorted(item)))
check("未知产品 404", c.get("/api/agents/nope/showcases").status_code == 404)
check("未知产品不泄内容", "showcases" not in (c.get("/api/agents/nope/showcases").get_json() or {}))

print("\n[4] 管理接口：鉴权、候选与 in_use")
check("未登录列表 401", c.get("/api/admin/showcases?agent_id=" + AID).status_code == 401)
check("未登录设置 401", c.post("/api/admin/showcases", json={"agent_id": AID, "no": 1,
                                                            "label": "常规"}).status_code == 401)
r = c.get("/api/admin/showcases?agent_id=" + AID, headers=H())
check("管理列表 200", r.status_code == 200, str(r.status_code))
adm = r.get_json()
check("带出候选池与标签格", set(adm) == {"agent_id", "labels", "showcases", "candidates"},
      str(sorted(adm)))
check("候选池与标签格一起给出",
      [x["no"] for x in adm["candidates"]] == [1, 3], str(adm["candidates"]))
check("已定为示例的候选有 in_use 标记",
      [x.get("in_use") for x in adm["candidates"]] == [False, True], str(adm["candidates"]))
r = c.post("/api/admin/showcases", json={"agent_id": AID, "no": 1, "label": "缺字段"},
           headers=H())
check("后台挑选 200", r.status_code == 200, str(r.get_json()))
check("挑完公开接口立刻可见",
      c.get("/api/agents/%s/showcases" % AID).get_json()["showcases"][1]["label"] == "缺字段")
r = c.post("/api/admin/showcases", json={"agent_id": AID, "no": 1, "label": "瞎写"}, headers=H())
check("非法标签 400", r.status_code == 400, str(r.get_json()))
r = c.post("/api/admin/showcases", json={"agent_id": AID, "no": "abc", "label": "常规"},
           headers=H())
check("缺序号 400", r.status_code == 400, str(r.get_json()))
r = c.post("/api/admin/showcases", json={"agent_id": "nope", "no": 1, "label": "常规"},
           headers=H())
check("未知产品 404", r.status_code == 404)

print("\n[5] 出厂种子：后台没挑过时也不空着")
fresh = tempfile.mkdtemp(prefix="showcase_seed_")
sc._data_dir = fresh
app.save_json(os.path.join(fresh, "showcases_seed.json"),
              {AID: [{"label": "常规", "no": 7, "input": {"text": "种子"},
                     "output": {"from": "seed"}, "confidence": 0.7, "coverage": 1.0,
                     "latency_ms": 1200, "ts": "2026-11-01T00:00:00"}]})
seeded = sc.read_showcases(AID)
check("空库回落到种子", len(seeded) == 1 and seeded[0]["output"] == {"from": "seed"},
      str(seeded))
sc.set_showcase(AID, 3, "缺字段")
merged = sc.read_showcases(AID)
check("首次挑选不清空种子来的另一格",
      [r["label"] for r in merged] == ["常规", "缺字段"], str(merged))
check("挑选结果落在运行时文件（种子不动）",
      os.path.exists(os.path.join(fresh, "showcases.json")))

print("\n[6] 样例集：知识管家有「库内无依据」那条")
kb = ls.SAMPLES.get("kb-assistant") or []
check("知识管家至少 4 组样例", len(kb) >= 4, str(len(kb)))
check("含一条知识库里没有的问题",
      any("报销" in (s.get("question") or "") for s in kb), str(kb))

print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
