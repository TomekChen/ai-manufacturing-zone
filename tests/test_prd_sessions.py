# -*- coding: utf-8 -*-
"""售前方案会话沉淀（A4-T1）：保存/追加版本/读取（离线，不调 LLM）。

运行：py tests/test_prd_sessions.py
"""
import os
import sys
import tempfile

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

import app  # noqa: E402

# 会话文件重定向到临时目录，不污染本地 data/
_TMP = tempfile.mkdtemp(prefix="prd_session_test_")
app.PRD_SESSIONS_FILE = os.path.join(_TMP, "prd_sessions.json")

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


def clear_bucket():
    app._ask_limits.setdefault("prd_session", {}).pop("127.0.0.1", None)


def read_file():
    return app.load_json(app.PRD_SESSIONS_FILE, [])


V1_RESULT = {"prd": "# 方案 v1\n第一版内容", "grounded": True, "hits": 8,
             "mode": "guide", "model": "stub", "sources": ["知识A", "知识B"]}
V2_RESULT = {"prd": "# 方案 v2\n第二版内容", "grounded": True, "hits": 10,
             "mode": "normalize", "model": "stub", "sources": ["知识C"]}
INPUTS = {"company": "某某精密制造", "industry": "汽车零部件",
          "business": "主营变速箱壳体加工", "mode": "guide", "raw_requirements": ""}


def test_save_and_versions():
    print("\n[会话保存与版本追加]")
    clear_bucket()

    r = c.post("/api/prd-sessions", json={"inputs": INPUTS, "result": V1_RESULT})
    body = r.get_json() or {}
    check("首次保存 200", r.status_code == 200, str(body))
    check("返回 session_id/version=1",
          bool(body.get("session_id")) and body.get("version") == 1)
    sid = body.get("session_id")

    r2 = c.post("/api/prd-sessions",
                json={"session_id": sid, "inputs": INPUTS, "result": V2_RESULT})
    body2 = r2.get_json() or {}
    check("同会话二次保存 200", r2.status_code == 200, str(body2))
    check("version 递增到 2", body2.get("version") == 2 and body2.get("session_id") == sid)

    rows = read_file()
    check("落盘 1 个会话（非 2 条记录）", len(rows) == 1, "rows=%d" % len(rows))
    sess = rows[0]
    check("会话标题默认取公司名", sess.get("title") == INPUTS["company"])
    check("版本数组长度 2", len(sess.get("versions", [])) == 2)
    check("版本号 1/2 递增", [v.get("no") for v in sess["versions"]] == [1, 2])
    check("v1 内容未被覆盖（追加不修改）",
          sess["versions"][0]["result"]["prd"] == V1_RESULT["prd"])
    check("每版记录了输入快照",
          sess["versions"][0]["inputs"]["company"] == INPUTS["company"])
    return sid


def test_get_session(sid):
    print("\n[会话读取]")
    r = c.get("/api/prd-sessions/%s" % sid)
    body = r.get_json() or {}
    check("读取 200", r.status_code == 200, str(body)[:120])
    check("读取到标题与 2 个版本",
          body.get("title") == INPUTS["company"] and len(body.get("versions", [])) == 2)
    check("读取内容与落盘一致（v2 prd 原样）",
          body["versions"][1]["result"]["prd"] == V2_RESULT["prd"])

    r404 = c.get("/api/prd-sessions/not-exist-xyz")
    check("不存在的会话 404", r404.status_code == 404)


def test_validation():
    print("\n[入参校验]")
    clear_bucket()
    r = c.post("/api/prd-sessions", json={"inputs": INPUTS, "result": {"prd": ""}})
    check("空 prd 拒绝 400", r.status_code == 400)
    r2 = c.post("/api/prd-sessions", json={"inputs": {}, "result": V1_RESULT})
    check("缺公司名（无标题可命名）拒绝 400", r2.status_code == 400)
    r3 = c.post("/api/prd-sessions",
                json={"session_id": "ghost", "inputs": INPUTS, "result": V1_RESULT})
    body3 = r3.get_json() or {}
    check("未知 session_id 新开一个会话而非 500",
          r3.status_code == 200 and body3.get("version") == 1
          and body3.get("session_id") != "ghost")


def test_bucket_isolated():
    print("\n[限流桶隔离]")
    clear_bucket()
    app._ask_limits.setdefault("demo_booking", {}).pop("127.0.0.1", None)
    # 打满会话留尾上限（限流 30 次/小时，循环里定期清桶绕开）
    for i in range(120):
        if i % 25 == 0:
            clear_bucket()
        c.post("/api/prd-sessions", json={"inputs": INPUTS, "result": V1_RESULT})
    clear_bucket()
    for _ in range(30):  # 打满 prd_session 桶（30 次/小时）
        c.post("/api/prd-sessions", json={"inputs": INPUTS, "result": V1_RESULT})
    r = c.post("/api/prd-sessions", json={"inputs": INPUTS, "result": V1_RESULT})
    check("打满后 429", r.status_code == 429)
    rb = c.post("/api/demo/booking", json={"name": "张三", "contact": "13800000000"})
    check("打满 prd_session 桶不影响 demo_booking 桶", rb.status_code == 200)
    check("会话留尾上限 100（不会无限膨胀）", len(read_file()) == 100,
          "rows=%d" % len(read_file()))


if __name__ == "__main__":
    sid = test_save_and_versions()
    test_get_session(sid)
    test_validation()
    test_bucket_isolated()
    print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
