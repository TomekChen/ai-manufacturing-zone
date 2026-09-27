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
import prd_sessions  # noqa: E402

# 会话文件重定向到临时目录，不污染本地 data/（R2 起路径归 prd_sessions 模块管）
_TMP = tempfile.mkdtemp(prefix="prd_session_test_")
prd_sessions._data_dir = _TMP

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
    return prd_sessions._load_json(prd_sessions._sessions_file(), [])


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


def test_share_page(sid):
    print("\n[只读分享页 /s/<id>]")
    r = c.get("/s/%s" % sid)
    html = r.get_data(as_text=True)
    check("分享页 200", r.status_code == 200)
    check("Content-Type 是 HTML", "text/html" in (r.content_type or ""))
    check("页面含会话标题", INPUTS["company"] in html)
    check("页面含 v1 与 v2 方案正文",
          V1_RESULT["prd"] in html and V2_RESULT["prd"] in html)
    check("无编辑/运行入口（只读）", "/api/prd-sessions\" POST" not in html and "生成 PRD" not in html)
    r404 = c.get("/s/not-exist-xyz")
    check("不存在的会话 404", r404.status_code == 404)

    # XSS：prd 里的 HTML 必须被转义
    clear_bucket()
    evil = {"prd": "<script>alert(1)</script>方案", "grounded": False,
            "hits": 0, "mode": "guide", "model": "stub", "sources": []}
    re_ = c.post("/api/prd-sessions", json={"inputs": INPUTS, "result": evil})
    sid2 = (re_.get_json() or {}).get("session_id")
    r2 = c.get("/s/%s" % sid2)
    html2 = r2.get_data(as_text=True)
    check("分享页 script 标签被转义", "<script>alert" not in html2
          and "&lt;script&gt;" in html2)


def test_admin_list(sid):
    print("\n[后台会话列表]")
    r = c.get("/api/admin/prd-sessions")
    check("未带 token 401", r.status_code == 401)
    TOKEN = app.hash_password(app.ADMIN_ACCOUNT + app.ADMIN_PASSWORD
                              + app.SECRET_KEY)[:32]
    r2 = c.get("/api/admin/prd-sessions", headers={"Authorization": "Bearer " + TOKEN})
    rows = r2.get_json() or []
    check("带 token 200", r2.status_code == 200)
    check("返回摘要列表且含刚才的会话",
          any(x.get("id") == sid for x in rows))
    check("摘要带 version_count 不带全文",
          all("versions" not in x and isinstance(x.get("version_count"), int)
              for x in rows))


class FakeKB:
    """知识库打桩：记录 add_text 调用，返回假 doc。"""

    def __init__(self):
        self.calls = []

    def add_text(self, text, title, url="", doc_type="upload",
                 status="pending", chunking=None):
        self.calls.append({"text": text, "title": title, "url": url,
                           "doc_type": doc_type, "status": status})
        return {"id": "doc_" + str(len(self.calls)), "title": title,
                "status": status}


def test_ingest(sid):
    print("\n[A4.5 know-how 入库飞轮]")
    TOKEN = app.hash_password(app.ADMIN_ACCOUNT + app.ADMIN_PASSWORD
                              + app.SECRET_KEY)[:32]
    H = {"Authorization": "Bearer " + TOKEN}
    fake = FakeKB()

    prd_sessions._kb = None
    r0 = c.post("/api/admin/prd-sessions/%s/ingest" % sid, headers=H)
    check("知识库未装配 503", r0.status_code == 503)

    prd_sessions._kb = fake
    r = c.post("/api/admin/prd-sessions/%s/ingest" % sid)
    check("未带 token 401", r.status_code == 401)
    check("未鉴权不打知识库", len(fake.calls) == 0)

    r404 = c.post("/api/admin/prd-sessions/ghost/ingest", headers=H)
    check("未知会话 404", r404.status_code == 404)

    r = c.post("/api/admin/prd-sessions/%s/ingest" % sid, headers=H)
    body = r.get_json() or {}
    check("入库 200 ok", r.status_code == 200 and body.get("ok") is True, str(body))
    check("知识库收到 1 次且 status=pending（人工审核把关）",
          len(fake.calls) == 1 and fake.calls[0]["status"] == "pending")
    check("doc_type=session 且 url 指回分享页",
          fake.calls[0]["doc_type"] == "session"
          and fake.calls[0]["url"] == "/s/%s" % sid)
    check("正文取最新版 v2 而非 v1",
          V2_RESULT["prd"] in fake.calls[0]["text"]
          and V1_RESULT["prd"] not in fake.calls[0]["text"])
    check("正文带来源与版本标注", "售前方案会话沉淀" in fake.calls[0]["text"])

    r2 = c.post("/api/admin/prd-sessions/%s/ingest" % sid, headers=H)
    check("重复入库 409 幂等（不产生重复文档）",
          r2.status_code == 409 and len(fake.calls) == 1)

    rows = c.get("/api/admin/prd-sessions", headers=H).get_json() or []
    me = next((x for x in rows if x.get("id") == sid), None)
    check("列表摘要标记已入库", bool(me and me.get("ingested")))
    prd_sessions._kb = None


if __name__ == "__main__":
    sid = test_save_and_versions()
    test_get_session(sid)
    test_validation()
    test_share_page(sid)
    test_admin_list(sid)
    test_ingest(sid)
    test_bucket_isolated()
    print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
