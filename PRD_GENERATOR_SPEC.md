# PRD 生成器 · mini-SPEC（Slice 7-Next，对齐老板新方向）

> 背景：老板在微信里明确了他对这个专区的真正目的——不是把知识库问答做精，而是
> **"用 AI 帮智能制造行业客户做智能体平台转型、促成合作"**。他最兴奋的功能是：
> 用户输入"我是什么公司 + 我们的业务介绍" → AI 直接产出一套**面向该客户的
> 《AI 智能体平台功能需求 PRD》**。本切片就是这个功能的 MVP。

## 一、目标与非目标

目标（本切片做）：
- 一个后台工具：填公司信息 + 业务介绍 → 一键生成结构化 PRD（Markdown）。
- 支持老板说的**两种模式**：
  - **引导模式（guide）**：客户不懂要什么 → AI 先给一版完整方案草稿，并在末尾列出"需要客户澄清的问题"，用来引导客户往下谈。
  - **规范化模式（normalize）**：客户已给了一堆原始需求 → AI 把它整理成规范 PRD，补齐缺口、标注歧义点待确认。
- **行业接地（know-how）**：生成前先从知识库检索相关片段，作为"行业参考与案例"注入，让产出更专业、更贴智能制造行业。呼应老板"做行业 know-how 专家"。
- 结果可复制、可下载为 `.md`。

非目标（本切片不做，留给后续）：
- 不做公开获客落地页（当前放后台，团队内部用；公开版是后续增强）。
- 不做多版本 PRD 管理 / 历史留存 / 在线编辑。
- 不做 PDF/Word 导出（先 Markdown，够用）。
- 不引新依赖（复用现有 `rag.llm.chat` + `KnowledgeStore.search`）。

## 二、接口契约

`POST /api/admin/prd/generate`（需管理员 token，`Authorization: Bearer`；限流 6 次/分/IP）

请求：
```json
{
  "company": "某某精密制造股份有限公司",
  "industry": "汽车零部件",
  "business": "主营汽车发动机精密零部件，10 个车间，ERP/MES 已有…",
  "mode": "guide",              // guide | normalize
  "raw_requirements": "客户原话…（normalize 模式必填）"
}
```
响应 200：
```json
{
  "prd": "# 某某精密制造 · AI 智能体平台功能需求 PRD\n…（Markdown 全文）",
  "mode": "guide",
  "grounded": true,            // 是否命中并注入了知识库资料
  "hits": 3,                   // 注入的参考片段数
  "sources": [ {"title": "...", "url": "..."} ],
  "model": "qwen-plus"
}
```
错误：无 `DASHSCOPE_API_KEY` → 400；输入校验失败 → 400；LLM 失败 → 502；其它 → 500。

校验规则（`clean_input`）：
- `company` 去空后必填，≤ 60 字。
- `industry` ≤ 40 字（可空，空则让模型从 business 推断）。
- `business` 必填，去空后 ≥ 5 字，≤ 4000 字。
- `mode` ∈ {guide, normalize}，非法回退 guide。
- `normalize` 模式 `raw_requirements` 必填，≤ 6000 字。

## 三、PRD 结构模板（提示词强约束输出骨架）

1. 文档信息（客户 / 行业 / 模式 / 日期 / 免责说明：AI 生成需人工复核）
2. 客户与业务背景
3. 智能体平台转型目标（业务价值导向）
4. 目标用户与角色
5. 核心智能体（Agent）功能需求清单（表格：智能体 / 应用场景 / 输入 / 输出 / 价值）
6. 平台功能需求（知识库、对话、工作流编排、系统集成、权限、运营看板等）
7. 非功能需求（性能、安全合规、可用性、可维护性）
8. 技术架构建议
9. 实施路线图（分期：PoC → MVP → 推广）
10. 行业参考与案例（引用知识库命中片段，标注来源）
11. 待客户确认的问题（引导模式必列；规范化模式列歧义/缺口）

## 四、可测边界（Seam）

`rag/prd.py` 纯函数 + 可打桩：
- `SYSTEM_PROMPT` / `build_system_prompt(mode)`
- `format_kb_context(hits)` → 行业参考段（空命中返回 ""）
- `build_user_prompt(company, industry, business, mode, raw_requirements, context)`
- `build_prd_messages(...)` → [{system},{user}]
- `clean_input(payload)` → 归一化 dict 或抛 `ValueError`
- `has_api_key()`
- `generate_prd(store, payload)` → 调 `store.search`（容错）+ `chat`，返回契约结构

单测：假 chat 返回固定串、假 store.search 返回固定命中，覆盖校验分支、模式分支、
空 KB 降级（grounded=false）、chat 异常上抛。全部离线不联网。

## 五、范围与后续候选
- 公开获客版（免登录、限次、留资表单）
- PRD 导出 PDF / 在线协同编辑 / 历史留存
- 与"案例库"打通（老板提到"包括我们的一些案例"）
- 界面整体美化（老板嫌"看起来简单"，独立切片）
