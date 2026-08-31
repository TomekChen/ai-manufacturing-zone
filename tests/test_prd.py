# -*- coding: utf-8 -*-
"""PRD 生成器 · Seam 单测（离线、确定性、不联网、不碰真 LLM）。

运行：py -3.12 test_prd.py
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import rag.prd as prd  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  -", name)
    else:
        FAIL += 1
        print("  FAIL-", name)


def expect_value_error(name, fn):
    try:
        fn()
        check(name + " (应抛 ValueError)", False)
    except ValueError:
        check(name, True)
    except Exception as e:  # 抛错类型不对也算失败
        check(name + " 但抛了 %r" % e, False)


# ---------- clean_input ----------
def test_clean_input():
    print("\n[clean_input]")
    ok = prd.clean_input({
        "company": "  某某精密制造  ",
        "industry": "汽车零部件",
        "business": "主营发动机精密零部件，已有 ERP/MES 系统若干。",
        "mode": "guide",
    })
    check("guide 合法：company 去空格", ok["company"] == "某某精密制造")
    check("guide 合法：mode 保留", ok["mode"] == "guide")
    check("guide 合法：raw_requirements 归一为空串", ok["raw_requirements"] == "")

    okn = prd.clean_input({
        "company": "A公司", "business": "做工业软件的",
        "mode": "normalize", "raw_requirements": "客户要：智能客服、图纸问答",
    })
    check("normalize 合法：mode 保留", okn["mode"] == "normalize")
    check("normalize 合法：raw_requirements 保留", "智能客服" in okn["raw_requirements"])
    check("industry 缺省为空串", okn["industry"] == "")

    expect_value_error("缺 company 报错", lambda: prd.clean_input({"company": "  ", "business": "内容够长了"}))
    expect_value_error("缺 business 报错", lambda: prd.clean_input({"company": "A", "business": ""}))
    expect_value_error("business 过短报错", lambda: prd.clean_input({"company": "A", "business": "短"}))
    expect_value_error("normalize 缺 raw_requirements 报错",
                       lambda: prd.clean_input({"company": "A", "business": "内容够长够长", "mode": "normalize", "raw_requirements": ""}))

    fb = prd.clean_input({"company": "A", "business": "内容够长够长", "mode": "乱写的"})
    check("非法 mode 回退 guide", fb["mode"] == "guide")

    long_company = prd.clean_input({"company": "公" * 100, "business": "内容够长够长", "mode": "guide"})
    check("company 超长被截断到 <=60", len(long_company["company"]) <= 60)

    long_biz = prd.clean_input({"company": "A", "business": "业" * 9000, "mode": "guide"})
    check("business 超长被截断到 <=4000", len(long_biz["business"]) <= 4000)


# ---------- prompts ----------
def test_prompts():
    print("\n[prompts]")
    sg = prd.build_system_prompt("guide")
    sn = prd.build_system_prompt("normalize")
    check("system 是非空字符串", isinstance(sg, str) and len(sg) > 50)
    check("guide 提示词含引导/待确认语义", ("引导" in sg or "澄清" in sg or "待确认" in sg))
    check("normalize 提示词含规范化/整理语义", ("规范化" in sn or "整理" in sn or "标准" in sn))
    check("两模式提示词不同", sg != sn)
    check("提示词要求输出 Markdown", ("Markdown" in sg or "markdown" in sg))

    ctx = prd.format_kb_context([
        {"text": "数字孪生赋能智能制造", "doc": {"title": "工控网", "url": "http://x.com"}},
        {"text": "MES 与 ERP 集成", "doc": {"title": "e-works", "url": ""}},
    ])
    check("format_kb_context 含资料标记", ("资料" in ctx))
    check("format_kb_context 含命中正文", ("数字孪生" in ctx))
    check("空命中返回空串", prd.format_kb_context([]) == "")
    check("None 命中返回空串", prd.format_kb_context(None) == "")

    msgs = prd.build_prd_messages(
        company="某某精密", industry="汽车零部件", business="主营发动机件",
        mode="guide", raw_requirements="", context="【资料1】…")
    check("messages 两条", isinstance(msgs, list) and len(msgs) == 2)
    check("第一条 system 角色", msgs[0]["role"] == "system")
    check("第二条 user 角色", msgs[1]["role"] == "user")
    check("user 含公司名", "某某精密" in msgs[1]["content"])
    check("user 含业务", "主营发动机件" in msgs[1]["content"])
    check("user 注入了行业参考上下文", "资料1" in msgs[1]["content"])

    msgs2 = prd.build_prd_messages(company="A", industry="", business="业务", mode="normalize",
                                   raw_requirements="客户原话需求", context="")
    check("无 context 时 user 仍含原始需求", "客户原话需求" in msgs2[1]["content"])


# ---------- has_api_key ----------
def test_has_api_key():
    print("\n[has_api_key]")
    old = os.environ.get("DASHSCOPE_API_KEY")
    os.environ["DASHSCOPE_API_KEY"] = "sk-test"
    check("有 key -> True", prd.has_api_key() is True)
    os.environ.pop("DASHSCOPE_API_KEY", None)
    check("无 key -> False", prd.has_api_key() is False)
    if old is not None:
        os.environ["DASHSCOPE_API_KEY"] = old


# ---------- generate_prd ----------
class _StubStore:
    def __init__(self, hits=None, raise_on_search=False):
        self._hits = hits or []
        self._raise = raise_on_search
        self.queries = []

    def search(self, query, top_k=5, retrieval=None):
        self.queries.append(query)
        if self._raise:
            raise RuntimeError("索引坏了")
        return self._hits


def _make_chat(return_text=None, raise_exc=False, capture=None):
    def _chat(messages, temperature=0.3, timeout=60):
        if capture is not None:
            capture.append((messages, timeout))
        if raise_exc:
            raise RuntimeError("上游 500")
        return return_text
    return _chat


def test_generate_prd():
    print("\n[generate_prd]")
    payload = {"company": "某某精密", "industry": "汽车零部件",
               "business": "主营发动机精密零部件，已有 MES。", "mode": "guide"}

    hits = [{"text": "数字孪生赋能", "doc": {"title": "工控网", "url": "http://gk.com"}}]
    orig_chat = prd.chat
    try:
        prd.chat = _make_chat(return_text="# PRD 全文\n正文…")
        res = prd.generate_prd(_StubStore(hits=hits), payload)
        check("返回 prd 文本", res["prd"].startswith("# PRD"))
        check("mode 透传", res["mode"] == "guide")
        check("grounded=True（有命中）", res["grounded"] is True)
        check("hits 计数=1", res["hits"] == 1)
        check("sources 提取标题", len(res["sources"]) == 1 and res["sources"][0]["title"] == "工控网")
        check("带 model 字段", "model" in res)

        # 超时透传：generate_prd 应把更长的 config.PRD_TIMEOUT 传给 chat（而非默认 60s）
        cap = []
        prd.chat = _make_chat(return_text="x", capture=cap)
        prd.generate_prd(_StubStore(hits=[]), payload)
        check("chat 收到 PRD_TIMEOUT", bool(cap) and cap[0][1] == prd.config.PRD_TIMEOUT)
        prd.chat = _make_chat(return_text="# PRD 全文\n正文…")  # 复位供后续用例

        # 空知识库 -> 降级不接地
        res2 = prd.generate_prd(_StubStore(hits=[]), payload)
        check("空命中 grounded=False", res2["grounded"] is False)
        check("空命中 hits=0", res2["hits"] == 0)

        # store.search 抛错 -> 容错，仍能生成，grounded=False
        res3 = prd.generate_prd(_StubStore(raise_on_search=True), payload)
        check("检索异常仍出 PRD", res3["prd"].startswith("# PRD"))
        check("检索异常 grounded=False", res3["grounded"] is False)

        # chat 抛错 -> 向上抛（端点映射 502）
        prd.chat = _make_chat(raise_exc=True)
        raised = False
        try:
            prd.generate_prd(_StubStore(hits=hits), payload)
        except RuntimeError:
            raised = True
        check("chat 异常向上抛", raised)

        # 校验非法输入 -> ValueError（在调 chat 前）
        bad = False
        try:
            prd.generate_prd(_StubStore(hits=hits), {"company": "", "business": "内容够长"})
        except ValueError:
            bad = True
        check("非法输入抛 ValueError", bad)
    finally:
        prd.chat = orig_chat


if __name__ == "__main__":
    test_clean_input()
    test_prompts()
    test_has_api_key()
    test_generate_prd()
    print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
