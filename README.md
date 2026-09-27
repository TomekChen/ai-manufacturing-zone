# 智能制造专区 · AI 制造应用门户与多智能体编排平台

> 让每家制造厂，都有自己的 AI 供应商。

一个面向制造业客户的 **AI 应用演示门户 + 多智能体编排平台**：访客在门户浏览行业解决方案、与知识库问答、体验多智能体协作；管理员在后台管理知识库（RAG / WeKnora 双引擎）、监测问答质量、沉淀售前方案会话。已在线上运行并持续迭代。

## 功能特性

**门户（访客）**
- 行业解决方案展示：预测性维护、质量检测、能效优化等场景化智能体卡片
- 知识库问答：意图路由（知识/闲聊/超范围）+ 多轮上下文 + 可插拔检索策略（BM25 / 向量 / 混合）
- 售前方案师：填「公司 + 业务介绍」生成面向该客户的《AI 智能体平台需求 PRD》，**生成即存档**——多版本回放、只读分享链接（`/s/<id>`），旧版本永不覆盖
- 预约演示：落盘 + 邮件通知，独立限流

**多智能体编排（A2 起）**
- 注册表模式：`agents/` 包 import 即注册，单一事实来源
- planner 派发：任务文本按触发词路由到 live 智能体，`run(payload) → {ok, agent_id, result, refs, confidence}`
- 已内置：售前方案师（prd）、知识管家（kb-assistant，复用公开问答内核）

**管理后台**
- 项目卡片 CRUD、外观配置、健康探活
- 知识库双引擎：自研 RAG（分块/嵌入/重建/文档审核）与 WeKnora LITE（`WEKNORA_ENABLED` 一键切换，旧链路即回滚网）
- 问答遥测看板：总量/拒绝率/策略对比/趋势/👍👎/未命中清单；离线 RAGAS-lite 评测
- 友情链接管理与一键采集入库
- **方案会话沉淀 → know-how 入库飞轮**：一键把售前会话最新版方案送入知识库待审队列，批准后知识管家即可引用（人工把关，会话变资产）
- 预约列表、平台探针

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React 18 + Vite，单页应用，原生 CSS |
| 后端 | Python 3.12 + Flask，Blueprint 按域拆分 |
| RAG | 自研：FAISS 向量检索 + BM25 + 混合召回 + 遥测；LLM/嵌入走阿里云百炼（qwen / text-embedding-v3） |
| 知识引擎（可选） | [WeKnora LITE](https://github.com/Tencent/WeKnora) 侧车容器（8805） |
| 部署 | Docker Compose，数据卷挂载，零外部数据库依赖 |

## 项目结构

```
├── app.py               # Flask 装配入口：配置/鉴权/项目管理/预约/智能体端点 + SPA 服务
├── kb_admin.py          # 知识库管理域：文档审核/采集/重建、WeKnora 转发、遥测看板、评测、友链
├── prd_sessions.py      # 售前方案会话账本：生成即存档/版本回放/只读分享/一键入库
├── notify.py            # 邮件通知（预约演示）
├── agents/              # 多智能体包：registry（注册表）/ runtime（依赖注入）/ planner / 各智能体
├── rag/                 # 知识库引擎：store（存储）/ engine（WeKnora 桥）/ intents / chunkers /
│                        #   retrievers / embedding / llm / evaluate（离线评测）/ telemetry
├── src/                 # React 前端（api.js 统一请求封装 + 各页面组件）
├── tests/               # 离线自组织断言测试（10 个文件，260+ 断言，不依赖外部服务）
├── docs/archive/        # 历史设计文档与报告归档（增量真相来源见 DEV_LOG.md）
├── DEV_LOG.md           # 开发日志：每个切片的背景/设计/测试/坑——唯一增量真相来源
├── Dockerfile           # 后端镜像（python:3.12-slim + 编译好的 dist）
└── docker-compose.yml   # 编排（含 WeKnora 网络接入与全部环境变量）
```

模块约定：**依赖单向**（入口 → 业务模块 → 数据层），业务模块不 `import app`，共享设施（限流/鉴权/存储）通过 `init()` 依赖注入；新增域照抄 `prd_sessions.py` 的 Blueprint + 注入模式。

## 快速开始

本地开发（前端热更新 + 后端直跑）：

```bash
# 后端（Python 3.10+）
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Windows；Linux/macOS 用 .venv/bin/pip
cp .env.example .env                              # 填 DASHSCOPE_API_KEY 才有问答/PRD 生成
python app.py                                     # http://127.0.0.1:8804（指向 dist/，需先构建前端）

# 前端
npm install
npm run dev                                       # Vite 开发服务器
npm run build                                     # 产出 dist/ 供后端托管
```

默认管理员账号 `admin / admin123`——生产环境**务必**通过环境变量覆盖。

## 测试

```bash
# 全量离线测试（缺 faiss/bs4 时测试文件自带桩，无需额外安装）
python tests/test_prd_sessions.py    # 单个文件
for f in tests/test_*.py; do python "$f"; done   # 全部（10 文件，260+ 断言）
```

## Docker 部署

```bash
cp .env.example .env    # 填好 ADMIN_PASSWORD / SECRET_KEY / DASHSCOPE_API_KEY
docker compose up -d --build
curl http://127.0.0.1:8804/api/kb/stats   # 冒烟：HTTP 200
```

- 数据全部落在 `./data` 卷（知识库、会话、预约、配置），升级镜像不丢数据
- 需要接入 WeKnora LITE 时保持 compose 里的 `weknora` 外部网络；不需要则 `WEKNORA_ENABLED=false` 走自研链路
- 邮件通知：`SMTP_*` 填 QQ 邮箱 SMTP 授权码（非登录密码）；留空则预约照常受理、只是不发邮件

## 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `HOST_PORT` | 宿主机映射端口 | `8804` |
| `ADMIN_ACCOUNT` / `ADMIN_PASSWORD` | 管理员账号/密码 | `admin` / `admin123` |
| `SECRET_KEY` | 令牌哈希盐，生产必改随机串 | `change-me-in-production` |
| `DASHSCOPE_API_KEY` | 百炼 Key：嵌入 + 问答 + PRD 生成 | 空（相关功能返回明确报错） |
| `WEKNORA_ENABLED` | WeKnora 引擎开关（回滚网） | `true` |
| `SMTP_HOST/PORT/USER/PASS`、`NOTIFY_TO` | 预约邮件通知 | 空（跳过发送） |

## API 概览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/kb/stats` `/api/kb/ask` `/api/kb/feedback` | 公开问答与反馈（限流） |
| POST | `/api/kb/upload` | 公开文档上传（进待审） |
| POST | `/api/agents/dispatch` `/api/agents/<id>/run` | 多智能体派发/直跑（限流） |
| POST | `/api/prd-sessions` | 方案会话存档（自动，限流） |
| GET | `/s/<id>` | 方案会话只读分享页 |
| * | `/api/admin/*` | 管理域（Bearer token 鉴权）：kb 文档/采集/重建/WeKnora/遥测/评测、项目 CRUD、方案会话入库、预约列表、友链 |

完整行为以 `DEV_LOG.md` 各节与 `tests/` 断言为准。
