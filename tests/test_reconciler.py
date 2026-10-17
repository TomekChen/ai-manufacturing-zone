# -*- coding: utf-8 -*-
"""A9 对账助手单测：注册表 + 匹配结果契约 + 通用 run 端点 + dispatch 路由（离线、确定性、不触发真 LLM）。

运行：py tests/test_reconciler.py

打桩：把 agents.reconciler.chat 换成假实现（模块顶层 import 进来的名字，
桩 agents.reconciler.chat 一处即生效）；LLM 失败/坏 JSON 的收敛行为也要覆盖。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

# 与 tests/test_agents.py 相同的本机缺库兜底（faiss/bs4 原生依赖不装也能跑）
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
import agents.reconciler as rc  # noqa: E402
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


GOOD_JSON = '''{"matched": [{"our": "应收 华阳 50,000 PO-2026-1001", "bank": "10-08 收 华阳 50,000",
"amount": "50,000.00", "basis": "单号 PO-2026-1001 + 金额一致"}],
"suspected": [{"our": "应收 天成 12,000", "bank": "10-09 收 天成贸易 11,850", "amount": "11,850",
"reason": "金额差 150", "confirm_hint": "查折让单或银行回单"}],
"unmatched_bank": ["10-10 付 苏州钢材贸易 32,100 原材料款"],
"unmatched_ledger": ["应付 苏州钢材贸易 32,100 账期30天"],
"suggestions": ["借 银行存款 50,000 / 贷 应收账款-华阳 50,000"],
"summary": {"matched_count": 1, "suspected_count": 1, "unmatched_count": 2},
"notes": "有一笔疑似短款 150 元，需查折让"}'''

# 本机未必配 DASHSCOPE_API_KEY：available() 走 rag.prd.has_api_key（与 app 同一模块对象），
# 桩 rag.prd 一处两边生效（同 test_order_catcher.py 的处理）
rc.kb_prd.has_api_key = lambda: True

FENCED_JSON = "```json\n%s\n```" % GOOD_JSON


def fake_chat(messages, temperature=0.1, timeout=60):
    text = messages[-1]["content"]
    if "只做流水侧归类" in text:
        return '''{"matched": [], "suspected": [],
"unmatched_bank": ["10-08 收 华阳 50,000"], "unmatched_ledger": [],
"suggestions": ["无台账，仅流水侧归类：贷方待认领 50,000"],
"summary": {"matched_count": 0, "suspected_count": 0, "unmatched_count": 1}, "notes": ""}'''
    return GOOD_JSON


rc.chat = fake_chat


def expect_error(name, exc, fn):
    try:
        fn()
        check(name + " (应抛 %s)" % exc.__name__, False)
    except exc:
        check(name, True)
    except Exception as e:
        check(name + " 但抛了 %r" % e, False)


def test_registry():
    print("\n[reconciler / 注册表]")
    a = get_agent("reconciler")
    check("已注册且 live", a is not None and a.status == "live")
    meta = a.meta()
    check("meta.ui=recon", meta.get("ui") == "recon")
    check("endpoint 指向通用 run", meta["endpoint"] == "/api/agents/reconciler/run")
    check("公开注册表顺序：prd → kb → order → recon",
          [x["id"] for x in agents.list_agents(only_live=True)] ==
          ["prd-advisor", "kb-assistant", "order-catcher", "reconciler"])
    check("route_task：对账任务命中 reconciler", route_task("月末银行流水要和台账对账") is a)
    check("route_task：核销命中", route_task("这几笔货款还没核销") is a)
    check("route_task：订单任务仍归 order-catcher",
          route_task("帮我抓一下客户邮件里的订单") is get_agent("order-catcher"))


def test_run_unit():
    print("\n[reconciler / run 单元]")
    a = get_agent("reconciler")
    r = a.run({"statement": "10-08 收 华阳 50,000", "ledger": "应收 华阳 50,000"})
    check("统一契约 ok/agent_id", r["ok"] is True and r["agent_id"] == "reconciler")
    check("result.matched 抽出", r["result"]["matched"][0]["amount"] == "50,000.00")
    check("result.unmatched 双边清单", len(r["result"]["unmatched_bank"]) == 1
          and len(r["result"]["unmatched_ledger"]) == 1)
    check("有疑似 + 未达 → confidence 0.6", r["confidence"] == 0.6)

    r0 = a.run({"statement": "10-08 收 华阳 50,000"})  # 无台账分支：fake 返回 unmatched_bank 独苗
    check("无台账 → 流水侧归类（matched 为空）", r0["result"]["matched"] == [])
    check("无台账 → unmatched_bank 收录", r0["result"]["unmatched_bank"][0].startswith("10-08"))
    check("全部未达 → confidence 0.3", r0["confidence"] == 0.3)

    expect_error("空流水抛 ValueError", ValueError, lambda: a.run({"statement": "   "}))
    expect_error("缺流水抛 ValueError", ValueError, lambda: a.run({"ledger": "x"}))

    old = rc.chat
    try:
        rc.chat = lambda *a_, **k_: "这不是 JSON"
        expect_error("坏 JSON 收敛 RuntimeError", RuntimeError, lambda: a.run({"statement": "x"}))
        rc.chat = lambda *a_, **k_: "前导文字 " + GOOD_JSON + " 尾注"
        r2 = a.run({"statement": "x", "ledger": "y"})
        check("夹带文字的 JSON 也能解析", r2["result"]["matched"][0]["amount"] == "50,000.00")
        rc.chat = lambda *a_, **k_: '{"matched": "不是列表"}'  # 列表字段缺省/坏类型兜底
        r3 = a.run({"statement": "x"})
        check("坏类型列表字段兜底为空列表", r3["result"]["matched"] == [] and r3["result"]["suggestions"] == [])
        check("summary 缺省按列表长度重算",
              r3["result"]["summary"]["unmatched_count"] == 0)
        # 全平账 → 0.8
        rc.chat = lambda *a_, **k_: GOOD_JSON.replace(
            '"suspected": [{"our": "应收 天成 12,000", "bank": "10-09 收 天成贸易 11,850", "amount": "11,850",\n"reason": "金额差 150", "confirm_hint": "查折让单或银行回单"}],', '"suspected": [],').replace(
            '"unmatched_bank": ["10-10 付 苏州钢材贸易 32,100 原材料款"],', '"unmatched_bank": [],').replace(
            '"unmatched_ledger": ["应付 苏州钢材贸易 32,100 账期30天"],', '"unmatched_ledger": [],')
        r4 = a.run({"statement": "x", "ledger": "y"})
        check("双边平账 → confidence 0.8", r4["confidence"] == 0.8)

        def boom(*a_, **k_):
            raise ConnectionError("网络断")
        rc.chat = boom
        expect_error("LLM 异常收敛 RuntimeError", RuntimeError, lambda: a.run({"statement": "x"}))
    finally:
        rc.chat = old


def test_http():
    print("\n[reconciler / HTTP 端点]")
    c = app.app.test_client()
    r = c.get("/api/agents")
    ids = [x["id"] for x in r.get_json()]
    check("GET /api/agents 含 reconciler", "reconciler" in ids)

    r = c.post("/api/agents/reconciler/run",
               json={"statement": "10-08 收 华阳 50,000", "ledger": "应收 华阳 50,000"})
    body = r.get_json()
    check("通用 run 200", r.status_code == 200, str(body)[:120])
    check("统一契约 result.matched", body.get("result", {}).get("matched", [{}])[0].get("amount") == "50,000.00")
    check("confidence 外层透传", body.get("confidence") == 0.6)

    r = c.post("/api/agents/reconciler/run", json={"statement": "  "})
    check("空流水 400", r.status_code == 400)

    r = c.post("/api/agents/dispatch", json={"task": "月末银行对账，流水贴在下面了"})
    body = r.get_json()
    check("dispatch 命中 reconciler",
          r.status_code == 200 and body.get("matched") == "reconciler", str(body)[:120])

    check("限流桶独立：agent_reconciler",
          "127.0.0.1" in app._ask_limits.get("agent_reconciler", {}))


def test_upload():
    print("\n[reconciler 文件上传解析]")
    import io
    import openpyxl

    def _clear():
        app._ask_limits.pop("recon_upload", None)

    c = app.app.test_client()

    # 单元层：CSV utf-8-sig（Excel 导出默认带 BOM）
    raw = "日期,收付,对方,金额\n2026-10-08,收,华阳汽车零部件,50000.00\n".encode("utf-8-sig")
    text, rows = rc.parse_upload("流水.csv", raw)
    check("CSV utf-8-sig 解析", "华阳汽车零部件" in text and rows == 2, text[:60])
    check("CSV 行内以制表符连接", "收\t华阳汽车零部件" in text)

    # 单元层：GBK（老网银常见）
    text, _ = rc.parse_upload("bank.csv", "日期,金额\n10-08,50000".encode("gbk"))
    check("CSV GBK 解析", "10-08" in text)

    # 单元层：xlsx
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["日期", "对方", "金额"])
    ws.append(["2026-10-08", "华阳", 50000])
    buf = io.BytesIO()
    wb.save(buf)
    text, rows = rc.parse_upload("台账.xlsx", buf.getvalue())
    check("XLSX 解析", "华阳" in text and "50000" in text and rows == 2, text[:60])

    # 单元层：拒绝类型 / 空表
    for fn, data, msg in [("订单.pdf", b"%PDF-1.4", "只支持 CSV / XLSX"),
                          ("空.csv", b"", "没有可读取的数据行")]:
        try:
            rc.parse_upload(fn, data)
            check("unit %s 应抛 ValueError" % fn, False)
        except ValueError as e:
            check("unit %s 400 语义" % fn, msg in str(e), str(e))

    # HTTP：无文件 400 / 坏类型 400 / 正常上传 200
    _clear()
    r = c.post("/api/agents/reconciler/upload", data={})
    check("无文件 400", r.status_code == 400)
    r = c.post("/api/agents/reconciler/upload",
               data={"file": (io.BytesIO(b"abc"), "x.pdf")},
               content_type="multipart/form-data")
    check("PDF 400", r.status_code == 400 and "CSV / XLSX" in r.get_json().get("error", ""))
    _clear()
    r = c.post("/api/agents/reconciler/upload",
               data={"file": (io.BytesIO(raw), "流水.csv")},
               content_type="multipart/form-data")
    body = r.get_json()
    check("CSV 上传 200 回填文本",
          r.status_code == 200 and body.get("ok") and "华阳汽车零部件" in body.get("text", ""),
          str(body)[:120])
    check("upload 限流桶 recon_upload",
          "127.0.0.1" in app._ask_limits.get("recon_upload", {}))


if __name__ == "__main__":
    test_registry()
    test_run_unit()
    test_http()
    test_upload()
    print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
