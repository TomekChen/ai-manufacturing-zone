# 知识库 RAG 模块重构 + 后台问答指标 —— 需求规格（对齐稿）

> 状态：**待用户批准**。批准后才进入拆 ticket 与编码。
> 方法论：disciplined-engineering（先对齐再动手 / 垂直切片 / 无红线不推理）+ ponytail（能少写就少写，不做投机抽象）。

---

## 〇、背景与诊断（针对智能制造源码）

核查智能制造项目自身源码（`app.py` + `kb.py` 两个 Python 文件）：**没有使用工厂/注册表/策略模式**，整体是过程式写法。

- `app.py`：一整排平铺的 Flask 路由函数 + 零散 helper（`load_json` / `save_json` / `hash_password` / `check_alive` …），无任何工厂或注册表。
- `kb.py`：一堆模块级函数（`embed_texts` / `chat` / `split_text` / `fetch_url_text` / `extract_pdf_text`）+ **一个巨型 `KnowledgeStore` 类**，把存储、切块、嵌入、检索、生成、网页采集、友链管理全部包在自己身上——正是「一个 py 文件 = 一整个 RAG 模块」。
- 切块：只有单一函数 `split_text`（固定 600/80），没有策略选择，更没有策略类。
- 检索：只有 `KnowledgeStore.search`（纯向量：百炼 text-embedding-v3 + FAISS），没有 BM25 / 混合的位置。
- `doc_type`（`upload` / `url` / `link`）只是存进元数据的字符串标签，**没有**按类型分派的处理逻辑。

结论：可插拔的「分块 / 检索 / 融合」这几处现在是写死的单实现，加一种策略就得改主流程。本次重构把 `kb.py` 拆成 `rag/` 包，并用「策略 + 注册表（轻量工厂）」收敛这几处——**加一种策略 = 注册一个实现，不改主流程**。结构上参考已完成项目 `rag_annual_report`（多文件、分阶段拆分）的做法，但把它「有想法却仍用 if/elif + 布尔开关、没抽干净」的部分在智能制造里重组干净。

---

## 一、已达成共识（决策清单）

| 编号 | 决策点 | 结论 |
|------|--------|------|
| D1 | 复用边界 | 在智能制造项目内做 `rag/` 可插拔包（策略+注册表），本次**不**抽成跨项目共享库 |
| D2 | 分块生效粒度 | **入库时逐文档选**分块策略；改策略不影响已有文档；另提供「全库重建索引」 |
| D3 | 检索/RRF/Rerank 时机 | **提问时选**，秒切、不重跑 embedding |
| D4 | v1 实现范围 | 务实集：分块 `fixed`+`semantic`；检索 `vector`/`bm25`/`hybrid+RRF`。Rerank、查询改写**只留接口预留位（注册表可挂）**，不写实现 |
| D5 | 问答指标 | 两者都要：**在线问答看板**（真实流量，纯计数，零 token）＋ **离线 RAGAS-lite 评测页** |
| D6 | LLM 裁判触发 | **管理员手动点「重跑评测」**才花 token；内置小题集跑四指标；对近期真实问答抽样打分**默认关**，勾选才跑 |
| D7 | 可视化 | 由 QoderWork 决定（见 §四） |

---

## 二、目标包结构 `rag/`（把单文件 kb.py 拆开）

> 目录即分层；注册表就是「工厂」。每个可插拔维度 = 一个 `REGISTRY` + 一个 `build_xxx(name, **opts)` 工厂函数 + 一个基类文档化接口。

```
rag/
  __init__.py         # 对外唯一入口：导出 KnowledgeStore；import 时触发各注册表自注册
  config.py           # env/常量、默认策略名、阈值集中处
  registry.py         # 通用注册表小工具（register/build），三处复用，避免重复样板
  chunkers/
    base.py           # Chunker 接口：chunk(unit) -> list[Chunk]
    fixed.py          # FixedChunker（滑动窗口 + overlap）
    semantic.py       # SemanticChunker（按段落/标题边界，表格单独成块）
    # hierarchical.py 预留（不实现，注册表可挂）
  retrievers/
    base.py           # Retriever 接口：search(query, k, filter) -> list[Candidate]
    vector.py         # VectorRetriever（百炼 embed + FAISS）
    bm25.py           # BM25Retriever（jieba + rank_bm25）
    hybrid.py         # HybridRetriever（vector + bm25 → RRF）
  fusion.py           # reciprocal_rank_fusion（纯函数，独立可测）
  rerankers/
    base.py           # Reranker 接口
    noop.py           # NoopReranker（默认直通，占住 seam）
    # cross_encoder.py 预留
  embedding.py        # 百炼 embed 封装（batch=10、L2 归一化）
  llm.py              # 百炼 chat 封装（qwen-plus，temp 低）
  ingest.py           # 采集/解析：fetch_url_text、looks_like_nav_page、PDF/DOCX 提取（从 kb.py 搬来）
  store.py            # KnowledgeStore：持久化 + approve/reject/delete + add_doc(chunking=…) + ask(retrieval=…, fusion=…, rerank=…)
  telemetry.py        # 问答日志落盘 + 指标聚合（命中率/拒绝率/各策略对比/未答问题/👍👎）
  evaluate.py         # RAGAS-lite 离线评测：内置小题集 + 手动触发跑四指标（不引 ragas 重依赖，自调 LLM 打分）
```

**兼容约束**：`app.py` 现在 `import kb; kb.KnowledgeStore(DATA_DIR)`。重构后 `app.py` 改成 `from rag import store`（或直接 `import rag`），保持 `KnowledgeStore` 对外方法名尽量不变，降低路由层改动。数据文件（kb_docs/kb_chunks/kb_index.faiss/kb_meta）沿用，避免线上数据迁移。

**已装依赖**：numpy、faiss、requests、bs4、pypdf。**需新增**：`rank_bm25`、`jieba`（纯 Python、轻）。

---

## 三、用户故事（详尽，含 Out of Scope）

### 3.1 分块（入库时逐文档）
- US-01 管理员上传/采集一篇文档，可在「分块方式」下拉里选 `固定窗口` 或 `语义`，默认 `语义`。
- US-02 选定的策略随文档元数据持久化（每篇记自己的 `chunking`）。
- US-03 管理员通过（approve）时，才按该文档的分块策略切块 + 嵌入入索引。
- US-04 管理员点「全库重建索引」→ 对每篇按其**各自记录的**分块策略重新切块、重新嵌入（确认弹窗，提示会重花 embedding 额度）。
- US-05 上传时不选就吃默认策略，无需二次操作。
- US-06 单篇文档可「换分块策略并重建该篇」（改元数据里该篇 chunking → 重切该篇）。

### 3.2 检索/融合/Rerank（提问时）
- US-10 前台问答或后台调试可选 `纯向量` / `BM25` / `混合(vector+BM25+RRF)`，默认 `混合`。
- US-11 RRF 融合参数 k 固定经验值 60（不暴露给管理员，YAGNI）。
- US-12 检索返回 top-N，交 LLM 生成，带来源编号引用。
- US-13 相关性低于阈值 → 拒答话术（沿用现有逻辑，阈值读 vec_score 量纲）。
- US-14 Rerank / 查询改写为**接口占位**，当前不启用（注册表可挂，未来零改主流程接入）。

### 3.3 在线问答看板（D5-a，零 token）
- US-20 每次真实问答落一条日志：时间、问题、所选检索策略、命中数、最高相似度、是否触发拒答、答案长度、耗时。
- US-21 前台回答下提供 `👍/👎` 反馈按钮，点了写入对应日志。
- US-22 后台「问答分析」页展示：总问数、无命中/拒绝率、平均最高相似度、各策略（vector/bm25/hybrid）并排对比（问数/拒绝率/平均相似度/平均👍率）、问答量时间趋势、👍👎 汇总。
- US-23 「未命中/被拒问题」清单按出现频次排序，直接暴露知识库缺口（管理员据此补内容或换策略）。
- US-24 日志文件设上限滚动（防无限膨胀），超限丢最旧。

### 3.4 离线 RAGAS-lite 评测（D5-b + D6，手动触发才花 token）
- US-30 后台「评测」区一个「重跑评测」按钮；管理员点才跑。
- US-31 内置一份小标准题集（5–10 题，带标准答案，随智能制造语料来），对**当前默认策略配置**跑，展示四指标：忠实度 / 答案相关性 / 上下文精确率 / 上下文召回率（横向条形对比，含上次结果做趋势）。
- US-32 每次评测结果落盘，记录时间 + 当时策略配置快照，便于「换策略前后对比」。
- US-33 可选勾「对近期 N 条真实问答抽样裁判打分」（默认关），勾选才把这些真实问答送去 LLM 评忠实度/相关性并计入看板。
- US-34 评测/裁判用与问答同一套百炼通道；无 `DASHSCOPE_API_KEY` 时按钮置灰并提示。

### 3.5 非功能
- US-40 所有新增后台界面汉化、字号偏大、暗色主题沿用现有设计令牌。
- US-41 不出现第三方/厂商痕迹，呈现为自研能力（沿用既定去品牌要求）。
- US-42 `rag/` 各策略有最小可运行自检（见 §五 seam），不依赖网络/真实 LLM 即可跑通分块与融合与聚合逻辑。

### Out of Scope（本次明确不做）
- 跨项目共享 pip 库（两项目 embedding/存储不同，统一为时过早）。
- 整站爬取 / 定时自动采集（边界不变）。
- CrossEncoder Rerank 真实实现、查询改写真实实现（仅留 seam）。
- hierarchical 父子块分块实现（仅留注册位）。
- 向量库换成生产级服务（Milvus/PGVector）——仍文件型 FAISS。
- 实时流式回答、多轮对话记忆。
- 自动后台采样裁判（改手动，见 D6）。

---

## 四、可视化方案（D7，由 QoderWork 决定）

**不引图表库**（本机 npm safe-delete 有坑，且几根条形用不上重库）。用纯 CSS/SVG 手绘，沿用站点设计令牌：

1. **顶部数字卡（count-up）**：总问数 / 拒绝率 / 平均最高相似度 / 👍率。
2. **各策略并排对比**：CSS 横向条形分组（vector/bm25/hybrid × 拒绝率、平均相似度、👍率），一眼看出哪种召回更稳。
3. **问答量时间趋势**：极简内联 SVG 折线（近 14/30 天）。
4. **未命中问题清单**：表格，按频次降序，附「最近提问时间」「问题原文」，每行一个「去知识库补」的引导。
5. **评测四指标**：横向进度条（0–1），显示当前值 + 上次值 + 策略配置快照标签；「重跑评测」按钮带 loading 与 token 提示。

理由：信息密度够、零依赖、可维护、与现有 AdminKB 风格一致。数据量大到需要交互图表时再升级 ECharts（届时才加依赖）。

---

## 五、测试 Seam（请确认，阶段三 TDD 前先对齐）

优先高 seam、越少越好。**离线确定性、不碰网络/LLM** 的才做单测：

- S1 `fusion.reciprocal_rank_fusion`：给定两路排名 → 期望融合序（期望值手工算，独立于实现）。
- S2 `chunkers.fixed` / `chunkers.semantic`：给定文本/块 → 断言块数、边界、overlap、表格独立成块。
- S3 `retrievers.bm25`：小语料 + 查询 → 断言排序（含精确数字命中的用例）。
- S4 `telemetry` 聚合：喂合成问答日志 → 断言拒绝率/命中率/各策略分组/未答清单计数正确。
- S5 `evaluate` 题集加载 + 结果结构（不真调 LLM，mock 打分桩）。

**不做**单测：embedding 真实调用、LLM 生成、hybrid 端到端、采集 fetch_url_text（网络）——归为手动/集成冒烟（本地 HTML fixture 已在上轮用过）。

---

## 六、拟拆垂直切片（曳光弹，每条一个上下文窗口内可完成 + 演示）

- **Slice 1（地基）**：建 `rag/` 骨架 + `registry` + `chunkers(fixed/semantic)` + `fusion` + 单测 S1/S2；`store.py` 暂用向量检索保持旧行为跑通「上传→approve→ask」。*价值：现有问答不回归。*
- **Slice 2（BM25+混合）**：`bm25`/`hybrid` retriever + 提问时选检索方式 + 单测 S3。*价值：管理员当场可切 vector/bm25/hybrid 看差异。*
- **Slice 3（分块可选+重建）**：入库逐文档选分块 + 记录策略 + 全库重建 + 单篇重建。*价值：D2 完整落地。*
- **Slice 4（在线看板）**：telemetry 落盘 + 👍👎 + 后台分析页（§四 1–4）+ 单测 S4。*价值：真实流量指标上线。*
- **Slice 5（离线评测）**：内置题集 + RAGAS-lite + 手动重跑 + 抽样裁判勾选 + 后台评测卡（§四 5）+ 单测 S5。*价值：换策略可量化对比。*

依赖：1→2→3 顺序（3 依赖 1 的 chunker 抽象，2 依赖 1 的 retriever 骨架）；4、5 依赖 1（可并行于 2/3 之后）。Rerank/查询改写/hierarchical 的 seam 在 Slice 1 就预留但不实现。

---

## 七、请确认

批准本规格即进入 Slice 1 编码（TDD：先 S1/S2 红→绿）。如需调整：包结构粒度、v1 策略集、看板指标项、切片顺序，请指出。
