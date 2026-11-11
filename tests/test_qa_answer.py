# -*- coding: utf-8 -*-
"""门户问答答案清洗单测：WeKnora 回答里前台渲染不出来的引用噪声要清干净。

运行：py tests/test_qa_answer.py

为什么测：客户看到的答案里混着 <kb doc=..> 标签和 ![...](resource://xxx) 图片语法，
浏览器既解析不了内部协议，前台 Markdown 也不渲染图片，只剩一行行乱码。
"""
import os
import sys

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

import qa  # noqa: E402

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  -", name)
    else:
        FAIL += 1
        print("  FAIL-", name, extra)


print("\n[1] 内联引用标记")
out = qa.clean_weknora_answer('MES 是执行系统<kb doc="a" chunk_id="1"/>，覆盖车间。<kb doc="b">引文</kb>')
check("自闭合标签清掉", "<kb" not in out, out)
check("成对标签连同内容清掉", "引文" not in out, out)
check("正文文字不动", out.startswith("MES 是执行系统") and "覆盖车间" in out, out)

print("\n[2] 渲染不出来的图片")
out = qa.clean_weknora_answer('落地分四步。\n![封面](resource://YoF4hFDkOHMpqt7WxYIOgA)\n- 需求定义')
check("resource:// 图片清掉", "resource://" not in out and "![" not in out, out)
check("前后正文保留", "落地分四步" in out and "需求定义" in out, out)
out = qa.clean_weknora_answer('![产品图](https://example.com/a.png)')
check("http(s) 图片原样保留", out == "![产品图](https://example.com/a.png)", out)

print("\n[3] 来源列表去重")
srcs = qa.build_sources([{"title": "A 文档", "snippet": "片段1"}, {"title": "B 文档", "snippet": ""},
                         {"title": "A 文档", "snippet": "片段2"}, {"snippet": "无题"}])
check("同标题只留第一条", [s["title"] for s in srcs] == ["A 文档", "B 文档", "(未命名)"], str(srcs))
check("保留第一条片段", srcs[0]["snippet"] == "片段1", str(srcs[0]))
check("空引用不炸", qa.build_sources([]) == [] and qa.build_sources(None) == [])

print("\n[4] 边界")
check("空输入不炸", qa.clean_weknora_answer("") == "" and qa.clean_weknora_answer(None) == "")
check("首尾空白去掉", qa.clean_weknora_answer("  答案  ") == "答案")

print("\n==== %d passed, %d failed ====" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
