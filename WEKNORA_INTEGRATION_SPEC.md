# WeKnora LITE 轻量集成 SPEC（v1 草案 · 待老板过目）

> 一句话：**WeKnora LITE 当引擎，门户当门面**。检索/解析/问答能力全部换成 WeKnora，评测和 PRD 生成保留并改为调 WeKnora API。百级文档规模下不引入任何重型基建（postgres/qdrant/milvus 一概不要）。

## 一、背景与决策记录

- 老板要求集成 WeKnora（腾讯开源知识框架）；经对齐，走**轻量集成**路线，后续按需扩充。
- 已确认的 4 个决策：
  1. **问答前端**：继续用门户现有问答 UI，后端转发 WeKnora；WeKnora 自带 UI 仅作管理员高级入口。
  2. **文档迁移**：现有 8 篇 KB 文档**直接迁**到 WeKnora 重新解析分块，**不做双读**；旧 rag 索引数据只读归档。
  3. **docreader**（文档解析 gRPC 服务）：**常驻**，不做按需起停。
  4. **端口**：WeKnora LITE 对内 8805（管理员可访问），门户 8804 不变；对外仍然只暴露 8804。
- 资源已核实：阿里云 8 核 / 14GiB，当前仅用 1GiB；LITE（单 Go 二进制 + SQLite）约 300MB + docreader 约 200–500MB，合计 < 1GB，**无需其他项目让路**。

## 二、LITE 存储栈（为什么够用）

`.env.lite` 关键配置（实测模板原文）：

```
DB_DRIVER=sqlite            # 单文件库
RETRIEVE_DRIVER=sqlite      # 检索 = FTS5(关键词) + sqlite-vec(向量)，混合检索内建
STORAGE_TYPE=local          # 文件本地目录
STREAM_MANAGER_TYPE=memory  # 无 redis
NEO4J_ENABLE=false / WEKNORA_SANDBOX_MODE=disabled / ENABLE_GRAPH_RAG=false
```

- 百级文档对 sqlite-vec + FTS5 毫无压力（十万级仍是舒适区）。
- Embedding 走云端 OpenAI 兼容接口（接 DashScope/qwen，与现状一致），不占本地内存。
- **已知短板（提前记录）**：LITE 仅带 Simple 解析引擎，扫描版 PDF / 复杂表格 / 图纸解析弱；升级路径 = 换标准版 docreader 或接 Cloud 解析，不动其他架构。

## 三、集成形态（进程级，非代码级）

WeKnora 是 Go，门户是 Python——集成方式为 **sidecar 容器 + REST API**：

```
┌─ 智能制造专区 (Flask :8804, 常驻) ─────────┐
│ 门户 UI / 意图路由 / PRD 生成 / 评测尺子      │
└──────────────┬─────────────────┘
               │ HTTP (docker 内网)
┌──────────────▼─────────────────┐
│ weknora-lite (:8805, ~300MB)              │
│   KB 管理 · 分块 · 向量化 · 混合检索 · 问答    │
│ weknora-docreader (gRPC :50051, 常驻)      │
│   文档解析（PDF/Word/图片 OCR）               │
└────────────────────────────────┘
```

**API 面（已从官方 Go client 源码确认，非猜测）**：

| 用途 | 端点 |
| --- | --- |
| 直接检索（评测/PRD 接地用） | `POST /api/v1/knowledge-search` |
| 会话问答（门户问答转发用） | `POST /api/v1/sessions` → `POST /api/v1/knowledge-chat/{session_id}` |
| 上传文档 | `POST /api/v1/knowledge-bases/{kb_id}/knowledge/file`（另有 `/url` `/manual`） |
| 分块查看 | `GET /api/v1/knowledge/{id}/spans` |
| 鉴权 | API Key（`Authorization: Bearer sk-...`），支持按 KB 收窄权限 |

## 四、保留 / 退役清单

**保留（门户自己的差异化价值）**：
- `rag/evaluate.py` + `eval_questions.json`：四指标 LLM-as-judge 评测**尺子不变**，被测对象换成 WeKnora 检索结果。
- `rag/prd.py` + `rag/llm.py`：PRD 生成器保留，"行业接地"检索从 `store.search` 改为 WeKnora `knowledge-search`。
- `rag/intents/`：意图路由（smalltalk/knowledge）留在门户，knowledge intent 内部转发 WeKnora chat。
- `rag/telemetry.py`、前端问答/管理 UI、全部后台页签。

**退役（被 WeKnora 替代，代码本版先留、下版删）**：
- `rag/store.py`、`fusion.py`、`retrievers/`、`chunkers/`、`embedding.py`、`ingest.py`、`registry.py`。
- 旧 KB 数据文件：移到 `data/rag_archive_<ts>/` 只读归档，不删。

## 五、改造点（代码层）

1. **新增 `rag/engine.py`（唯一收口层，~150 行）**：封装 WeKnora 客户端——`search(query, top_k)`、`chat(session, question)`、`upload(file)`、`list_kb()`。所有 WeKnora 调用只准走这一层，env 开关 `WEKNORA_ENABLED`，关闭时自动回退旧检索（回滚网）。配置进 `.env`：`WEKNORA_BASE_URL=http://weknora:8805`、`WEKNORA_API_KEY=sk-...`、`WEKNORA_KB_ID=...`。
2. **`prd.py`**：`format_kb_context` 的检索来源改为 `engine.search()`，其余提示词/流程不动。
3. **`evaluate.py`**：`store.search` 替换为 `engine.search()`；四指标打分逻辑零改动；评测报告里标注 `engine=weknora-lite`。
4. **`app.py`**：`/api/kb/ask` 的 knowledge 分支改为 `engine.chat()`；新增 `/api/admin/kb/weknora/*` 转发（列表/上传/分块查看），复用 `@require_admin`。
5. **前端 `AdminKB.jsx`**：知识库管理页签改调 WeKnora 转发接口（文档列表/上传/解析状态/分块预览）；顶部加"打开 WeKnora 控制台"外链（管理员高级入口，走 8805）。
6. **部署**：`docker-compose.yml` 增加两个 service（`weknora`、`docreader`），同一 compose 编排、同一内网；门户容器 env 注入 `WEKNORA_BASE_URL=http://weknora:8080`（容器内端口）。

## 六、切片划分（每片独立可验证、可回滚）

- **Slice W1 · 引擎上线**：阿里云部署 weknora-lite + docreader → 建"智能制造专区"KB → 传 1 篇文档 → `knowledge-search` 冒烟通过。**不含任何门户代码改动**，纯基建，失败零影响。
- **Slice W2 · 管理侧对接**：`engine.py` + `AdminKB` 改造 + 8 篇文档迁移 + 分块预览。验收：后台能传/能看/能删，文档解析状态可见。
- **Slice W3 · 问答切换**：`/api/kb/ask` knowledge 分支转发 WeKnora chat；前端问答 UI 不变；意图路由回归（你好→smalltalk、知识问题→WeKnora）。
- **Slice W4 · 评测/PRD 切换 + 收尾**：PRD 接地与评测被测对象切到 engine；跑 30 题评测集出四指标基线；旧检索代码标记 `@deprecated`（下版删）。

## 七、风险与回滚

| 风险 | 缓解 |
| --- | --- |
| WeKnora 容器起不来 / API 不通 | `WEKNORA_ENABLED=false` 一键回退旧检索（旧代码整个版本周期保留） |
| Simple 解析引擎吃不下某类文档 | 上传时按文档类型预检，扫描件提示"解析质量可能受限"；后续升标准版 docreader |
| 迁移后检索质量波动 | W4 用同一套 30 题评测集对比迁移前后四指标，掉点明显则回退并排查 |
| 8805 意外暴露公网 | compose 里 8805 只绑 127.0.0.1 / 内网，防火墙不放行；管理员访问走 SSH 隧道 |
| 内存超预期 | compose 加 mem_limit（weknora 1G / docreader 1G），超限重启不拖垮门户 |

## 八、验收标准（真机）

1. `docker compose ps` 三个容器 Up，`free -h` 显示增量 < 1.2GB。
2. 后台上传一篇新 PDF → 解析完成 → 分块预览可见。
3. 门户问答："什么是数字孪生" → 走 WeKnora 返回带引用回答；"你好" → smalltalk 人设话术不变。
4. PRD 生成：grounded=true 且命中数 > 0（来源为 WeKnora）。
5. 评测：30 题跑完四指标出数，报告标注 `engine=weknora-lite`。
6. 回滚演练：`WEKNORA_ENABLED=false` 重启后问答/PRD/评测回到旧链路。
