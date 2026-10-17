# -*- coding: utf-8 -*-
"""对账助手（A9 第四个上线智能体）：银行流水 × 应收应付台账 → 匹配建议 + 差异报告。

场景：月末财务人工逐笔核对银行流水与台账，费时且易漏。把两份文本粘贴进来，
LLM 输出强制 JSON：完全匹配对 / 疑似匹配（附核对要点）/ 双边未达账项 / 建议分录。
只给建议不给结论——疑似项必须人工确认后才能入账。LLM 解析失败收敛 RuntimeError
（端点层 502）；入参校验失败抛 ValueError（端点层 400）。
"""
import csv
import io
import json

from rag import prd as kb_prd
from rag.llm import chat

from .base import AgentBase, make_result
from .registry import register

_SYSTEM = """你是制造企业的财务对账助手。用户会提供两份文本：银行流水（必填）和应收应付台账（可选，没有则只做流水侧归类）。逐笔比对后只输出一个 JSON 对象，不要输出任何其他文字：
{
  "matched": [{"our": "台账条目摘要（含日期/对方/金额原文写法）", "bank": "流水条目摘要", "amount": "金额，保留原文写法", "basis": "匹配依据（单号/金额/日期/对方名称）"}],
  "suspected": [{"our": "台账条目摘要", "bank": "流水条目摘要", "amount": "金额", "reason": "为什么只算疑似（金额相近/日期不符/名称含糊）", "confirm_hint": "人工核对要点，如：查银行回单尾号"}],
  "unmatched_bank": ["银行有、台账无的流水条目摘要，逐条列出"],
  "unmatched_ledger": ["台账有、银行无的应收应付条目摘要，逐条列出"],
  "suggestions": ["建议分录，按会计口语写，如：借 银行存款 50,000 / 贷 应收账款-华阳 50,000；未达账项写 待处理项，不编造分录"],
  "summary": {"matched_count": 0, "suspected_count": 0, "unmatched_count": 0},
  "notes": "其他需要提醒的差异或风险，没有则空字符串"
}
要求：金额一律保留原文写法，不要换算或编造；匹配依据写清具体凭据；两边数量不一致时差额必须出现在 unmatched 列表里；不确定就放 suspected，宁多勿漏。"""

MAX_UPLOAD_ROWS = 2000  # 解析行数上限（超出截断，防止把整份年度流水灌给 LLM）


def parse_upload(filename, data):
    """上传的对账文件 → 表格文本（A9 增强，run() 入参同款格式）。

    CSV/TXT 用 stdlib（编码依次试 utf-8-sig/gbk/utf-8/latin-1，兼容银行网银导出），
    XLSX 用 openpyxl（只读首个工作表，取单元格显示值）。返回 (text, total_rows)。
    入参非法抛 ValueError（端点层 400）。
    """
    name = (filename or "").lower()
    if name.endswith(".csv") or name.endswith(".txt"):
        text = None
        for enc in ("utf-8-sig", "gbk", "utf-8", "latin-1"):
            try:
                text = data.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if text is None:
            raise ValueError("无法识别文件编码（请用 UTF-8 或 GBK 编码的 CSV）")
        rows = list(csv.reader(io.StringIO(text)))
    elif name.endswith(".xlsx"):
        try:
            import openpyxl
        except ImportError:
            raise RuntimeError("服务器未安装 openpyxl，暂不支持 Excel 文件")
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as e:
            raise ValueError("无法解析 Excel 文件：%s" % str(e)[:120])
        try:
            ws = wb.worksheets[0]
            rows = [[("" if c is None else str(c)) for c in row]
                    for row in ws.iter_rows(values_only=True)]
        finally:
            wb.close()
    else:
        raise ValueError("只支持 CSV / XLSX 文件（扫描件 PDF 暂不支持）")

    lines = []
    for row in rows[:MAX_UPLOAD_ROWS]:
        line = "\t".join(str(c).strip() for c in row).strip()
        if line:
            lines.append(line)
    if not lines:
        raise ValueError("文件里没有可读取的数据行")
    return "\n".join(lines)[:12000], min(len(rows), MAX_UPLOAD_ROWS)


@register
class ReconcilerAgent(AgentBase):
    id = "reconciler"
    name = "对账助手"
    role = "银企对账核对智能体"
    emoji = "🧮"
    color = "amber"
    desc = ("把银行流水和应收应付台账粘贴进来，自动逐笔比对：完全匹配 / 疑似匹配（附核对要点）"
            "/ 未达账项清单 / 建议分录。疑似项必须人工确认，差异不漏一笔。")
    caps = [
        "银行流水 × 台账逐笔匹配（完全匹配/疑似/未达）",
        "差异报告：未达账项双边清单，不漏一笔",
        "建议分录 + 疑似项人工核对要点",
    ]
    status = "live"
    endpoint = "/api/agents/reconciler/run"
    triggers = ["对账", "流水核对", "核销", "未达账", "银企"]
    ui = "recon"

    def available(self):
        return kb_prd.has_api_key()

    def _messages(self, statement, ledger):
        user = "【银行流水】\n%s" % statement
        if ledger:
            user += "\n\n【应收应付台账】\n%s" % ledger
        else:
            user += "\n\n（未提供台账，只做流水侧归类，matched/suspected 留空，全部条目进 unmatched_bank）"
        return [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ]

    def _parse(self, raw):
        s = (raw or "").strip()
        if s.startswith("```"):
            s = s.strip("`").lstrip("json").strip()
        start, end = s.find("{"), s.rfind("}")
        if start == -1 or end <= start:
            raise RuntimeError("对账失败：模型未返回结构化结果，请重试")
        try:
            r = json.loads(s[start:end + 1])
        except ValueError:
            raise RuntimeError("对账失败：结果解析出错，请重试")
        if not isinstance(r, dict):
            raise RuntimeError("对账失败：结果形状异常，请重试")
        for key in ("matched", "suspected", "unmatched_bank", "unmatched_ledger", "suggestions"):
            if not isinstance(r.get(key), list):
                r[key] = []
        if not isinstance(r.get("summary"), dict):
            r["summary"] = {
                "matched_count": len(r["matched"]),
                "suspected_count": len(r["suspected"]),
                "unmatched_count": len(r["unmatched_bank"]) + len(r["unmatched_ledger"]),
            }
        if not isinstance(r.get("notes"), str):
            r["notes"] = ""
        return r

    def run(self, payload):
        p = payload or {}
        statement = (p.get("statement") or p.get("text") or "").strip()
        ledger = (p.get("ledger") or "").strip()
        if not statement:
            raise ValueError("请粘贴银行流水文本（网银导出/流水单/CSV 均可）")
        if len(statement) > 12000:
            statement = statement[:12000]
        if len(ledger) > 8000:
            ledger = ledger[:8000]
        try:
            raw = chat(self._messages(statement, ledger), temperature=0.1)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError("对账失败：%s" % str(e)[:120])
        r = self._parse(raw)
        unmatched = len(r["unmatched_bank"]) + len(r["unmatched_ledger"])
        suspected = len(r["suspected"])
        if unmatched == 0 and suspected == 0:
            confidence = 0.8
        elif r["matched"]:
            confidence = 0.6
        else:
            confidence = 0.3
        return make_result(self, r, confidence=confidence)
