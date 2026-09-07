# 智能制造专区 · 开发日志（DEV_LOG）

> 项目：智能制造专区（ai-manufacturing-zone）
> 服务器：180.127.11.169:21828（容器）→ 应用端口 8804 → 外部地址 http://180.127.11.169:21886/
> 技术栈：前端 React + Vite（单文件 SPA），后端 Flask（Python），数据存 JSON 文件
> 本文档用通俗中文记录开发过程，方便非技术同事看懂在做什么。

---

## 一、项目背景

专区原本是一个"项目矩阵"展示页：顶部大标题（Hero）+ 解决方案卡片 + 智能体项目卡片 + 管理后台。

老板提出改进要求：在专区顶部做一张**"智能制造 AI 智能体整体解决方案架构图"**，逻辑是
`企业层级 → 部门 → 业务场景 → 智能体集群 → 能力中台 → 技术底座 → 算力/基础设施`，
风格参照组织架构图，用户点击业务场景能看到对应智能体列表。

采用敏捷开发：先做原型，每一步跟老板确认。

---

## 二、需求对齐记录

### 第一轮（原型阶段）
| 决策点 | 结论 | 理由 |
|--------|------|------|
| 架构图位置 | 替换原 Hero 区 | 老板说"展示在专区顶部" |
| 点击交互 | 弹出右侧侧边栏展示智能体 | 不离开当前视图，体验流畅 |
| 视觉风格 | 现代科技感（深色+发光边框+渐变+hover动效） | 契合专区整体暗色调 |
| 数据来源 | 原型先硬编码，结构按可配置设计 | 快速出效果给老板看 |

### 第二轮（本轮 · 老板给了真实企业资料）
老板发来《东莞市老友五金制品有限公司2025》产品册 PDF，说"这个企业就是智能制造行业"，
并强调"还有一些行政、管理部门"。

**从 PDF 提炼出的真实组织架构（第3页组织架构图）：**
- 顶层：总经理 → 副总 / 生产厂长
- 8 个部门：财务部、工程部、行政部、业务部、PCM部、生产部、模具部、品质部
- 各部门下属岗位见"功能清单"

**结论：把原型里的通用部门换成这家企业的真实 8 部门，并补齐行政/管理部门的场景。**

---

## 三、功能清单（通俗中文）

1. 专区顶部展示一张五层架构图，最上方是"总经理→副总/生产厂长"的组织层级。
2. 架构图按真实企业 8 个部门展开：每个部门列出它的典型业务场景。
3. 每个业务场景对应一个 AI 智能体，点击场景从右侧滑出详情栏，显示智能体名称、职责、能力清单。
4. 架构图往下依次是：智能体集群 → Agent协同调度中枢 → AI能力中台 → 技术底座&算力 → 三种部署模式 → 数据流闭环。
5. 排版参照组织架构图风格，层级清晰、连接线明确。
6. 管理后台可维护项目卡片（沿用原有能力，本轮不动）。

**明确不做的（边界）：**
- 本轮架构图数据仍硬编码，不做后台可视化编辑架构（下一轮再做）。
- 不改后端 Flask 接口。
- 不做真实智能体的对接，只做展示原型。

---

## 四、真实部门 → 业务场景 → AI 智能体 映射（依据 PDF 整理）

| 部门 | 典型业务场景 | 对应 AI 智能体 |
|------|-------------|---------------|
| 生产部 | 压铸排产、产线异常处置、产能分析、装检工单跟踪 | 生产调度智能体 |
| 品质部 | AI视觉质检、不良根因分析、SPC数据分析(CPK)、质检报告生成 | 质检分析智能体 |
| PCM部 | 库存优化、物料齐套(MC)、生产计划(PC)、仓库出入库 | 供应链计划智能体 |
| 模具部 | 模具设计评审、制模进度跟踪、CNC加工排程、模具验收 | 模具工艺智能体 |
| 工程部 | 项目交付跟踪、图纸/BOM设计问答、新品试产分析 | 工艺研发智能体 |
| 业务部 | 订单跟单、客服问答、交期预警、客户报价 | 业务跟单智能体 |
| 行政部 | 智能考勤排班、设备科预测性维护、IT运维、后勤管理 | 行政人事智能体 / 设备运维智能体 |
| 财务部 | 智能报销审核、成本核算分析、应收应付预警 | 财务分析智能体 |

（设备运维单列：PDF 里"设备科"隶属行政部，但预测性维护是独立智能体，映射时兼顾。）

---

## 五、任务拆分（垂直切片）

| 任务 | 内容 | 依赖 | 状态 |
|------|------|------|------|
| T0 曳光弹 | 架构图替换 Hero + 点击场景弹侧边栏（通用部门版） | — | ✅ 已完成 |
| T1 真实部门 | 重构 architectureData.js 为真实 8 部门 + 总经理层级 + 子岗位 + 10 智能体 | T0 | ✅ 已完成 |
| T2 排版优化 | 新增 OrgTree 组织架构图（总经理→副总/生产厂长→8部门），部门卡带岗位标签 | T1 | ✅ 已完成 |
| T3 部署验证 | 上传构建、本地 8804 验证、外部地址确认 | T2 | ✅ 已构建，待老板外部确认 |

---

## 五·补 本轮（第二轮）实现记录

**改动的三个文件：**

1. `architectureData.js` — 全量重写为真实企业数据。
   - `enterprise`：东莞老友五金制品有限公司（专业光模块结构件 · 锌合金压铸）。
   - `org`：新增组织架构树 `{ ceo: 总经理, branches: [副总 → 财务/工程/行政/业务, 生产厂长 → PCM/生产/模具/品质] }`。
   - `departments`：8 个部门，每个带 `positions`（子岗位）和 `scenarios`（业务场景，指向 agentId）。
   - `agents`：10 个智能体（生产/品质/供应链/模具/工艺研发/业务跟单/设备运维/行政人事/财务/经营决策），各含描述与能力清单。
   - 新增导出 `getDepartmentById(id)` 供组织树取部门名/颜色。

2. `ArchitectureDiagram.jsx` — 新增 `OrgTree` 组件（总经理 → 副总/生产厂长 → 部门叶子），
   插在"企业顶层"和"部门场景层"之间；`DepartmentLayer` 每列加上部门英文名与子岗位标签；
   侧边栏顶部同步显示部门岗位。

3. `architecture.css` — 加组织树样式（顶部连接线、分支框、部门彩色叶子），
   部门网格从 5 列改为 8 列，并补 1280px→4 列、1100px→3 列、768px→2 列（组织树转竖排）响应式。

**部署方式（沿用第一轮踩坑后的方案）：**
文件 base64 分块 → SSH 里 `base64 -d` 落盘 → `rm -rf node_modules/.vite` → `npx vite build` → dist 由 Flask 直服，无需重启后端。

---

## 五·补2 第三轮微调（老板反馈后）

1. **去除具体公司名称（通用官网要求）** — commit `807268e`
   - 顶部企业框：`东莞老友五金制品有限公司` → `智能制造企业`，副标题改为通用表述。
   - 顺带中性化厂商特征词：生产调度去掉"锌合金"，质检"光通信级"→"高精度品质管控"（保留 CPK>1.67、≤50PPM 等通用质量指标）。
   - 组织架构/部门/岗位/场景这些通用内容不动。

2. **字号整体放大（照顾不同年龄段阅读）** — commit `d7395b3`
   - `architecture.css` 全站字号上调一档：正文类 12→15、标签类 10→12、标题类同比放大（主标题 32→40、企业名 18→24 等）。
   - 容器加宽 1400→1560px；部门网格由 8 列改为 **4 列两行**，让放大后的文字有空间不挤。
   - 侧边栏加宽 420→480px，点击/触控留白同步加大；响应式断点重排（≤1100 两列、≤768 单列）。

---

## 五·补3 第四轮（老板反馈项目矩阵三个问题）

老板在后台添加了好几个项目，反馈三个问题：

1. **明明地址能访问，页面却显示"离线"。**
2. **添加项目时选的"主题色"没有任何效果。**
3. **后台配颜色只能手输十六进制，应该有调色板。**

### 问题1：诊断"离线"根因（心跳探测走的是服务器端）

- 现象：外部浏览器能打开的项目地址，后台仍显示"离线"。
- 排查：心跳是**服务器自己去访问**那个地址（`app.py` 后台线程 + requests），不是老板的浏览器。
  经实测确认是 **回环（hairpin NAT）问题**——容器里访问自己的公网地址:端口（`180.127.11.169:2188X`）连不通：
  只有配了内网心跳地址（`127.0.0.1:8800`）的 Pascal 显示在线，其余填公网地址的全部 ConnectTimeout；
  填另一台服务器（219.133.7.139）公网的被 Connection reset。
- 内网实测确认在听的服务端口：8800 / 8801 / 8803 / 8804 / 8805 / 8806（外加 8901 next-server）。
- 解决方案（老板选"加测试按钮 + 我填内网口"）：
  - `app.py` 新增 `probe_url()` + `/api/admin/probe`（需登录），返回 `{alive, status, error}`，
    带中文可读错误（区分"无法建立连接 / 超时 / 5xx / SSL 告警但可达"）。
  - 编辑弹窗里"访问地址""心跳检测地址"各加一个「测试连接」按钮，实时给出在线/离线判定和原因。
  - "心跳检测地址"下加醒目提示：本机项目心跳地址请填**内网** `http://127.0.0.1:<内部端口>/`（如 8804），
    公网地址服务器无法回环访问会误判离线。
  - 即"访问地址"给访客点、保持公网 URL；"心跳地址"给系统探、填内网 URL，两者分开。

### 问题2：让"主题色"真正起作用（老板选"卡片主视觉配色"）

- 根因：主题色以前只体现在"无图片时的头像底色"，且写死成 blue/green… 几个命名类，有图或选任意色就看不见。
- 改法：卡片渲染时用 `toHex()` 把命名色或任意十六进制解析成真实色值，写入 CSS 变量
  `--proj-color / --proj-soft / --proj-glow`，驱动卡片主视觉：
  顶部 4px 渐变条、头像底、角色副标题文字、能力要点圆点、"访问"链接、hover 边框与光晕。
  调色板选任意颜色都能立刻体现在卡片上。

### 问题3：手输十六进制 → 原生调色板

- 项目编辑弹窗 + 后台"外观配置"（主色调 / 画布背景色）全部换成 `<input type="color">` 原生取色器，
  旁边保留一个文本框可微调精确值（用 `.color-picker-row` 布局，色块 + 十六进制预览）。
- 遵循"优先用平台原生能力"原则，不引第三方调色板库。

**本轮改动文件：** `app.py`（新增探测端点，需重启后端）、`src/main.jsx`（测试按钮/提示/色板/卡片配色变量）、
`src/style.css`（`--proj-color` 主视觉 + `.field-hint`/`.probe-badge`/`.color-picker-row` 等表单辅助样式）。

**部署：** base64 上传 3 个文件 → `rm -rf node_modules/.vite && npx vite build` → **`bash start.sh` 重启 Flask**
（本轮不同于前几轮：改了 `app.py`，必须重启后端才生效；前端改动无需重启）。

**验证：** 登录后实测 `/api/admin/probe`——内网 8800/8801/8803/8804/8805/8806 全部 `alive:true (200)`，
公网 `180.127.11.169:21886` 返回 `alive:false` 并给出清晰中文原因，证实回环判断与测试按钮均正常。

---

## 五·补4 第五轮（官网迁移阿里云 + 侧边场景"价值卡"新样式）

### 1. 官网迁移到阿里云，部署方式改为 Docker

老板把官网从原容器迁到了阿里云：新地址 **http://47.115.223.159:8804/**，SSH `root@47.115.223.159:22`。
实测确认新部署形态（和老服务器完全不同，务必记住）：

- 端口 8804 由 **docker-proxy** 监听 → 应用跑在名为 `ai-manufacturing-zone` 的容器里，`python app.py`。
- 工程在宿主机 `/data/projects/ai-manufacturing-zone/`，用 **docker compose** 管理（service=app）。
- 目录：`Dockerfile` + `docker-compose.yml` + `.env`（端口/管理员账号密码/SECRET_KEY）+ `NOTES.md` + `source/` + `data/`。
- **只有 `data/` 是挂载卷**（映射到容器 `/app/data`，存 projects.json、uploads），容器重建不丢。
- `source/` 里只有 `app.py`、`requirements.txt` 和**已编译的 `dist/`**——**没有前端 src 源码，宿主机也没装 node**。
- Dockerfile 逻辑：装 python 依赖 → COPY app.py → COPY source/dist/ → CMD python app.py。

**新的前端部署流程（和以前"上传 src 到服务器再 build"不一样）：**
1. 本地 `F:\projects\ai-manufacturing-zone` 编辑 src → `npm install`（首次；Windows 默认 npm 缓存会 EPERM，
   加 `--cache <工作区目录>` 绕过）→ `npx vite build` 生成 `dist/`。
2. 把 `dist/`（index.html + assets/*.js/*.css）上传覆盖宿主机 `source/dist/`。
3. `cd /data/projects/ai-manufacturing-zone && docker compose up -d --build` 重建镜像并重启容器。
4. `curl 127.0.0.1:8804` 确认返回的是新 hash 的 bundle。

### 2. 侧边弹窗"价值卡"新样式（老板给了参考图，先做 1 张样板）

老板发来 4 张"AI Agent 场景"参考卡（星纪元公众号），说这种效果吸引用户，问加在哪些侧边弹窗合适。
拆解参考卡好看的三要素——**① 三个量化 KPI 大数字 ② 一条"处理流程"步骤链 ③"引入前痛点✗/引入后收益✓"对比色块**，
这三样我们原来的侧边弹窗（点业务场景滑出的 `DetailSidebar`）都没有。

**契合度判断：** 这套"流程+数字"叙事最适合**交易/决策类、能量化前后对比**的场景——业务部（订单跟单/客服/交期）、
PCM（齐套/库存/排程）、财务（报销发票识别）、品质（视觉质检）、生产（排产/异常）、设备（预测性维护）。
**不适合**的是仪表盘类（经营看板）和纯知识问答类（人事政策/IT运维/图纸问答），它们没有清晰步骤链，硬套别扭。

**老板拍板：** 先做 1 张样板（选最契合的「业务部 · 订单智能跟单」），用行业标杆示意数字，满意再铺开。

**实现（向后兼容，最小改动）：**
- `architectureData.js`：给 `biz-order` 场景加一个可选的 `feature` 对象（category / summary / metrics[3] /
  flowLabel+flow / before / after）。**只有带 feature 的场景走新样式，其余场景保持原样**，方便逐张铺开。
- `ArchitectureDiagram.jsx`：`DetailSidebar` 判断 `scenario.feature` 存在则渲染价值卡（分类标签→高亮描述→
  KPI 三宫格→流程链→痛点/收益对比块→"核心能力"补充），否则走旧的简洁布局。加了个 `highlightAI()`
  把描述里的"AI 智能体"高亮（用 split+map，不用 innerHTML）。
- `architecture.css`：新增 `.arch-feature/.arch-metrics/.arch-flow/.arch-callout(-before/after)` 等样式，
  沿用站点暗色主题（痛点红调、收益绿调），未做浅色版。

**部署：** 本地 build 出 `index-BNP_Z86c.js` / `index-fvoekS0l.css` → 上传覆盖 `source/dist/` →
`docker compose up -d --build` → 容器重建，线上已返回新 bundle 且含"引入前痛点"标记。

**老板确认：** 打开后满意，拍板"就这个观感，全部场景铺开"。

### 3. 样板验收后铺开到全部 24 个业务场景

老板认可样板观感，要求所有场景弹窗统一升级为价值卡。逐场景补 `feature` 内容：

- 8 个部门 24 个业务场景全部加 `feature`（category / summary / metrics[3] / flowLabel+flow / before / after），
  KPI 仍用行业标杆示意数字（通用站无真实客户数据）。
- **流程链有两种形态**：大多数场景是"接收→处理→输出"的线性步骤，用 `→` 箭头；
  但「产能瓶颈分析」「模具设计评审」本质是**并列评估维度**、没有先后顺序，硬套箭头会别扭。
  给 `feature` 加了可选的 `flowStyle:'dims'`，侧边栏据此把分隔符从 `→` 换成中点 `·`（`.arch-flow-dot`），
  `flowLabel` 也相应写成"评估维度"。
- 无 `feature` 的场景保留旧简洁布局（向后兼容判断仍在），目前 24 个都已带上，等于全量切换。

**部署：** 本地 build 出 `index-D4PNeRoN.js`（189 kB）/ `index-BIRSsk1_.css`（34 kB）→ 上传覆盖 `source/dist/` →
`docker compose up -d --build` → 容器重建，线上 `curl` 返回新 bundle 且含"引入前痛点"标记。

---

## 五·补5 第六轮（底层知识库：公网采集 + 用户上传 + RAG 问答 + 友情链接）

### 1. 需求背景（与老板对齐）

老板要求"底层知识库要采集行业的公网信息 + 企业用户上传"，页面上要有问答功能。
经逐项确认的决策：

| 决策点 | 结论 |
|--------|------|
| 数据源 | 公网采集 + 用户上传，一期同时做 |
| 检索方案 | FAISS 文件型（本地 index 文件，无外部数据库） |
| LLM/嵌入 | 阿里云百炼 MaaS：qwen-plus + text-embedding-v3（compatible-mode/v1，OpenAI 协议） |
| 用户上传审核 | 需要管理员审核（pending → approve 入库 / reject） |
| 上传格式 | TXT / Markdown / PDF |
| 采集方式 | 管理员后台录入 URL 触发抓取（不做定时爬虫） |
| 问答入口 | 首页新增"知识库问答"模块，访客免登录可用 |
| 友情链接 | 底部展示权威站点；后台可增删改；每条链接可"一键采集入库"（解决"不知道去哪爬"） |
| 用户隔离 | 不做（全部公共知识库，私人库后续扩展） |

### 2. 实现内容

**后端（新增 `kb.py` 知识库引擎 + `app.py` 新增 13 个路由）：**

- `kb.py`：百炼嵌入/LLM 客户端（每批最多 10 条嵌入、失败给中文错误）、
  文本切块（约 600 字/块、重叠 80、句读处断开）、网页正文抓取（requests + BeautifulSoup，剔除导航/脚本）、
  PDF 文本提取（pypdf）、`KnowledgeStore` 类（文档审核流转 + FAISS IndexIDMap2 索引读写 + 检索 + RAG 问答 + 友情链接管理）。
- 数据文件全部在 `data/` 挂载卷内：`kb_docs.json`（文档元数据）、`kb_chunks.json`（分块文本）、
  `kb_index.faiss`（向量索引）、`kb_meta.json`（自增 id）、`links.json`（友情链接）。
- 审核流转：用户上传 → pending（只存文本不嵌向量）；管理员通过 → 此时才嵌入入索引；拒绝/删除 → 索引同步移除（remove_ids）。
- 管理员主动采集（后台录 URL / 友情链接一键采集）视为已审核，直接 approved 入库。
- 问答：检索 top-5 → 拼参考资料 prompt → qwen-plus 生成，带引用来源（标题+URL+摘要，去重）；
  知识库无相关内容时诚实告知，不让模型编造。
- 防滥用：公开问答限流每 IP 每分钟 10 次、上传每 5 分钟 6 次；上传限 TXT/MD/PDF、10MB。

**前端（新增 4 个组件 + main.jsx 接入）：**

- `KnowledgeQA.jsx`：首页"知识库问答"模块——对话式 UI（建议问题气泡、回答带参考来源）、
  旁边"＋上传资料"公开上传按钮（免登录，提示审核后入库）。
- `LinkFooter.jsx`：底部"推荐站点"友情链接条——访客点击跳转；管理员登录时每条链接旁出现"采集"小按钮。
- `AdminKB.jsx`：后台"知识库管理"标签——URL 采集输入框、统计（已入库/待审核/知识块数）、
  状态筛选（待审核/已入库/已拒绝/全部）、审核操作（通过/拒绝/重新通过/删除）。
- `AdminLinks.jsx`：后台"友情链接"标签——链接增删改 + 每条"采集入库"按钮。
- 导航栏加"知识问答"锚点；首次启动自动预填 6 个智能制造权威站点（工信部、e-works、工控网、中国智能制造网、赛迪、电子标准院）。

**部署配置：** `Dockerfile` 加 `COPY source/kb.py`；`docker-compose.yml`/`.env` 加 `DASHSCOPE_API_KEY`
（`.env.example` 提供模板，真实 key 只在服务器 `.env`，不进 git）；`requirements.txt` 新增
numpy / faiss-cpu / pypdf / beautifulsoup4。Dockerfile 与 docker-compose.yml 从此纳入 git 版本控制。

### 3. 端到端验证（全部通过）

| 验证项 | 结果 |
|--------|------|
| 公开上传 TXT → pending | ✅ 返回"等待管理员审核" |
| 管理员登录 → 通过审核 | ✅ 嵌入入库（真实调百炼嵌入） |
| RAG 问答（内网+公网） | ✅ qwen-plus 基于知识库回答，带引用来源，未编造 |
| 后台录 URL 采集工控网首页 | ✅ 8546 字、15 个知识块直接入库 |
| 友情链接一键采集 e-works | ✅ 4441 字、8 个知识块直接入库 |
| 删除文档 | ✅ 向量同步移除（16→15 块） |
| 公网 47.115.223.159:8804 | ✅ 新 bundle index-BnShum0V.js 上线 |
| 默认友情链接初始化 | ✅ 6 条权威站点 |

### 4. 踩坑记录

- **本地冒烟测试用 mock 嵌入**：写了个临时脚本 mock `kb.embed_texts`，把"切块→pending→approve→search→reject→delete"
  全流程在本地跑绿再上服务器，避免拿线上环境试错。真实百炼调用只在服务器端验证。
- **Git Bash 的 curl -o /tmp/xxx 路径陷阱**：Windows 原生 curl 不认 MSYS 虚拟 `/tmp`，文件写到了别处；
  验证公网接口时改为直接管道输出，不落盘。

---

## 六、踩坑记录（现象 → 原因 → 解决）

1. **黑屏 + `DEFAULT_FEATURES is not defined`**
   - 现象：外部地址访问全黑，控制台报 ReferenceError。
   - 原因：删掉了 DEFAULT_FEATURES 常量，但下方"解决方案"区还在 `.map()` 引用它。
   - 解决：连带删除整个 solutions section（架构图已覆盖该内容）。

2. **构建产物不含新数据（grep 到 0）**
   - 现象：源码明明有"生产部"，但 dist 里搜不到。
   - 原因：Vite 缓存 node_modules/.vite 未清。
   - 解决：`rm -rf node_modules/.vite` 后重新 build。

3. **SFTP 上传超时 / shell 吞引号**
   - 现象：直连 SFTP createWriteStream 卡住；python3 -c 内联命令引号被吞报语法错。
   - 原因：容器网络 + 多层 shell 转义。
   - 解决：文件 base64 单行编码，SSH 里 `echo '<b64>' | python3 decode_b64.py <目标>` 落盘。

4. **后台"心跳"把能访问的项目误判为离线**
   - 现象：外部浏览器能打开的项目，后台显示"离线"。
   - 原因：心跳是服务器端主动探测，容器无法回环访问自己的公网地址:端口（hairpin NAT）。
   - 解决：本机项目的"心跳地址"填内网 `http://127.0.0.1:<内部端口>/`；
     "访问地址"仍填公网 URL 给访客点。新增「测试连接」按钮 + `/api/admin/probe` 让管理员自查并看到具体原因。

5. **改了 `app.py` 但后端行为没变**
   - 现象：加了新接口，请求却 404。
   - 原因：前几轮只改前端，dist 由 Flask 直服无需重启；但后端代码改动必须重启进程。
   - 解决：`bash /root/ai-manufacturing-zone/start.sh`（内含 pkill + setsid 重启）；watchdog 每 30s 兜底，端口活着就不干预。

6. **迁阿里云后按老办法上传 src 到 /root 失败**
   - 现象：`/root/ai-manufacturing-zone` 不存在，8804 由 docker-proxy 监听，宿主机没有 node，也找不到前端 src。
   - 原因：迁移改成了 Docker 部署，源码只在宿主机 `source/`（且只留 app.py + 编译好的 dist），前端 src 不在服务器上。
   - 解决：改为"本地 vite build → 上传覆盖 `source/dist/` → `docker compose up -d --build`"；
     本地 `npm install` 报 EPERM（Windows 默认 npm 缓存被占用），加 `--cache <可写目录>` 绕过。

---

## 七、项目结构

```
ai-manufacturing-zone/
├── app.py                    # Flask 后端：配置/项目/心跳/上传/登录/知识库/友情链接 API + 静态托管
├── kb.py                     # 知识库引擎：百炼嵌入/LLM、切块、抓取、FAISS 索引、KnowledgeStore
├── Dockerfile                # Docker 镜像构建（纳管版本控制）
├── docker-compose.yml        # 编排（含 DASHSCOPE_API_KEY 透传）
├── .env.example              # 环境变量模板（真实 .env 不进 git）
├── index.html                # Vite 入口
├── vite.config.js            # base:'./' 相对路径
├── package.json              # react + vite
├── requirements.txt          # flask + requests + numpy + faiss-cpu + pypdf + bs4
├── start.sh                  # 启动脚本（PORT=8804，历史遗留）
├── watchdog.sh               # 进程守护（历史遗留）
├── data/                     # 运行时数据（挂载卷，不进 git）
│   ├── projects.json         # 项目卡片数据
│   ├── config.json           # 站点外观配置
│   ├── kb_docs.json          # 知识库文档元数据
│   ├── kb_chunks.json        # 知识库分块文本
│   ├── kb_index.faiss        # FAISS 向量索引
│   └── links.json            # 友情链接
└── src/
    ├── main.jsx              # 主应用（导航/管理后台/项目矩阵）
    ├── KnowledgeQA.jsx       # 首页知识库问答 + 公开上传
    ├── LinkFooter.jsx        # 底部友情链接（管理员可快捷采集）
    ├── AdminKB.jsx           # 后台知识库管理（审核/URL采集）
    ├── AdminLinks.jsx        # 后台友情链接管理
    ├── style.css             # 全局样式
    ├── ArchitectureDiagram.jsx  # 五层架构图组件 + 侧边栏
    ├── architecture.css      # 架构图样式
    └── architectureData.js   # 架构数据（部门/场景/智能体映射）
}
```

---

## 八、启动方式

**当前（阿里云 Docker）：** 工程在 `/data/projects/ai-manufacturing-zone/`，`docker compose up -d --build` 起停；
访问 http://47.115.223.159:8804/。端口/管理员账号密码/SECRET_KEY 在 `.env` 改，改完 `docker compose up -d` 生效。
前端改动：本地 `F:\projects\ai-manufacturing-zone` 编辑 src → `npx vite build` → 覆盖 `source/dist/` →
`docker compose up -d --build`（宿主机没有 node，不能就地 build）。后端 `app.py` 改动同理走 `--build` 重建镜像。

**（历史·已废弃）原容器直跑：** `cd /root/ai-manufacturing-zone && bash start.sh`（Flask 监听 8804），
前端上传 src 后在服务器 `npx vite build`。迁阿里云后不再用这套。

---

## 九、已知限制

- 架构图数据硬编码，改内容需改代码重新构建（下一轮做后台可配置）。
- 智能体是展示原型，未对接真实可运行的智能体服务。
- 知识库为全局公共库，无用户/企业隔离（后续按需扩展私人知识库）。
- 文本切块为固定长度策略（600 字/块），未做语义切块；检索 top-5 固定。
- 问答限流为单进程内存计数，容器重启清零（够用，未上 Redis）。
- 采集仅支持单页抓取，不做整站爬取/定时任务（边界明确，防止失控）。

---

## 十、第七轮：回答 Markdown 渲染 + 采集结果可见性

**需求来源**：用户实测反馈两个问题——
1. 首页问答回答仍是 Markdown 源码（`**加粗**`、`- 列表` 直接显示），对访客不友好；
2. 管理员采集后不知道"采到了哪些数据、采下来的内容长啥样"。

**改动**：
- 前端新增 `src/markdown.js`：轻量 Markdown→HTML（标题/加粗/斜体/有序无序列表/行内代码），先做 HTML 转义再渲染，可安全 `dangerouslySetInnerHTML`；不引入额外 npm 依赖（绕开本机 npm safe-delete 卡死）。
- `src/KnowledgeQA.jsx`：AI 回答改走 `renderMarkdown` 渲染，新增 `.qa-answer-content` 暗色主题排版样式（标题/列表/加粗/code 均按现有设计令牌）。错误与用户消息仍纯文本。
- 后端 `kb.py` 新增 `get_doc_detail(doc_id)`：返回文档元数据 + 完整分块文本 `chunks` + `chunk_count`。
- 后端 `app.py` 新增 `GET /api/admin/kb/docs/<doc_id>`（管理员鉴权），用于单文档预览。
- 前端新增 `src/DocPreview.jsx` 弹窗组件：展示标题/URL/状态/来源/字数/知识块数，并逐块预览正文（超 240 字折叠"展开/收起"）。
- `src/AdminKB.jsx`：文档列表每行加"预览"按钮；管理员 URL 采集成功后自动弹出所采文档的预览（显示字数、块数、分块内容）。
- `src/AdminLinks.jsx`：友情链接"采集入库"成功后同样自动弹出预览。

**验证**：
- 公网首页 `index.html` 含新 bundle 指纹（`index-CCO6lwVH.js`）→ 前端已生效；
- `GET /api/admin/kb/docs/<id>` 返回 `chunk_count` + `chunks`（实测首份文档 7 块、首块 587 字）；
- `GET /api/kb/stats` 返回 `approved:7, chunks:101`（知识库存量未丢，重建后数据卷正常）。

**已知限制更新**：问答 Markdown 已渲染；采集结果可在后台预览。仍不支持整站爬取/定时自动采集（边界明确）。

---

## 十一、第八轮：修「看不到入库内容」+「采集全是子标题没用」

**需求来源**：老板实测反馈两个问题——
1. 后台"知识库管理"里看不到入库的东西是什么；
2. 采集下来的基本都是网站的子标题，没什么用。

**根因定位（读代码 + 跑测试确认，非猜测）**：
- 问题①其实不是没入库，是**列表默认停在"待审核"标签**（`AdminKB.jsx` 里 `useState('pending')`）。
  而采集入库走的是 `_crawl_to_kb`，以 `approved`（已入库）状态直接写，绕过待审核 → 待审核页永远空。
  预览正文的能力第七轮已经有了（每行"预览"按钮 + `DocPreview`），只是被默认筛选挡住了入口。
- 问题②是**喂给采集器的是门户网站首页**（提示语举例、6 条友情链接默认值全是首页）。
  首页正文本来就是一堆栏目名 + 文章标题；旧的 `fetch_url_text` 只是"整页去标签"，
  于是把首页的标题列表当成正文入库（第七轮验证里"采集工控网首页 8546 字""采集 e-works 4441 字"其实多是这类标题）。

**改动**：
- `src/AdminKB.jsx`：默认筛选 `pending → all`；采集输入框提示语改成"粘贴【具体文章页】地址（不要网站首页）"；
  下方加一条黄色提示 `.kb-crawl-hint`，说明首页抓出来只有栏目导航、采集成功会自动弹预览。
- `src/style.css`：新增 `.kb-crawl-hint` 样式（复用 `--surface-2 / --warning` 设计令牌）。
- `kb.py` 重写 `fetch_url_text` 为简易正文抽取（readability-lite）：
  ① 丢弃结构性噪音标签（script/style/nav/header/footer/aside/form/button…）；
  ② id/class 命中噪音词（comment/related/recommend/copyright/menu…）且文本 <600 字的块删掉（阈值防误删正文）；
  ③ 用"语义正文容器优先（article/main/.content/.TRS_Editor/#UCAP-CONTENT…）→ 否则按 `文本量×(1-链接密度)` 打分取最高"
     定位正文（链接密度低=像正文，高=像导航列表）；④ 标题优先 `og:title`/`twitter:title` → `<h1>` → `<title>`（去掉 `_站点名` 后缀）。
- `kb.py` 新增 `looks_like_nav_page(text)`：抽出来的"正文"若没有一行像句子（长度≥40 或含句读），判定为首页/列表页。
- `app.py` `_crawl_to_kb`：入库前调用 `looks_like_nav_page`，命中就报错
  "抓到的内容像是网站首页/栏目列表（全是标题、没有正文），请粘贴具体文章的详情页地址"，不再静悄悄入库垃圾。

**验证**（本地确定性 fixture 测试，内置 HTML，不依赖外网）：
- 门户首页样本 → 抽出 65 字全是标题；`looks_like_nav_page=True`（会被后端拦截）。
- 文章详情页样本 → 标题正确取到 `og:title`（非带 `_某智造网` 后缀的 title）；正文抽到；
  导航/相关推荐/网友评论/版权"均未误入"（断言 False）；`looks_like_nav_page=False`（正常放行）。
- `python -m py_compile kb.py app.py` 通过。

**部署状态（重要）**：本轮 + 知识库整套（`kb.py`、`app.py` 的 KB 路由、`AdminKB/DocPreview/KnowledgeQA` 等）
目前**只在本地 F 盘，尚未部署到阿里云**——服务器仍跑旧的 308 行 `app.py`（没有知识库）。
上线需要：本地 `npx vite build`（前端）→ 上传 `dist/` + `kb.py` + `app.py` → 镜像装 `faiss-cpu / beautifulsoup4 / pypdf` →
`.env` 配 `DASHSCOPE_API_KEY` → `docker compose up -d --build`。建议先在 PyCharm 本地跑通再部署。


---

## 十二、第九轮：RAG 模块拆分（单文件 kb.py → rag/ 可插拔包）

**需求来源**：老板问「智能制造源码有没有用工厂模式」+「把 rag 代码拆一下，不要一个 kb.py 就是一整个模块」。
核查结论：智能制造源码（`app.py` + 旧 `kb.py`）**没用工厂/策略模式**，旧 `kb.py` 是一个巨型 `KnowledgeStore` 类
把存储、切块、嵌入、检索、生成、采集、友链全包在一起，切块只有单一 `split_text`、检索只有纯向量，加新策略就得改主流程。

**方法论**：先用 disciplined-engineering 对齐需求（复用边界 / 分块生效粒度 / 检索时机 / v1 范围 / 指标类型 / 裁判触发），
达成共识写进 `KB_RAG_REFACTOR_SPEC.md`；再用 TDD 红→绿实现纯逻辑；ponytail 保证不投机抽象（retriever/reranker 等
真实 seam 等到需要第二个实现时再建，本轮不预先塞空壳）。

**本轮做了什么（Slice 1：地基）**：
- 新建 `rag/` 包，把旧 `kb.py` 按职责拆开：
  - `rag/config.py` 配置与默认策略；`rag/embedding.py` 百炼请求+嵌入；`rag/llm.py` 生成；
  - `rag/ingest.py` 网页/文档解析（`fetch_url_text`/`looks_like_nav_page`/`extract_pdf_text` 原样搬来）；
  - `rag/store.py` = `KnowledgeStore`（旧逻辑，仅两处结构变化：切块走 chunker、嵌入/生成改为 import）。
- 引入「注册表（轻量工厂）」：`rag/registry.py` 通用 `Registry`；
  `rag/chunkers/` 下 `base.py`(接口+CHUNKERS 注册表) + `fixed.py`(FixedChunker，等价旧 split_text) + `semantic.py`(段落语义分块)，
  `build_chunker(name, **opts)` 一个工厂函数搞定分块策略选择——**以后加分块策略 = 注册一个类，不动主流程**。
- `rag/fusion.py`：RRF 融合，纯函数、独立可测（混合检索在 Slice 2 接入，本轮先把地基与用例测好）。
- `kb.py` 改成**薄兼容层**：只做 `from rag.store import KnowledgeStore` 等再导出。→ **`app.py` 一行未改**，
  `import kb` 照旧可用（已 `py_compile` + 注入假依赖跑通整条 import 链验证）。

**测试（离线确定性，不碰网络/LLM/FAISS）**：`tests/test_rag_unit.py` 11 条断言全过——
S1 RRF（期望值按 1/(k+rank) 手算：b>a>c）；S2 固定窗口（空/短文/滑动计数 [0:100][80:180][160:250]/句读回缩不吞字）；
语义分块（短段合并/超长段回落固定窗口/短文单块）；注册表（names + 未知策略抛 KeyError）。
默认策略 `fixed` 且参数(600/80)与旧 `split_text` 一致 → **本轮问答行为零变化**。

**尚未做（留给后续切片，见 SPEC §六）**：Slice 2 检索层 retriever 抽象 + BM25/混合 + 提问时选检索方式；
Slice 3 入库逐文档选分块 + 全库重建；Slice 4 在线问答看板（拒绝率/各策略对比/未答清单/👍👎）；
Slice 5 离线 RAGAS-lite 手动评测 + 抽样裁判。

**依赖变化**：新增纯 Python 轻依赖 `rank_bm25`、`jieba`（Slice 2 才真正用到，届时补进 requirements）。
`faiss-cpu / beautifulsoup4 / pypdf` 沿用。

**部署状态**：仍未上线阿里云，全程本地 F 盘 + PyCharm 验证。本轮属纯结构重构，风险低；
建议老板在 PyCharm 里跑一遍现有问答确认无回归后，再继续 Slice 2。

---

## 十三、第十轮：检索层可插拔（向量 / BM25 / 混合 + 提问时选检索方式）

**目标（Slice 2）**：把「检索」从旧 kb 里写死的纯向量，抽成和分块一样的可插拔策略，
让管理员**提问时**就能在向量 / BM25 / 混合之间切换对比，且切换是秒级的（不重跑 embedding、不重建索引）。

**本轮做了什么**：
- 新建 `rag/retrievers/` 子包，沿用 Slice 1 的注册表模式：
  - `base.py`：`Retriever` 接口 + `RETRIEVERS` 注册表；
  - `vector.py`：`VectorRetriever`，把原 `_vector_rank_locked`（FAISS 相似度）包成一个策略；
  - `bm25.py`：`BM25Retriever`，用 `jieba` 分词 + `rank_bm25.BM25Okapi` 建关键词索引；
  - `hybrid.py`：`HybridRetriever`，向量与 BM25 各取 top_n×2 召回，再用 Slice 1 的 `reciprocal_rank_fusion`（k=60）融合排名；
  - `__init__.py`：`build_retriever(name, *, vec_search, bm25, k)` 工厂，**加一种检索 = 注册一个类 + 工厂加一个分支，主流程 store 不动**。
- `rag/store.py` 接入：
  - 新增 BM25 缓存 `_bm25_cache / _bm25_dirty`，文档增删改时置脏，下次检索懒重建（避免每次问答都重算全库 BM25）；
  - `_vector_rank_locked`（拆出的纯向量排名）、`_get_bm25_locked`（建/取 BM25 缓存，**缺 jieba/rank_bm25 或建索引失败时打日志并降级为纯向量，不抛错**）；
  - `search(query, top_k, retrieval=None)` 按名选策略，命中项带 `retrieval` 标注实际生效策略；`ask` 同步透传并把生效策略回给调用方。
  - 默认策略 `hybrid`（`config.DEFAULT_RETRIEVAL`，可用环境变量 `KB_RETRIEVAL` 覆盖）。
- `app.py` `/api/kb/ask`：接收可选 `retrieval` 入参，**在信任边界按注册表白名单校验**（非法值退回默认，防注入未知策略名）；
  `kb.py` 薄兼容层再导出 `RETRIEVAL_OPTIONS / DEFAULT_RETRIEVAL` 供前台下拉与校验取用。**`app.py` 其余路由零改**。

**测试（离线确定性）**：
- `tests/test_rag_unit.py` 仍 11/11（回归不受影响）。
- 新增 `tests/test_rag_retrieval.py` 9/9：BM25 关键词命中（"茅台 营业收入"→茅台、"研发费用"→宁德、分数降序、无匹配返回空、遵守 top_k）；
  混合 RRF（用假向量+假BM25手算融合序 a>c>b>d、两路并集、top_k 截断）；检索注册表 names。
- 端到端集成（注入假 faiss/bs4 + 假零向量嵌入绕开联网）：`search(...,retrieval="bm25")` 与 `retrieval="hybrid"`
  均命中正确文档且 `retrieval` 标注正确；**FAISS 索引为空时 hybrid 自动只走 BM25、不报错**（降级链路验证通过）。

**踩坑**：
- `KB_RAG` 早期把检索写死在 `KnowledgeStore.search` 里；本轮把「选哪个策略」和「策略怎么算」分离——store 只管装配原料（向量排名函数、BM25 实例），
  retriever 只管排名，便于单测里塞假原料、也便于以后加 rerank。
- 验证时发现 2 篇文档的小语料下 BM25 分数恒为 0——这是 `rank_bm25` 的 idf 在极小语料上的固有退化（词只出现在半数文档时 idf=0），**非代码 bug**；
  换成 4 篇正常语料分数即恢复，真实测试用例即用 4 篇。

**依赖变化**：`rank_bm25`、`jieba` 本轮正式启用，需补进 `requirements`（部署时容器内 `pip install`）。

**部署状态**：仍未上线阿里云。KB 整个功能（含这两轮重构）只活在本地 F 盘，服务器仍是旧的、不含知识库问答的 `app.py`。
建议老板在 PyCharm 跑通问答 + 后台切检索方式无异常后再继续；前端「后台下拉选检索方式」属 Slice 2 收尾，需 `npx vite build`，下一步再定。

---

## 十四、第十一轮：后台鉴权收敛成装饰器（去重复样板）

**缘起**：排查「前后端本身有没有用工厂模式」时发现——工厂/注册表在这个项目里其实没有用武之地
（后端 25 个路由各做各的事、前端是数据驱动 React，都不是"同一类事情的多路变体"，硬套反而违反 YAGNI）。
但确实有一处**纯重复样板**：15 个后台路由里每个都手写了两行一模一样的
`if not verify_token(...): return 401`。这不是工厂模式问题，是 DRY 问题，正解是**装饰器**。

**本轮做了什么**：
- `app.py` 新增 `require_admin(fn)` 视图装饰器（内含 `functools.wraps`，保留原函数名，
  否则 Flask 会把所有 endpoint 塌成 `wrapper` 而互相冲突）。
- 把 15 个 `@app.route` 后台路由的鉴权样板统一换成 `@app.route(...)` 下一行的 `@require_admin`。
  路由函数体逻辑、返回结构、状态码**一字未改**，只是删掉了重复的两行守卫。
- 公开路由（`/api/kb/stats`、`/api/links`、`/api/kb/ask`、`/api/kb/upload`）与登录 `/api/admin/login`
  本就不该鉴权，保持不变。

**验证**：`py_compile` 通过；用 Flask `test_client` 冒烟——无 token 访问 4 个后台路由均 401、
带合法 token 放行（200）、公开 `/api/kb/stats` 不受影响、`url_map` 里 25 个 endpoint 名字正常无塌陷。行为与改前完全一致。

**教训（写进 skill）**：抽东西前先分清「这是重复分支该上注册表/策略」还是「这只是重复样板该上装饰器/函数」。
别把工厂模式当万金油——**没有"多态变体"就不要建抽象基类/注册表**，普通去重（鉴权、日志、限流、事务）用装饰器或工具函数更轻更准。

---

## 十五、第十二轮：逐文档选分块 + 重建（Slice 3，D2 落地）

**目标**：让管理员**入库时逐篇选分块方式**（固定窗口 / 语义），策略随文档记录；并提供**单篇重建**（换策略重切重嵌）
和**全库重建**（按各篇自己的策略整体重切重嵌）——这正是把 Slice 1 的 chunker 抽象用起来的地方。

**关键设计发现（先想清楚再动手）**：要「换策略重新切块」，就必须留着**原始全文**。
现有 `kb_chunks.json` 只存切好的块，而 fixed 分块带 80 字重叠，把块拼回去是**有损**的（重叠区会重复、分隔符丢失）。
→ 因此新增一份 `kb_raw.json`（doc_id → 原始全文），入库时写、删除时清。这是重建的前提，不先想透这点会做出个拼不回去的重建。

**本轮做了什么（后端）**：
- `rag/store.py`：
  - `add_text` 记录 `self.raw[doc_id]=全文` 并落盘；`delete` 同步清 raw；
  - 新增 `rebuild_doc(doc_id, chunking=None)`：清旧块+旧向量 → 按新（或沿用原）策略重切 → approved 的重新嵌入。
    **历史无原文的老文档**只能原样重嵌入、拒绝换策略（抛友好提示：请重新上传/采集），不硬拼残缺文本；
  - 新增 `rebuild_all()`：逐篇按各自记录策略重切、从零重建 FAISS 索引，索引向量数 = 所有 approved 篇的块数之和（pending 不进索引）；
  - 抽了两个共用小函数 `_new_chunk_ids`（分配自增块 id）、`_rechunk_locked`（切块+更新元数据），
    让 add_text / rebuild_doc / rebuild_all 复用同一套「分配 id 写块」逻辑，不再各写一遍重复循环。
- `kb.py` 兼容层再导出 `CHUNKING_OPTIONS / DEFAULT_CHUNKING`（取自 CHUNKERS 注册表，单一事实来源）。
- `app.py`：
  - `GET /api/admin/kb/options`：一次返回分块 + 检索的可选项与默认值，**前端下拉框改成读这个接口，不再硬编码策略名**；
  - `POST /api/admin/kb/rebuild`（全库）与 `POST /api/admin/kb/docs/<id>/rebuild`（单篇，body 可选 `chunking`）；
  - `/api/admin/kb/crawl` 采集时也可带 `chunking`；`_crawl_to_kb` 相应加参数透传；
  - 抽 `_clean_choice(raw, options)` 小工具：可选入参「空/非法→退回默认、合法→原样」，
    retrieval 与 chunking 两处共用（又是一处该抽函数、不该抽工厂的样板去重）。
  - 默认全局 `DEFAULT_CHUNKING` 仍为 `fixed`（公开上传零回归）；管理员在后台按需选，语义分块作为可选项。

**测试与验证**：
- 新增 `tests/test_rag_rebuild.py` 6/6（注入假 faiss + 假嵌入，纯离线）：入库记录原文、单篇换策略重切且块 id 全重分配、
  未知策略抛 KeyError、老文档缺原文拒绝换策略、全库重建索引向量数=approved 块数总和、老文档块被保留。
- 回归：`test_rag_unit.py` 11/11、`test_rag_retrieval.py` 9/9 仍全过。
- 端点冒烟（Flask test_client，临时库不碰真实 data/）：options 返回 fixed/semantic + vector/bm25/hybrid；
  一篇 fixed(2块) 换 semantic 重建→1 块且 `re_sharded=True`；全库重建 vectors 与 approved 块数一致；非法 chunking 退回默认不报错；未带 token 一律 401。

**前端收尾（Slice 2+3 合并，一轮做完）**：后台 UI 一次补齐并只 `npm run build` 一次——
- `src/AdminKB.jsx` 重写：进入页面先 `GET /api/admin/kb/options` 拉可选项，**分块 / 检索下拉全部数据驱动，不再硬编码策略名**；
- 「问答调试」面板：选检索方式（vector/bm25/hybrid）→ 调 `/api/kb/ask` → 显示答案 + 参考来源 + 「本次实际检索」标签（读接口回的 `retrieval`，验证退化是否生效）；
- 采集行加「分块方式」下拉（fixed/semantic），采集时随 body 带上 `chunking`；
- 文档表加「分块」列显示每篇记录的策略；每行加「换策略重建」下拉 + 「重建」按钮（单篇 `POST /docs/<id>/rebuild`），工具栏加「全库重建」按钮（`POST /rebuild`，二次确认提示会重花 embedding 额度）；
- 策略中文名在前端集中映射（`CHUNK_LABEL`/`RETR_LABEL`），未知 key 直接原样显示，容错。
- `src/style.css` 补 `.kb-debug*` / `.kb-tag` / `.kb-rebuild-select` / `.kb-crawl-row select` 等样式，全部复用既有 CSS 变量（surface-2/hairline/radius/ink/accent…），不引新色值。

**构建与验证**：`npm run build` 成功（39 模块），产物 `dist/assets/index-*.js` 已含新增串（`admin/kb/rebuild`、`换策略重建`、`问答调试`、`固定窗口`、`语义分块`）。
用假 faiss + 假 bs4 + 假嵌入起完整 Flask 栈冒烟：静态资源 200、`/api/kb/ask`（bm25 / 非法 retrieval）均 200、`options` 返回 `chunking:[fixed,semantic] retrieval:[vector,bm25,hybrid]` 及默认值。
> 注：Windows 本机 `.js` 的 MIME 注册成 `text/plain`（浏览器按内容仍可执行，Linux 部署为 `application/javascript`），冒烟只验状态码 + 产物字节数 + bundle 含新码，不因该 MIME 差异判失败。

**至此 Slice 1/2/3 全部完成（后端 + 前端 + 测试），无遗留。** 下一切片：Slice 4 在线问答看板（`telemetry.py` + 👍/👎 反馈接口 + 后台分析页）。

**部署状态**：仍未上阿里云；`kb_raw.json` 是新数据文件，部署时容器内 data 卷会自动生成，老库首次「全库重建」会把没原文的历史篇按原块保留。前端 `dist/` 为 gitignore 构建产物，未入库。

---

## 十六、第十三轮：在线问答看板（Slice 4，D5-a 落地，零 token）

**目标**：把真实问答流量记下来并聚合成看板，让管理员**不花额度**就能看到「问了多少、哪些答不上、哪种检索更稳、用户满不满意」，据此补知识库缺口或换策略（SPEC §3.3 US-20~24、§四 1–4、§五 Seam S4）。

**关键设计取舍**：
- **聚合写成纯函数** `summarize(records, days, now)`——不读盘、不碰网络/LLM，`now` 可注入，因此 Seam S4 能喂合成日志做确定性断言（拒绝率/命中率/各策略分组/未答清单计数/趋势铺桶/边界口径）。落盘与写反馈留给 `Telemetry` 类，另用临时目录小测覆盖「滚动上限丢最旧」「反馈写回」。
- **「相似度」诚实处理**：`top_score` 是**当前策略返回的首位原始分数**，vector≈余弦、bm25 无界、hybrid 是 RRF 融合值（量纲不同，跨策略不可直接比）。故看板只在**同一策略内**用平均分看趋势（UI 标成「平均最高分」且仅显示数值），顶部数字卡改用**策略无关**的指标：总问数 / 拒绝率 / 👍率 / 平均命中数。避免拿 0.016 和 0.8 摆一起误导。
- **遥测绝不能拖垮问答**：`store.ask` 里 `_log_ask` 用 try/except 包住，写失败只 warning，照常返回答案。遥测用独立文件 `kb_telemetry.json` + 自己的锁，和文档锁解耦；体量小（上限默认 5000 条），沿用项目既有「文件型 + 全量读改写」风格，不引 DB。
- **反馈用 ask_id 关联**：每次 `ask` 生成 `ask_id` 随答案返回；前台 👍/👎 打 `POST /api/kb/feedback{ask_id,rating}` 写回对应记录。反馈是公开接口（访客也能点），故限流 + 校验 rating 归一 + ask_id 必须存在（否则 404），同一条只记一次。

**本轮做了什么**：
- 后端：
  - 新增 `rag/telemetry.py`：`summarize` 纯聚合 + `Telemetry`（`record`/`set_feedback`/`aggregate`，滚动上限 `config.TELEM_MAX`）+ `normalize_question`（未答清单去重归一）。
  - `rag/config.py` 加 `TELEM_MAX`(5000)、`TELEM_TREND_DAYS`(30)（可 env 覆盖）；`kb.py` 兼容层再导出 `TELEM_TREND_DAYS`。
  - `rag/store.py`：`__init__` 建 `self.telemetry`；`ask()` 计时、取 top_score/命中数/是否拒答、生成 `ask_id`、落一条日志并回传 `ask_id`（两条返回路径都带）。
  - `app.py`：`POST /api/kb/feedback`（公开👍👎）、`GET /api/admin/kb/analytics?days=`（`@require_admin`，days 夹在 1–90）。
- 前端：
  - `src/KnowledgeQA.jsx`：答案下加 👍/👎，点一次记一次并回填 `feedback` 状态（已反馈显示「感谢你的反馈」）。
  - 新增 `src/AdminAnalytics.jsx`：顶部数字卡（带轻量 count-up 补间）、各策略并排 CSS 条形对比、问答量趋势（内联 SVG 折线+面积，近 7/14/30 天切换）、未命中问题清单（按频次降序表格）。**零图表库**（§四 决定：几根条用不上重库，且本机装库有坑）。
  - `src/main.jsx` 后台加「问答分析」标签页；`src/style.css` 补 `.qa-feedback*` 与 `.an-*`，全部复用既有设计令牌（surface/hairline/ink/accent/success/warning），不引新色值、暗色一致。
- `.gitignore` 加 `data/kb_telemetry.json`。

**测试与验证**：
- 新增 `tests/test_rag_telemetry.py` **10/10**（Seam S4，纯离线确定性）：总量与各率、窗口过滤与 7 天边界口径、按策略分组（含 avg_top_score 只算非空、up/down 计数）、未答清单归一化去重与频次降序、趋势铺满 N 天且日期升序、空输入安全、文件滚动丢最旧、set_feedback 命中/未命中。
- 回归：`test_rag_unit` 11/11、`test_rag_retrieval` 9/9、`test_rag_rebuild` 6/6 仍全过（合计 **36/36**）。
- 全栈冒烟（假 faiss/bs4/嵌入/LLM）：①store↔telemetry——ask 回传 `ask_id` 且落一条含全字段的记录、未命中记 `refused=True`/`top_score=None`、👍 写回、aggregate 反映 total/feedback_up/趋势 30 桶/未答计数；②端点——analytics 无 token 401、带 token 200 且 `days=14` 生效、feedback 未知 id 404 / 非法 rating 400 / 缺 id 400，且不写真实 data。
- `npm run build` 成功（40 模块，`dist/assets/index-*.js` 219.81 kB、css 48.03 kB），产物含新看板与反馈代码。

**至此 Slice 4 完成（后端+前端+测试），无遗留。** 下一切片：Slice 5 离线 RAGAS-lite 评测（内置小标准题集 + 手动「重跑评测」才花 token + 四指标横向对比 + 可选真实问答抽样裁判 + 后台评测卡 + Seam S5）。

**部署状态**：仍未上阿里云；`kb_telemetry.json` 为新数据文件，容器 data 卷自动生成。公开 `/api/kb/feedback` 与既有 `/api/kb/ask` 同属免鉴权前台接口，靠限流兜底。

---

## 十七、第十四轮：意图路由 + 多轮对话（Slice 5，老板临时改需求）

> **计划变更说明（务必留痕）**：SPEC §六 原定 Slice 5 是「离线 RAGAS-lite 评测」，且「多轮对话记忆」在 SPEC §三被明确列为**超出范围**。本轮老板拍板把 Slice 5 改成**意图路由 + 多轮对话**，RAGAS-lite 评测**顺延为 Slice 6**。多轮记忆从「超范围」改纳入本切片，属对已签功能清单的有意调整，已在此记录，非擅自扩范围。

**目标**：让知识库问答从「单轮死答」升级成——① 先判**意图**（行业知识 / 闲聊问候 / 明显跑题）分流处理；② 支持**多轮追问**，能听懂「那它呢」「还有呢」这类靠上下文的追问；③ 无登录前提下按访客隔离会话，并把上面这些自然接入 Slice 4 的遥测看板。

**关键设计取舍**：
- **意图识别走「规则」不走大模型**：`rag/intents/rules.py` 是纯函数（领域词命中→知识；短寒暄词→闲聊；跑题词→超范围；判不准→默认知识，宁可多答不误拒）。零 token、确定性、可单测，也符合老板「能不调模型就不调、省额度」的取向。`classify_intent / pick_retrieval / needs_rewrite / build_messages` 全可离线断言（Seam S5）。
- **三种意图用「注册表 + 策略类」**（和 Slice 1 分块、Slice 2 检索一个套路）：`rag/intents/` 子包，`base.py` 定义 `IntentHandler` 抽象 + `INTENTS` 注册表，`handlers.py` 注册 knowledge / smalltalk / offtopic 三个处理器，`store.ask` 只做「分类→取处理器→执行→落遥测」的分发。**知识问答分支的系统人设文案与 Slice 4 的旧 `ask` 一字不差**，保证单轮零回归。闲聊走轻量 LLM 友好回应（LLM 挂了降级固定话术），跑题直接给引导话术、**一次都不调模型**。
- **多轮记忆 = 前端带历史、后端保持无状态**：后端不存会话状态，每次请求由前端把 `history`（最近若干条 user/assistant）随 `question` 一起发来。好处：① 天然免登录、无需服务端会话存储；② **每个访客各看各的**——对话记录存在浏览器 `localStorage`（`kb_chats_v1`），换浏览器/清缓存即分开，不同访客互不可见，符合老板「没有注册登录也要每人历史不同」的诉求。
- **多会话侧栏（类 ChatGPT）**：前端 `KnowledgeQA.jsx` 重写成左侧会话列表 + 右侧对话区，可新建/切换/删除会话（删除带二次确认）；窄屏侧栏收成抽屉，用「☰ 会话」顶栏唤出。
- **上下文改写（追问补全）**：`needs_rewrite` 命中指代词或极短追问时，先用一次 `temperature=0` 的小 LLM 调用把追问改写成「不依赖上下文、能独立检索」的完整问题（`REWRITE_SYSTEM`），再拿改写后的句子去检索与作答；改写失败（无 Key / 异常）自动回退原问题，不阻断。`config.HISTORY_MAX`（默认 12，可 env 覆盖）统一裁剪历史长度。
- **遥测顺手记意图**：Slice 4 的 `summarize` 向后兼容——老记录没有 `intent` 字段一律归入 knowledge；`by_strategy` 只统计**真正走了检索**的问答，闲聊/跑题的 `retrieval=None` 被剔除，不污染各策略对比。看板新增 `intents` 三分类计数，`Telemetry` 记录新增 `intent / rewritten / turns` 三字段。

**本轮做了什么**：
- 后端：
  - 新增 `rag/intents/`（`__init__.py` 触发注册并再导出 `classify_intent/build_intent`；`rules.py` 纯规则；`base.py` 抽象+注册表；`handlers.py` 三处理器 + `_rewrite_query`）。
  - `rag/config.py` 加 `HISTORY_MAX`(12)。
  - `rag/store.py`：`ask()` 重写为**意图分发**（分类→`build_intent`→处理器→`_log_ask` 带 intent/rewritten/turns），新增 `_clean_history` 过滤/裁剪历史；返回体加 `intent`。
  - `rag/telemetry.py`：记录新增三字段；`summarize` 加 `intents` 分布、`by_strategy` 跳过非 KB 检索（向后兼容）。
  - `app.py`：`/api/kb/ask` 透传前端 `history`（非 list 视为 None）。`kb.py` 无需改（`ask` 签名向后兼容，多轮只是新增入参）。
- 前端：
  - `src/KnowledgeQA.jsx` 重写为**多会话侧栏**（`localStorage` 持久化、每轮携带 `history`、答案下显示**意图标签**、保留 Slice 4 的 👍/👎 与公开上传）。
  - `src/style.css` 补 `.qa-layout/.qa-sidebar/.qa-newchat/.qa-chat*/.qa-mobile-bar/.qa-sidebar-toggle/.qa-intent-tag` 及 ≤860px 抽屉响应式，全部复用既有设计令牌，暗色一致，未引新色值。

**测试与验证**：
- 新增 `tests/test_rag_intents.py` **15/15**（Seam S5，纯离线确定性）：三意图分类（含领域词优先压过寒暄、判不准默认知识、带历史追问归知识交改写）、精确型号/编号词偏好 bm25、`needs_rewrite` 三类判据、`build_messages` 顺序/角色/裁剪/空历史、`summarize` 意图分布 + 老记录缺字段归知识 + `by_strategy` 剔除非 KB 检索。
- 回归：`test_rag_unit` 11/11、`test_rag_retrieval` 9/9、`test_rag_rebuild` 6/6、`test_rag_telemetry` 10/10 仍全过（五文件合计 **51/51**）。
- 全栈冒烟（假 faiss/bs4/嵌入/LLM）28 项断言全绿：① 知识单轮——`intent=knowledge`、`answer` 来自 KB-LLM、有 sources、回传 `ask_id`；② 多轮追问——`needs_rewrite` 命中→`_rewrite_query` 恰调用一次→遥测 `rewritten=True/turns=2/intent=knowledge`；③ 闲聊——`intent=smalltalk`、`retrieval=None`、走轻量 LLM 一次；④ 跑题——`intent=offtopic`、返回引导话术、**全程零 LLM 调用**；⑤ 遥测 `intents` 三分类计数正确、`by_strategy` 无非 KB 键；⑥ `app.test_client()` POST `/api/kb/ask` 带 `history` → 200 且响应含 `intent/ask_id`。
- `npm run build` 成功（40 模块，`dist/assets/index-*.js` 222.12 kB、css 50.70 kB），产物已确认含多会话侧栏与意图标签新码。

**至此 Slice 5（意图路由 + 多轮对话，后端+前端+测试）完成，无遗留。** 下一切片：Slice 6 = 原 SPEC 的离线 RAGAS-lite 评测（内置小标准题集 + 手动「重跑评测」才花额度 + 四指标横向对比 + 可选真实问答抽样裁判 + 后台评测卡 + Seam S5 评测向）——**开工前先与老板确认**。

**部署状态**：仍未上阿里云。后端**无状态**，本切片不新增数据文件（会话状态只在访客浏览器 `localStorage`）；遥测多出的 `intent/rewritten/turns` 字段随 `kb_telemetry.json` 落盘，容器 data 卷自动生成，老记录无这些字段也能被 `summarize` 兼容处理。

---

## 十八、第十五轮：RAGAS-lite 离线评测（Slice 6，回到 SPEC 主线）

**目标**：把 SPEC §3.4 的 D5-b + D6 落地——管理员在后台点一下「重跑评测」，用一份内置的**小标准题集**跑一次问答 + 四段裁判 LLM 打分，看**忠实度 / 答案相关性 / 上下文精确率 / 上下文召回率**四个维度的均分，配合每次跑落盘的**当时策略快照**（chunking / retrieval / top_k / chat_model / judge_model …），实现"换策略前 vs 换策略后"的**量化横向对比**，弥补 Slice 4 在线看板只能看真实流量、看不到"标准答案命中率"的短板。

**关键设计取舍**：
- **不引 ragas 重依赖，自写四段裁判提示词**：SPEC §六 D5-b 明确"不引 ragas"，与 Slice 4 定"不引图表库"同源，避开本机装依赖踩坑。四段裁判各管一件事：忠实度看"回答有没有编造上下文以外的事实"、答案相关性看"切不切题"、上下文精确率看"检索到的段落里有多少是真有用"、上下文召回率看"标准答案要点被上下文覆盖多少"。每段独立调用一次 `chat(messages, temperature=0)` 让裁判返回"分数：X.XX"格式，`parse_score` 用两段正则（带中文标签优先 → 兜底抓任意浮点）抠出 0–1 数值并夹到区间。**18 题一轮 = 72 次 LLM 调用**，估算 2–3 元/次，只在手动点按钮时发生。
- **异步后台线程 + 状态轮询**：一次评测要跑 2–4 分钟，绝不能占用 HTTP 请求线程。`start()` 立刻返回 202 + 启动快照，评测在线程里跑，逐题更新模块级 `_STATE` 的 `current / current_qid / running / error / last_record_id`；前端每 3 秒轮 `GET /api/admin/kb/eval/status`。同模块级 `_LOCK` 保证**同一进程只允许一次评测在跑**，避免管理员手滑连点双倍烧额度。
- **对照组从主指标里剔除**：题集里 3 道 control 题（天气 / 写诗 / 世界杯）故意让 KB 答不出，用来**自检评测体系对失败模式是否敏感**。`summarize_items` 把 `overall` 只按 knowledge 题平均，`by_type.control` 单列；前端主卡片显示 knowledge 均分，横向条形对比图用粗条=knowledge / 细条=control 并排，control 分数越低说明裁判越严。
- **每次落盘带策略快照**：`strategy_snapshot()` 抓当前 config 的 chunking / retrieval / top_k / embed_dim / chunk_size / chunk_overlap / rrf_k / chat_model / judge_model / history_max 十项，作为评测记录的一部分写进 `data/kb_eval_results.json`。这样换 `KB_RETRIEVAL` 环境变量重启后跑一次，就能和上次直接对比"bm25 vs hybrid 谁的上下文召回率高"。
- **无 API Key 直接拒绝启动 + 前端按钮置灰**：`has_api_key()` 检环境变量，`start()` 抛 `RuntimeError`，`app.py` 路由翻成 **400**；`GET /api/admin/kb/eval/status` 一直可用（不需要 Key），前端首次挂载拿到 400 就把按钮 disable 并显示原因，符合 US-34。
- **裁判 LLM 挂掉不阻断整轮**：`judge_one` 内部 `try/except` 返回 `None`；`summarize_items._avg` 过滤 None 后取均值，全 None 时返回 None；`counts.skipped` 逐指标统计跳过数——这样单题某指标偶发网络问题不会毁掉整轮 2–3 元的评测。

**本轮做了什么**：
- 后端：
  - 新增 `rag/eval_questions.json`（题集数据，**随代码走版本控制**）：**18 题 = 15 knowledge + 3 control**，覆盖概念定义 / 方法路径 / 具体技术 / 对比概念 / KPI 计算 / 标准合规 / 型号精确词 / 经典理论 / 前沿应用共 9 类，题目和标准答案要点均为老板参与拟定（老板最初问要不要就 6 题、后要求扩到 18 题并补供应链 / 能耗）。
  - 新增 `rag/evaluate.py`：`load_questions`（含字段/类型/id 唯一性校验）→ `parse_score`（带中文标签优先 + 任意浮点兜底 + 越界夹到 [0,1]）→ `JUDGE_PROMPTS` 四段（各自说明评分维度 + 强制"分数：X.XX"结尾）→ `build_judge_messages` 固定四段结构（问题/参考要点/上下文/模型回答）→ `judge_one` 单次调用 → `run_one_question` 串起 `store.ask` + `store.search` 拿上下文 + 4 次裁判 → `summarize_items` 分 knowledge/control 聚合 → `EvalStore` 文件型滚动上限落盘（默认 20，env `KB_EVAL_MAX` 覆盖）→ `start / get_state / reset_state` 三件套管线程与状态。
  - `rag/config.py` 加 `EVAL_MAX_RESULTS`(20)、`EVAL_JUDGE_MODEL`（默认与 CHAT_MODEL 一致，可独立换更便宜的）、`EVAL_METRICS` 元组（前后端共享的四指标顺序，避免拼写漂移）。
  - `app.py` 新增三端点：`POST /api/admin/kb/eval/run`（202 启动 / 409 已在跑 / 400 无 Key）、`GET /api/admin/kb/eval/status`（轮询进度）、`GET /api/admin/kb/eval/results?limit=N`（读历史 + 四指标元数据 + 中文标签）。全部 `@require_admin` 装饰。
  - `.gitignore` 加 `data/kb_eval_results.json`（滚动历史数据，不进仓库）。
- 前端：
  - 新增 `src/AdminEval.jsx`：顶部四指标卡（带 count-up 补间 + 右上角 Δ 徽标显示与上次比较的绝对百分点差，`首次` / `↑x.x pt` / `↓x.x pt`），下方一行策略快照 chip 列出当次配置，主区"knowledge vs control"双条横向对比（粗渐变条=knowledge 均分、细灰条=control 均分），底部折叠表格"逐题分数明细"（control 行淡底 + 前置"对照"角标）。工具栏「▶ 重跑评测」+ 「刷新」，`running` 时按钮文案变"评测中…"并禁用；顶部一条进度条 + `当前 i/18 · 当前题目 qXX`。首次挂载并行拉 `/results` + `/status`，`running=true` 时起 3 秒轮询定时器。
  - `src/main.jsx` 加"评测"标签按钮 + `{activeTab === 'eval' && <AdminEval token={token} />}` 面板挂载。
  - `src/style.css` 补 `.ev-*`（panel / run-btn / progress / delta chip / snapshot chip / compare row / detail table / control-row），全部复用 Slice 4 已建的 `.an-*` 令牌，暗色一致，未引新色值。≤720px 响应式收窄 compare-row 列宽、隐藏 category 列。

**测试与验证**：
- 新增 `tests/test_rag_eval.py` **24/24**（Seam S5，纯离线确定性）：题集加载字段/类型/唯一性 + 文件缺失抛错、`parse_score` 中英文/带分数/越界/垃圾输入 5 类边界、`build_judge_messages` 结构与 metric 特定关键字、`JUDGE_PROMPTS` 与 `METRIC_LABELS` 覆盖四指标、`judge_one` 假 chat 正确解析 + 异常时返回 None、`strategy_snapshot` 十项齐全且与 config 同步、`run_one_question` 假 store + 桩 chat 串起完整链路并回填四分数、无命中场景不崩、`summarize_items` 主指标只算 knowledge / by_type 分开 / 单指标 None 计入 skipped / 空集合不炸、`EvalStore` append + 补 id/ts + 滚动上限 + latest、`has_api_key` 环境驱动、`start` 无 Key / 已 running 两种拒启动、`get_state` 字段齐全。
- 回归：`test_rag_unit` 11/11、`test_rag_retrieval` 9/9、`test_rag_rebuild` 6/6、`test_rag_telemetry` 10/10、`test_rag_intents` 15/15 仍全过（**六文件合计 75/75**）。
- 全栈冒烟 42 项断言全绿（假 faiss/bs4/嵌入/LLM）：① 无 Key 拒启动 + 状态未 running；② 设 Key + 桩 store + 假 chat 调 `start()` → 起真线程 → 30s 内跑完 18 题 → 状态 `current==total` / `finished_at` / `last_record_id` / `last_summary` 都齐；③ 落盘记录结构完整（id/ts/elapsed/strategy_snapshot/counts/overall/by_type/per_question 全在），counts 分布 15+3，overall 四指标都 == 0.83（假 chat 恒定分数），per_question 覆盖 q01–q18 且 q06 intent=offtopic；④ 触发滚动上限验证丢最旧；⑤ HTTP 层——无 token 401 / 缺 Key 400（错误原因回显）/ 带 Key 202 启动 / `/status` 轮询到完成 / `/results` 返回 metrics + 中文 labels + 完整 history + 最近一条含 overall 与 per_question。
- `npm run build` 成功（41 模块，`dist/assets/index-*.js` 229.84 kB、css 53.80 kB），产物已确认含新「评测」标签、`重跑评测` 按钮与相关 CSS 类。

**关于范围与后续**：SPEC §3.4 里的 US-33「对近期 N 条真实问答抽样裁判打分」按老板意愿**顺延为 Slice 7**——Slice 4 的在线看板已经通过 👍/👎 与拒绝率给了真实流量的反馈信号，再叠一层 LLM 打分边际价值不高且要多花额度。SPEC §三"超出范围"里"多轮对话记忆"一项在 Slice 5 已改纳入，本切片无新的越范围动作。

**至此 Slice 6（离线 RAGAS-lite 评测，后端 + 前端 + 测试）完成，无遗留。** 下一切片候选（**开工前先与老板确认**）：
- Slice 7：US-33 真实问答抽样裁判（勾选才跑，默认关）+ 从 `kb_telemetry.json` 挑最近知识问答喂给评测器打分并入看板；
- 或阿里云部署（前 6 个切片累积的 KB RAG 全功能一次性上线）；
- 或其他老板临时想加的需求。

**部署状态**：仍未上阿里云。`rag/eval_questions.json` 是题集**源码**，随代码部署，不进 gitignore；`data/kb_eval_results.json` 是运行时数据，容器 data 卷自动生成，滚动 20 条上限；无 `DASHSCOPE_API_KEY` 时评测端点走 400 分支，前端按钮置灰，与问答主流程无耦合，可正常上线。

---

## 十九、部署上线（前 6 个切片累积的 KB RAG 全功能一次性上阿里云）

**老板指令**：「你先部署进阿里云吧。」

**现状盘点（先只读探查，未动生产）**：`ai-manufacturing-zone` 早已作为 docker compose 项目常驻阿里云 ECS（`/data/projects/ai-manufacturing-zone`，宿主机 8804 端口，跑的是 8-29 的旧镜像、**只含单文件 `kb.py` 版 KB，没有本次重构的 rag/ 包**）。服务器采用 `source/` 打包约定：Dockerfile 里 `COPY source/app.py` 等，构建上下文根放 `Dockerfile + docker-compose.yml + source/`。`.env` 里 `DASHSCOPE_API_KEY` **已配置**（非空），embedding + 问答可直接用。`data/` 是服务器独有挂载卷，内含旧 KB 数据 8 篇文档 / 111 分块（`kb_docs/kb_chunks/kb_index.faiss/kb_meta`，但**无 `kb_raw.json`**——旧版单文件 kb.py 不存原文）。

**动手前先解决的两个关键风险**：

1. **本地 Dockerfile 过时且不匹配服务器约定**——旧 Dockerfile 只 COPY `source/{app.py,kb.py,dist}`，完全没有 `rag/` 包；而重构后的 `app.py` 依赖整条 `import kb → from rag...` 链，直接构建会得到一个 import 即崩的镜像。本地那份我改成了仓库根风格（`COPY app.py kb.py ./ && COPY rag/ ./rag/ && COPY dist/ ./dist/`），并补了 `.dockerignore`（排除 node_modules/.git/.venv/data，加速构建上下文）。但**服务器用的是 source/ 约定**，所以为保持这台机器的既有运维方式，交付包里的 Dockerfile 沿用 `source/` 前缀、只新增一行 `COPY source/rag/ ./rag/`。两套 Dockerfile 各有用途：仓库根那份给 clone/本地用，source/ 那份给这台服务器用。

2. **新代码能否读旧 KB 数据（最要命的一条）**——读 `rag/store.py` 确认 Slice 1 是**纯结构搬迁**（其 docstring 自陈"把旧 kb.py 的 KnowledgeStore 原样搬来"），schema 未变：所有新字段都用 `.get(...)` 带默认值读取，`kb_raw.json` 缺失时 `self.raw={}`（只影响"换分块策略重建"，不影响检索/问答），`kb_meta.next_id` 容错读取，`kb_docs/kb_chunks/kb_index.faiss` 格式与旧数据逐字段一致。**结论：旧 8 篇文档可原样加载，零迁移零丢失。**

**验证链（本地全程跑通后才碰生产）**：
- `npm run build` → dist 41 模块，含 Slice 5/6 前端；
- 本地 `docker build` 仓库根 Dockerfile → 起容器 → 前端 200、`/api/kb/ask`、评测三端点、无 Key 时评测 400、`require_admin` 的 `Authorization: Bearer` 鉴权 401/200 全部符合预期；
- 用 `source/` 约定的交付包**再本地 build 一次**，并把**服务器真实旧数据**拉到本地挂进容器 → `/api/admin/kb/docs` 返回 stats `{total:8, approved:8, chunks:111}`，8 篇标题中文正常、分块数逐篇吻合，`/api/admin/kb/options` 三种检索策略齐活——**向后兼容坐实**。

**生产部署（带回滚保障，一条脚本原子执行）**：
1. 上传 `project.tar.gz`（含 `source/`+新 Dockerfile+compose，**不含 .env、不含 data/**）；
2. 备份：`cp -a source source.bak-<ts>`、`tar czf data.bak-<ts>.tar.gz data`、`docker tag ...:latest ...:rollback-<ts>`（旧镜像留着随时回滚）；
3. `rm -rf source && tar xzf project.tar.gz` 覆盖新代码（含 rag/），`.env` 与 `data/` 均不受影响；
4. `docker compose up -d --build` 重建重启。

**上线后功能复验（真机）**：新容器 Up、镜像 459MB（比旧 392MB 大是因新增 rank_bm25/jieba + rag 包）、回滚镜像在；对外 `http://47.115.223.159:8804/` HTTP 200，未登录访问后台评测端点 401。`/api/kb/ask "什么是数字孪生"` → `intent=knowledge`、`retrieval=hybrid`（**BM25+向量混合检索真跑通**）、返回 3 条资料 + 基于 KB 原文的实质回答；`"你好"` → `intent=smalltalk` 人设话术；无素材问题 → 诚实"知识库暂无"拒答；评测 `status`/`results`/`analytics` 全 200。**评测（Slice 6）未在服务器主动触发**——按 SPEC「手动重跑才花额度」，留给老板在后台点「重跑评测」再产生真实四指标数据。

**遗留 / 已知点**：
- 服务器 `SECRET_KEY` 仍是模板值 `change-me-in-production`、管理员仍 `admin/admin123`——上线前就该改，本次按老板"先部署"未擅改，**建议尽快改**（改了要重启容器，token 会失效需重登）；
- 旧数据无 `kb_raw.json`：这 8 篇只能原样重嵌，不能换分块策略重建；要换策略得重新采集/上传（这是历史数据固有限制，非本次引入）；
- Flask 仍是开发服务器直跑（compose 里 `python app.py`），这台机器沿用已久，非本切片范畴，若要更稳可换 gunicorn。

**至此：6 个切片的 KB RAG 全功能（重构 + 混合检索 + 逐文档分块重建 + 问答看板 + 意图路由多轮对话 + 离线评测）已一次性上线阿里云，旧库数据完整保留、混合检索与问答在生产环境验证通过。**

---

## 二十、两件安全小事 + PRD 生成器 MVP（方向由老板微信对话决定）

**先做的两件安全小事**（上线遗留项）：把服务器 `.env` 的 `SECRET_KEY` 换成随机 64 位十六进制、`ADMIN_PASSWORD` 换成强随机口令；只改这两行、保住 `DASHSCOPE_API_KEY`、`.env` 先备份（`.env.bak-<ts>`）、`docker compose up -d` 重建生效。验证：旧密码登录 401、新密码 200、改 secret 后旧 token 一并失效（401）、后台接口正常。

**方向调整**：本来按原 SPEC 下一步该做 Slice 7（US-33 真实问答抽样裁判）。但老板在微信里把真实目的讲清楚了——不是把 RAG 做精，而是**"用 AI 帮智能制造行业客户做智能体平台转型、促成合作"**，他最兴奋的功能是"输入公司+业务介绍 → AI 直接产出面向该客户的《AI 智能体平台功能需求 PRD》"，且要**引导模式**（客户不懂先给草稿+澄清问题）和**规范化模式**（把客户原始需求整理成规范 PRD）两种。据此我停下来先跟老板方向对齐（写了 `PRD_GENERATOR_SPEC.md`），确认后再动手，**没有**照原计划去做低价值的 Slice 7。

**这个切片做了什么（PRD 生成器 MVP）**：
- 后端 `rag/prd.py`：`clean_input`（校验+截断）、`build_system_prompt(mode)`（角色=智能制造数字化转型顾问+AI 智能体平台产品专家，强约束 11 段 PRD 骨架，按模式切换引导/规范化指令）、`format_kb_context`（知识库命中拼"行业参考"）、`build_prd_messages`、`generate_prd`（先 `store.search` 做行业接地→组提示词→`chat`）。
- `rag/config.py` 新增 PRD_* 常量（模型/top_k/温度/各字段长度上限）。
- `app.py` 新增 `POST /api/admin/prd/generate`：`@require_admin` + 限流 6 次/分 + 无 Key 400 + 校验失败 400 + LLM 失败 502。
- 前端 `src/AdminPRD.jsx`：后台新增"PRD 生成"页签。表单（公司/行业/业务/模式二选一/规范化时贴原始需求）+ loading（LLM 约 15–40s）+ 结果区。**自带一个轻量 Markdown 渲染器**（标题/粗体/行内码/有序无序列表/表格/分隔线），不引第三方库；支持复制全文、下载 `.md`；顶部显示是否接地、命中数、模式、模型、参考来源。
- `style.css` 加 `.prd-*` 一套样式，沿用现有暗色主题变量。

**设计取舍**：
- **复用而非新起**：直接用现有 `rag.llm.chat` + `KnowledgeStore.search`，零新依赖，与已上线的 RAG 栈同构。
- **行业接地但可降级**：生成前检索知识库注入"行业参考与案例"，呼应老板"know-how 专家"诉求；空库/检索异常自动降级为不接地，不阻断生成（现在知识库还比较空，等老板补进行业报告/论文后产出会更专业）。
- **两模式一套骨架**：引导/规范化共用 11 段 PRD 模板，只在系统提示词里切换指令 + 规范化模式多传"客户原始需求"，维护面小。
- **放后台不上公开**：MVP 先做成团队内部售前工具（复用管理员鉴权、控额度）；公开获客落地页（免登录+限次+留资）留作后续增强。
- **输出必须人工复核**：提示词与文档信息里都写明"AI 生成需人工复核"，不假装 PRD 可直接交付。

**验证**：单测 `tests/test_prd.py` 43/43 绿；全量回归 7 文件 118 项全绿；`npm run build` 42 模块通过；端点冒烟 `smoke_prd.py` 13/13 绿（假 chat+假 search，覆盖 401/200/grounded/normalize 校验/无 Key 400/chat 异常 502）。

**本切片未上生产**（等老板在本地看过方向对不对再决定何时上线，与既定"先本地验证再上线"一致）。

**下一切片候选（开工前先对齐）**：
- 把 PRD 生成器**上阿里云**（本切片代码 + 新端点 + 前端）；
- **界面整体美化**（老板嫌"看起来简单"，用 beautiful-pages 规范重做门户/知识库/问答/后台观感）；
- **案例库**（老板提到"包括我们的一些案例"，做可维护的案例展示，并喂给 PRD 生成器当参考）；
- 原 SPEC 的 Slice 7（抽样裁判）——优先级已低于上面几项。

---

## 二十一、PRD 生成器上线阿里云（含一处读超时踩坑修复）

**上线动作**：老板点头"先上线 PRD 生成器"后，按既定 `source/` 打包约定部署——本地重建前端 dist（42 模块，确认已含 PRD 页签与 `.prd-*` 样式）→ 组 `project.tar.gz`（`Dockerfile`(source 风格)+`docker-compose.yml`+`source/`(app.py/kb.py/rag 含 prd.py/dist)，**不含** `.env`/`data`）→ paramiko 上传（md5 双端一致 `d9b9b75…`）→ 备份（`cp -a source source.bak-<ts>`、`tar czf data.bak-<ts>.tar.gz data`、`docker tag …:rollback-<ts>`）→ `rm -rf source; tar xzf` 解包 → `docker compose up -d --build` 重建镜像并滚动重启。`.env` 里上一切片改好的 `SECRET_KEY`/`ADMIN_PASSWORD`/`DASHSCOPE_API_KEY` 原样保留、未被动到。

**踩到一个坑（真机验证才发现，单测/冒烟都测不出）**：接口连通性、鉴权、KB 8 篇向后兼容全绿，但"用真实 Key 跑一次真实生成"时连续两次 HTTP 500，报 `dashscope… Read timed out (read timeout=60)`。定位：`rag/embedding._dashscope` 默认读超时 60s，而 KB 问答返回短、60s 够用；PRD 要一次生成整份 11 段中文长文（实测约 6900 字），非流式要等全文吐完才返回，60s 顶不住。**这是运行时/网络侧才暴露的问题**，本地用假 chat 的单测和冒烟自然全绿——记一笔教训：涉及真实 LLM 长输出的功能，上线前最好真机点一次。

**修法（小、可配、向后兼容）**：`chat()` 增加 `timeout` 参数并透传给 `_dashscope`；`config` 新增 `PRD_TIMEOUT`（env `KB_PRD_TIMEOUT` 可覆盖，默认 120）；`generate_prd` 用 `PRD_TIMEOUT` 调 chat。只影响 PRD 长生成，KB 问答仍走 60s 默认不动。补 1 条"超时透传"单测（PRD 单测 44 全绿，全量回归 99 项绿）。三文件 targeted 同步到服务器 `source/rag/` 后重建镜像、重启，再跑真实生成即通过。

**真机验收（阿里云 47.115.223.159:8804）**：
- 未带 token 调 `/api/admin/prd/generate` → 401；登录 → 32 位 token；
- `/api/admin/kb/docs` → 旧 8 篇照常列出（新代码向后兼容再次确认）；
- **真实接地生成（引导模式）**：`grounded=True`、`hits=4`、`model=qwen-plus`、正文 6900 字、恰好 11 个 `##` 段（文档信息→客户背景→转型目标→目标用户→智能体功能清单→平台功能→非功能→私有化技术架构建议→分三期≤20 周路线图→行业参考与案例→待客户确认问题清单），并带"AI 生成需人工复核"字样。
- 回滚网兜底：本轮回滚镜像 `ai-manufacturing-zone-app:rollback-20260831-<ts>` + `source.bak-*` + `data.bak-*` 均在。

**下一步**：PRD 生成器已在生产可用。接下来按老板优先级推进**界面整体美化**（老板嫌"看起来简单"），并把老板提到的一些案例沉淀进知识库当 PRD 生成的行业参考素材。开工前再跟老板对齐范围。

---

## 二十二、外观配置加「恢复默认」按钮（老板把外观调坏了，一键救急）

**起因**：老板在后台"外观配置"里把画布背景色调成了 `#c8c8df`（浅色），但站点是暗色文字主题，结果整站文字糊成一片、等于"改坏了"。需要给后台加一个"恢复默认"入口，避免以后再改坏没法自救。

**做法（小、单一真源、非破坏）**：
- 后端把内置默认抽成 `DEFAULT_CONFIG`（`{title:智能制造专区, accent:#3b82f6, canvas:#0b0b0f}`），`get_config()` 兜底改用它——以后默认值只有一处。
- 新增 `POST /api/admin/config/reset`（`@require_admin`）：把默认值写回 `config.json` 并返回（是**覆盖写**不是删文件，保持文件合法、无破坏性删除）。
- 前端 `AdminPanel` 加 `resetConfig`：二次确认 → 调 reset → 用返回值刷新表单 → `onChange()` 触发重取 `/api/config` 让 `useEffect` 把 CSS 变量重新落回默认 → 在"外观配置"页签"保存"旁加了 `.btn-ghost`「恢复默认」按钮 + 一句救急提示文案。

**验证**：本地冒烟 `smoke_config_reset.py` 7/7 绿（未授权 401、登录、先写坏配置、reset 返回内置默认、`GET /api/config` 随之变默认）；`npm run build` 42 模块通过。上线走 targeted 同步（`app.py` + 重建的 `dist/`）→ 备份回滚镜像 `rollback-cfgreset-*` → `docker compose up -d --build`。真机验收：未带 token 调 reset 401；reset 前线上 config 是 `canvas:#c8c8df`（就是被调坏的那个），reset 后回到 `#0b0b0f`，**生产外观当场修好**。

**留痕**：老板改坏前的值是 `{title:智能制造专区, accent:#3b82f6, canvas:#c8c8df}`，仅背景色一项偏离默认，已记录，若确有需要可再单独调。

---

## 二十三、日夜间主题切换（默认浅色）+ 外观配置输入校验

**需求**：老板要"右上角一个太阳/月亮按钮，一键切换白天/夜晚"。太阳=整站白底，月亮=当前暗色页；默认进**浅色**（老板拍板"以后主打对外展示，白天档更耐看"）。顺带把上次「外观调坏」的隐患一并堵掉——外观表单加输入校验。

**技术选型（一次定生死，别走岔）**：
- **不用 `prefers-color-scheme`**，直接 CSS 自定义属性 + `<html data-theme="dark">` 属性选择器覆盖。理由：要显式按钮切换，且要**覆盖管理员自定义的 `canvas` 配置**——媒体查询做不到；用 `data-theme` 属性最直观，SSR 也能同套机制。
- **默认浅色**意味着要**重设计一整套浅色调色板**，不能沿用暗色色板倒一倒。走 `beautiful-pages` skill 的"风格 A 明亮白底"规范：`--canvas:#ffffff`、`--surface-1:#f7f7f8`、`--surface-2:#f1f1f3`、`--surface-3:#e7e7ea`、`--ink:#18181b`、`--body:#3f3f46`、`--muted:#71717a`、`--hairline:rgba(0,0,0,.09)`、`--accent:#2563eb`。暗色档保留原来那套值不动，只是搬到 `:root[data-theme="dark"]`。
- **新增四个语义令牌**方便后续复用：`--nav-bg`（导航条半透明背景）、`--panel-fill`（浅/中面板底 3%）、`--panel-fill-2`（hover 面板底 6%）、`--overlay`（模态遮罩）。之前散落在 CSS 里的 `rgba(255,255,255,0.0X)` 白透明"玻璃面板"在浅色下等于**隐形**，全都要 token 化。
- **管理员 `canvas` 配置只在暗色档生效**——浅色档坚持 CSS 默认 `#ffffff`。这样以后老板即便又给 `canvas` 填了个 `#c8c8df`，也只影响他自己后台预览的暗色页，白天档不会糊。`accent` 两档都覆盖。

**改了哪些文件**（一次 commit `2afbf26`）：
- `src/style.css`：把原来一个 `:root` 拆成 `:root`（浅色默认）+ `:root[data-theme="dark"]`（暗色覆盖）；`body` 加 `transition: background-color .25s ease, color .25s ease` 让切换有过渡不硬跳；`.navbar` 背景从写死的 `rgba(11,11,15,.85)` → `var(--nav-bg)`；`.qa-answer-content code` 内联码背景 `rgba(255,255,255,.08)` → `var(--panel-fill-2)`；PRD 表格斑马行 `rgba(255,255,255,.02)` → `var(--panel-fill)`。
- `src/architecture.css`：`.arch-section` 顶部渐变原本写死暗色（`#06080d→#0b0f1a→#0d1117`），改成"浅色渐变 `#fff→#fafafa→#f4f4f5` 做默认 + `:root[data-theme=dark] .arch-section` 覆盖回原暗色"；侧边栏 `#12121a` → `var(--surface-1)`；遮罩 `rgba(0,0,0,.5)` → `var(--overlay)`；一共 15 处 `rgba(255,255,255,0.02~0.12)` 白透明面板/边框（`.arch-org-leaf`、`.arch-pos-tag`、`.arch-dept-header`、`.arch-scenario-box`、`.arch-coord-item`、`.arch-tech-item`（含 hover）、`.arch-dataflow-step`、`.arch-sidebar-close`（含 hover）、`.arch-cap-tag`、`.arch-sidebar-related`、`.arch-sidebar-related-item`（含 hover）、`.arch-metric`、`.arch-flow-step`）全部映射到 `--panel-fill` / `--panel-fill-2` / `--hairline` / `--hairline-strong`；`grep` 复核确认无残留白透明或写死的暗色 hex。
- `src/main.jsx`：
  1. 模块顶层加同步初始化——`localStorage.getItem('mz_theme')` 立刻写到 `document.documentElement` 的 `data-theme` 属性，**在 React 挂载前**执行，避免首帧闪一下"错的主题"（FOUC）。
  2. `App` 组件加 `theme` state（初值从 `<html data-theme>` 读，兜底 `'light'`）；一个 `useEffect` 每次 `theme` 变化时同步属性 + 写 localStorage；`toggleTheme` 切换。
  3. 图标 `ICONS.sun` / `ICONS.moon` 加进现有 SVG 集，导航右侧新增 `.btn.btn-ghost.btn-sm.theme-toggle` 按钮，`aria-label` + `title` 都写了。当前是暗色就显示太阳（点击切浅色），当前是浅色就显示月亮（点击切暗色）。
  4. 原本 `useEffect` 里 `config.canvas` 无脑写 CSS 变量的逻辑，改成**只在 `theme === 'dark'` 时**才 `setProperty('--canvas', config.canvas)`；浅色时反过来 `removeProperty('--canvas')` 让 CSS 默认 `#ffffff` 生效。`config.accent` 两档都覆盖不变。effect 依赖数组加进 `theme`，切档时会自动重跑清理。
  5. `saveConfig`（后台"外观配置"保存）前加校验：`title` 非空；`accent` / `canvas` 若非空必须是 `#rgb` 或 `#rrggbb`，正则 `^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$`。不合规 `alert` 中文提示 + 阻断请求，防止再出现"提交 `#c8c8df` 洗白整站"。

**踩过的坑**：
- **白色透明在浅色主题下"看不见"**——不是 bug，是设计。原来暗色下 `rgba(255,255,255,0.04)` 是"微微亮一点的浮层"，翻到浅色主题下变成"几乎透明的白"叠在白底上，什么都看不见。**必须 token 化**：把 0.02~0.05 归到 `--panel-fill`（浅色档=`rgba(0,0,0,.035)`），0.06~0.12 归到 `--panel-fill-2`（浅色档=`rgba(0,0,0,.06)`）。这样两套主题下"轻微浮层 / 强浮层"两级都有可视对比。
- **侧边栏关闭按钮 hover 视觉降级**：原本 base 0.06 → hover 0.12，两级都在 `--panel-fill-2` 会没差别。把 hover 改到 `--hairline-strong`（浅色档=`rgba(0,0,0,.16)`、暗色档=`rgba(255,255,255,.14)`）保留对比。
- **默认浅色 = 要重设计浅色调色板**，不是"把暗色倒过来"。文字色不能纯 `#000`（对比过头、显廉价），面板色不能用纯白叠纯白，hairline 用 `rgba(0,0,0,.09)` 而不是纯灰 `#ddd`——参考 beautiful-pages 里 Linear/Vercel/Notion 的做法。

**构建 & 上线**：`npm run build` 42 模块过，产出 `dist/assets/index-ZAZcovoc.css`（58.87 kB / gzip 10.78 kB）、`index-HxQmxCcY.js`（238.76 kB / gzip 82.64 kB）。**只前端改动**（后端 `app.py` 未动），走 targeted 同步：`dist_theme.tgz`（91KB）sftp 上传 `/tmp` → 服务器 `cp -a source/dist source/dist.bak-<ts>`（324K）→ `rm -rf source/dist; tar xzf /tmp/dist_theme.tgz -C source` → `docker compose up -d --build`。镜像重建，容器 `Recreate → Started`，`Up 3 seconds`；首页 HTTP 200 size=652。

**真机验收**：
- 首页引用的资源哈希 `index-ZAZcovoc.css` / `index-HxQmxCcY.js` 与本地构建一致（部署没漏）；
- `curl` 拉线上 CSS grep 到 `data-theme=dark]{--canvas:#0b0b0f;--surface-1:#121218;…}` **和** `data-theme=dark] .arch-section{background:linear-gradient(180deg,#06080d,#0b0f1a 40%,#0d1117)}` 双主题块都在；
- `curl` 拉线上 JS grep 到 `mz_theme` / `theme-toggle` / `data-theme` 三处关键字都在（切换逻辑打包成功）；
- 用户在浏览器目视确认"浅深色切换正常"。

**外观输入校验（同一 commit 顺手做了）**：`AdminPanel.saveConfig` 里 `title` 空 → alert "站点标题不能为空"；`accent` / `canvas` 非 `#rgb` / `#rrggbb` 格式 → alert 明确提示样例值。校验放在 `apiPost` 之前，一次不合规直接阻断，不会把脏值写到 `/data/config.json`。

**下一切片候选（回到对齐过的 Slice B 落位）**：既然老板拍板"案例=已部署的项目、复用现有项目矩阵不新建案例库"，接下来给 8 张能力作品集卡片拟文案（AI CAD Studio、铸形、智工AI、snail-ai、智枢/astron、idc-visual、pascal-editor、databuff-apm），逐条给用户过；过完通过 `POST /api/admin/projects` 落 `projects.json`，前端 `AGENTS_FALLBACK` 自动被覆盖。

## 二十四、WeKnora 轻量集成 W1：LITE sidecar 部署上线 + 论文冒烟（官方镜像不可用 → 源码自建 126MB 镜像）

按 `WEKNORA_INTEGRATION_SPEC.md` 开工切片 W1：把 WeKnora LITE 以 sidecar 形式部署到阿里云 ECS（47.115.223.159），与门户 8804 同机不同端口（**8805 仅绑 127.0.0.1，纯内网**，外部摸不到）。W1 的验收口径：建库、上传一篇真实论文 PDF、解析完成、knowledge-search 能召回。另外老板特意要求 W2 开始前先拿**论文/行业报告**这类高质量文档压一压解析器——所以冒烟文档选了 arXiv 数字孪生×智能制造论文（2311.05748，5MB）。

**先踩一跤：官方 v0.7.2 镜像根本不是 LITE-ready**。拉起 `wechatopenai/weknora-app:v0.7.2` 后一切看似正常（健康检查绿），但一注册就炸：`table tenants has no column named api_principal_config`、`no such table: system_settings`、`Failed to create FTS5 table: no such module: fts5`。根因：标准镜像的 sqlite 迁移只到 v2，二进制却要求 v12 的表结构；且编译没带 `sqlite_fts5` tag，FTS5 全文索引直接没有。标准版靠 redis+postgres 兜着，LITE 玩不转。结论：**按 SPEC 的 fallback 路线走源码自建**。

**自建镜像四连坑**（Dockerfile 折了四轮才绿，每轮都有真实报错兜底）：

1. **router.go 隐式依赖 `docs/` 包**——裁剪打包时把 docs/ 排除了，`go build` 直接 `no required module provides package github.com/Tencent/WeKnora/docs`。docs 目录必须进构建上下文。
2. **sqlite-vec 的 CGO 头文件**——`fatal error: sqlite3.h: No such file or directory`。builder 阶段必须 `apt-get install libsqlite3-dev`（对照上游 docker/Dockerfile.app 确认）。
3. **gojieba 启动 panic**——二进制编译过了，运行时 `panic: Dictionary file does not exist: /go/pkg/mod/github.com/yanyiwu/gojieba@v1.4.7/deps/cppjieba/dict/jieba.dict.utf8`。gojieba 按**编译期模块缓存绝对路径**找 cppjieba 词典，final stage 必须 `COPY --from=builder /go/pkg/mod/github.com/yanyiwu/ /go/pkg/mod/github.com/yanyiwu/`（照抄上游的做法）。
4. **runtime 缺动态库**——CGO 二进制动态链接 libsqlite3，`bookworm-slim` 没有。runtime 装 `libsqlite3-0`，顺手补 `tzdata`（Asia/Shanghai 时区）和 `curl`（compose 健康检查要用）。

最终镜像 **126MB**，构建 3 分钟（go mod download 单独成缓存层，重构建只要 12 秒）。compose 把 app 换成 `weknora-lite:local`，清掉被标准版写坏的 sqlite 库重来，起来后日志全是 LITE 特征：`SQLite retriever engine repository with sqlite-vec`、`Populating contentless FTS5 table with bigrams`、`Lite mode, no Redis`，8805 健康检查 200。

**再来一跤：模型创建的 source 字段是个坑**。bootstrap 脚本按直觉给模型填 `source:"aliyun"`（枚举里明明有 `ModelSourceAliyun`），结果上传论文后 `parse_status` 永远卡 `processing`——docreader 4.5 秒就解析完了（8 页、41366 字符、10 张内嵌图都导出了），但 app 侧 chunk→embedding 管线毫无动静。翻源码 `model.go` 的 `CreateModel`：**只有 `source == "remote"` 才置 active，其余一切值都进 ollama 本地下载分支**，embedding 模型状态停在 downloading，管线永远等不到可用模型。改成 `source:"remote"`（DashScope compatible-mode + interface_type openai 是标准路径）立刻通。

**W1 冒烟全链路通过**，干净库上 16 秒跑完：注册 201 → 登录（tenant=1）→ 建 text-embedding-v4（1024 维）+ qwen-plus 双模型 → 建 KB「智能制造专区」→ 上传论文 → **parse completed** → knowledge-search 200 命中 10 条（top3 相关度 0.504/0.500/0.498，内容确实是论文里数字孪生/智能制造段落）。97 个 chunk 全部向量化入库（SQLite+FTS5+sqlite-vec 三件套齐活），处理完 `enable_status` 自动转 enabled。

**资源占用实测**（对 SPEC 的"百级文档够用"判断是个好印证）：app 容器 224MiB + docreader 180MiB ≈ 400MB 总占用；DB 12MB（含 97 chunks + 向量）；切分质量采样看，标题/作者块完整、正文引用规范、参考文献 DOI 保留，平均 ~425 字/chunk，Simple parser 对学术论文的抽取没有乱码断词。**对论文/行业报告类文档，解析质量可以支撑 W2**。

**过程中的工程坑**（跨任务通用，记一笔）：paramiko `nohup` 后台火启存在竞争——子进程可能在重定向前被会话回收干掉（`setsid` 都救不了），`pgrep/pkill -f` 还会自匹配自己的 `bash -lc` 包装。最终稳定模式：**前台流式 channel**（`open_session` + `recv` 循环 + keepalive(30)），长任务全程握着 channel 流式收输出，彻底告别后台任务黑箱。

**下一步（W2）**：rag/engine.py 网关对接 8805（`WEKNORA_ENABLED` 回退开关）+ AdminKB 管理界面重做 + 既有 8 文档迁移。W1 的冒烟结论已满足老板"先验证论文解析质量"的前置条件。

## 二十五、批次1质量测试：7篇CNKI论文切分+问答实测（切分PASS / 问答PASS / 挖出改写随机性根因）

用户按清单下载了 7 篇核心论文（Edge 下载目录 → 重命名 `01~07_短标题_作者年份.pdf` 共 22.1MB），要求先测这批的切分和问答再继续。测试链路全部走 LITE sidecar API（`POST /knowledge-bases/{kb}/knowledge/file` 上传 → 轮询 `parse_status` → sqlite 直查 `chunks` 表统计 → `POST /sessions` + `POST /knowledge-chat/{sid}` SSE 问答）。

**切分结果（PASS）**：7 篇全部 completed，共 842 块，块均长 475~495 字（上限 512），无碎块无超长块；期刊头/DOI/作者/摘要保留完整，图片以 `resource://` 内嵌。02（王柏村英文综述，Engineering 期刊）400 块解析也正常。**解析器不用调参。**

**问答结果（6 题：3 一次过 + 1 负控正确拒答 + 2 排查后过）**：Q3 数字化转型（上海电气案例全命中）、Q4 知识图谱（3大类15小类）、Q5 智能制造特征（HCPS/四维目标）首测直接满分，答案全部带 `<kb doc chunk_id>` 溯源、零编造；Q6 MES/APS 库内无内容，正确拒答还给了 ISA-95 建议。Q1 五维模型、Q2 工业5.0 首测拒答——但库里明明有原文。

**根因排查（本切片最大收获）**：
- 直查 `/knowledge-search`（不走改写）精准命中 01×6（含「笔者团队前期提出了数字孪生五维模型，包括物理实体、虚拟模型、服务、孪生数据以及它们之间的连接交互」原文）→ 检索层没问题；
- 拉问答 SSE 流看：首测 Q1 的 14 条引用 **100% 来自 W1 的英文冒烟论文**（向量分 0.35~0.44）；
- 什么都不改只重新提问 → Q1/Q2 立即满分。
- 结论：**query_understand（LLM 问题改写）有随机性**，首测偶发把中文问题改写成英文，跨语言向量检索时英文块占优挤掉中文语料。英文冒烟论文是最大噪声源，已删（正确路由是 `DELETE /api/v1/knowledge/{id}`，`/knowledge-bases/{kb}/knowledge/{id}` 是 404）。

**顺手记录的坑**：knowledge-chat SSE 帧是 `event:message` + `data:{json}`，增量在 `response_type:"answer"` 帧的 `content` 字段，`references` 帧的 `knowledge_references` 数组挂在帧顶层（不在 data 里）——按空行分块再 `startswith("data:")` 会漏掉所有帧（块首是 event: 行），必须逐行解析。直查检索是关键词评分（~0.016 量级）、问答管线是向量评分（0.3+ 量级），做评测时两套分不能混比。SFTP 上传中文文件名到 Linux 落盘显示乱码但内容无损，WeKnora 侧 filename 取的是 multipart 里的 UTF-8 名，正常。

**产出**：`批次1切分与问答质量测试报告.md`（项目根）、`batch1_results.json` / `batch1_retest.json`（本地 workspace）。服务器遗留：`uploads/batch1/*.pdf`（保留供重解析）、`batch1_sse_q1~6.txt`、`retest_q1~2.txt`、`.batch1_qa_done` 标记。知识库当前 = 干净的 7 篇批次1语料。

**对 W2 的输入**：① 语料纪律——只进中文目标语料；② engine.py 检索兜底用 `/knowledge-search` 直查（行为确定），问答改写只当增强；③ 高频预置问题可固定检索词绕过改写随机性；④ 文档级 `summary_status=failed` 不影响检索问答，暂不修。


## 二十六、W2 管理侧对接：WeKnora 成为知识库引擎（门户改走转发端点）

按 SPEC 切片 W2 完成「管理侧对接」：后台知识库管理页从操作自建 rag 改为操作 WeKnora，旧链路原样保留作回滚网。

**做了什么**：
- `rag/engine.py`（约 240 行，收口层）：search / chat(SSE) / upload_file / upload_url / list_docs / doc_detail / doc_chunks / delete_doc / reparse / health，全部 WeKnora 调用只准走它；`WEKNORA_ENABLED=false` 一键回退。
- `app.py` 新增转发端点（全部带 @require_admin）：`/api/admin/kb/weknora/{status,docs,upload,docs/<id>,docs/<id> DELETE,search}`；`/api/admin/kb/crawl` 引擎开启时分流到 WeKnora（异步解析）；`/api/admin/kb/options` 增加 `engine` 字段供前端判模式。
- `AdminKB.jsx` 双模式：引擎开=横幅(含 8805 控制台外链)+文件上传+URL采集(无分块下拉)+检索调试(直查 knowledge-search)+文档表(解析状态轮询 5s/分块预览/删除)；引擎关=原界面原样。
- compose：portal 加入外部网络 `weknora-lite_wknet`，env 注入 `WEKNORA_BASE_URL=http://weknora-app:8080` + `WEKNORA_API_KEY` + `WEKNORA_KB_ID`，容器内网直连（8805 不对公网开放）。
- 服务端专用 API Key（scoped）：`POST /api/v1/tenants/1/api-keys`，capabilities=[retrieve,chat,ingest,manage_kbs] 且限定 KB 白名单，最小权限。

**验收（真机全过）**：admin 登录→options.engine.enabled=true→status healthy→7 篇批次1论文在列→上传冒烟 txt（5 秒解析完）→分块预览 2 块→直查检索命中冒烟文档(0.0164)→删除干净→旧 /api/kb/ask 不受影响（W3 才切）→回退开关演练 OFF/ON 都正常。旧 rag 数据已复制归档到 `data/rag_archive_20260905_w2/`（原件暂留，W3 切问答后再清）。

**坑与教训**：
1. WeKnora API Key 请求头是 `X-API-Key: sk-...`，**不是** `Authorization: Bearer`（Bearer 走 JWT，两套并行）——拿 Bearer 测 API key 一直 401，翻中间件源码才发现。
2. 创建 key 的响应里 `api_key` 字段是入库的密文形态（enc:v1:...），真正能用的是 `token` 字段（sk- 开头），且**只在创建响应里出现一次**，列表接口不回显——存错字段只能删了重建。
3. scoped key 报错信息很误导：不传 capabilities 报 "capabilities are required for scoped API keys"，其实传 `full_access: true` 可以免 capabilities；我们选了 scoped + KB 白名单更安全。
4. 前端 `fetchOptions` 的 setOptions 是白名单式合并，新加的 `engine` 字段必须显式透传，否则界面永远停在旧模式（上线前自查发现，重打了 dist）。
5. 文档列表字段是 `file_name`（不是 filename），检索命中是 `knowledge_filename`/`knowledge_title`；分块列表走 `GET /chunks/{knowledge_id}`（SPEC 里写的 /knowledge/{id}/spans 是解析阶段视图，也在，但 chunks 更适合预览）。

**改动文件**：`rag/engine.py`(新)、`app.py`、`src/AdminKB.jsx`、`src/DocPreview.jsx`(状态映射扩展)、`src/style.css`(wk-banner/wk-hit)、`docker-compose.yml`；服务器 `backups/w2/` 留了全量备份（app.py/compose/dist）。

**下一步（W3）**：`/api/kb/ask` 的 knowledge 分支转发 `engine.chat()`（多轮 session_id 由门户保管），前台问答 UI 不变，意图路由回归；W4 切 PRD/评测 + 30 题基线 + 删旧代码。

## 二十七、W3 问答切换：前台知识问答正式走 WeKnora

按 SPEC 切片 W3 完成「问答切换」：`/api/kb/ask` 的 knowledge 意图转发 WeKnora 会话问答，问候/闲聊/超范围仍走原意图链路，前台问答 UI 一行没动。

**做了什么**：
- `app.py`：ask 入口先做意图分类，knowledge 且引擎开启 → `_ask_weknora()`；会话映射（conversation_id → WeKnora session_id）只存内存（TTL 1 小时、上限 300 条、超量淘汰最旧），重启丢失 = 自动新建会话无感；映射的会话失效时自动丢弃重建重试一次。
- `rag/store.py`：加 `log_weknora_ask()` 公开遥测入口（retrieval 固定标 `weknora`，top_score 不记——与旧链路分数不同尺度不可比），看板 by_strategy 能分辨两种引擎的量。
- `rag/engine.py`：`chat()` 修 SSE 答案提取（见坑 1）。
- `src/KnowledgeQA.jsx`：请求体带 `conversation_id`（前台本来就有会话 id，顺手带上）；UI 零改动。
- 回答清洗：WeKnora 回答内嵌 `<kb doc=".." chunk_id=".."/>` 内联引用标记，来源列表已单独展示，正则清掉。

**验收（真机 8 项全过）**：知识问答 6.8s 带 14 条来源；**多轮追问成功**——先问五维模型组成、再问"它是谁提出的？"，正确答出陶飞/北航团队/2019（WeKnora 会话上下文生效）；闲聊→smalltalk 原链路；超范围→offtopic 原链路；知识库没有的 MES/APS 题 → WeKnora 给出"未提供相关内容+邻近主题"的得体回答；看板 by_strategy 出现 weknora 条目；回退演练关引擎→同一问题走旧 hybrid 链路→恢复开启→恢复 WeKnora。

**坑与教训**：
1. **SSE 答案增量的位置**：帧顶层字段是 `response_type`（不是 type），答案增量在 response_type=="answer" 帧的【顶层 content】——而 `frame["data"]` 里只有 event_id。第一次部署按"data 里的 content"取，来源引用全对但答案是空串。教训：拿不准协议形状时，第一件事是 dump 一条真实 SSE 原始流看帧结构（服务器上批次1留下的 batch1_sse_q1.txt 直接救场），别靠记忆猜。
2. WeKnora 的回答会内嵌 `<kb doc chunk_id/>` 引用标记，markdown 渲染会吞掉但不干净，门户侧统一正则清除。
3. 看板聚合的键是 `by_strategy`（不是 by_retrieval）。
4. WeKnora 对知识库没有的问题不是硬拒绝，而是"声明未提供+给邻近主题"——遥测里 refused 只在引用数为 0 时记，所以拒绝率口径和旧链路（检索 0 命中才拒）天然一致。

**改动文件**：`app.py`、`rag/store.py`、`rag/engine.py`、`src/KnowledgeQA.jsx`；服务器 backups/w2/dist_pre_w3 留了切换前 dist。

**下一步（W4，收尾切片）**：PRD 生成器/离线评测的检索底座切到 engine.search（30 题基线对比迁移前后指标），旧 rag 代码标 @deprecated，按 SPEC 回滚表完成收尾。


## 二十八、Slice W4 · 评测/PRD 切换 + 收尾（2026-09-07，WeKnora 集成收官）

按 SPEC 切片 W4 完成最后一层切换：PRD 接地检索与离线评测的被测对象都切到 WeKnora，跑 30 题基线对比新旧链路，旧 rag 代码正式标 @deprecated，旧检索数据物理清理归档。WeKnora LITE 集成四个切片（W1 基建→W2 管理→W3 问答→W4 评测/PRD）全部完成。

**做了什么**：
- `rag/engine.py`：新增 `search_context(query, top_k)`——把 WeKnora 直查结果归一成旧链路 hit 形状 {doc:{title,url}, text, score}，PRD 和评测共用这一个映射函数，调用方代码零改动换底座。
- `rag/prd.py`：`generate_prd` 接地检索分流——引擎开启走 `engine.search_context`（挂了降级不接地，不挡生成），关闭回退 `store.search`；提示词/流程一行没动。
- `rag/evaluate.py`：`run_one_question` 分流——引擎开启且判为 knowledge 意图时，回答走 `engine.chat()`（**每题独立会话**，防跨题串上下文）、上下文走 `engine.search_context()`，并按线上口径记遥测；问候/跑题等非知识意图仍走旧意图人设（与 /api/kb/ask 路由行为一致，对照组题才有意义）。四段裁判提示词与打分逻辑零改动；`strategy_snapshot` 新增 engine 字段（weknora-lite / legacy），前端快照条动态渲染自动显示。
- `rag/eval_questions.json`：题集 18 → **30 题**（q19-q30 新增数字孪生专题，对齐新语料）；27 知识 + 3 对照。12 道新题上传后先跑覆盖预检：knowledge-search 全部命中真实论文（陶飞 2021 / 吴雁 2021 / 李浩 2021），无空转题。
- @deprecated 标记：14 个旧 rag 模块头部插入 DEPRECATED(W4 2026-09) 注释；`store.py` 用「部分退役」措辞——links 管理、遥测、意图人设还在用，只有文档管理/检索/问答退役。
- 旧数据物理清理：`kb_docs.json / kb_chunks.json / kb_index.faiss` mv 进 `data/rag_archive_20260907_w4/`（kb_raw.json 在 W2 已归档所以缺席；links.json / kb_meta.json / 遥测 / 评测历史保留）。是 mv 不是 rm，回滚 = 拷回三件套再重启。

**30 题基线对比（同一题集，旧链路 vs WeKnora，双轮真机）**：

| 指标（overall，只算 knowledge 题） | 旧链路 | WeKnora | 变化 |
|---|---|---|---|
| 忠实度 | 0.889 | 0.519 | -0.37 |
| 答案相关性 | 0.964 | 0.914 | -0.05 |
| 上下文精确率 | 0.024 | 0.419 | **+0.39** |
| 上下文召回率 | 0.007 | 0.444 | **+0.44** |

**怎么解读**：旧链路检索层对这套题接近全盲（精确率/召回≈0，因为旧语料就是 8 篇门户快照，跟题集主题错位），它的高忠实度其实是「不会就拒答」撑起来的。WeKnora 检索层有真实命中（+0.4 量级），但忠实度被拉低——WeKnora chat 对语料没覆盖的题（能耗/标准/KPI/安全）**不拒答，而是用大模型世界知识硬答**，裁判判为编造。分类别看得更直白：数字孪生专题（有语料）10 题里 7 题显著提升、q19/q21/q24/q27 直逼满分 0.988；语料没覆盖的类别显著下降。**结论：引擎方向正确，短板从「检索不出」变成「语料外不拒答」**——后续优化方向明确：门户侧引用数为 0 时直接给拒答话术（不透传 WeKnora 的自由发挥），或收紧 WeKnora 会话提示词。对照组自检正常（旧链路 0.75 / WeKnora 0.44 均值，跑题题 q06/q13 两轮一致）。

**验收对照 SPEC 第八节**：PRD 生成 grounded=true 且 hits=10、来源为 WeKnora 语料（PRD 7024 字）✓；评测 30 题四指标出数、报告带 engine 标注 ✓；清理后冒烟：知识问答 engine=weknora 带 14 来源、smalltalk 原链路 ✓；本地单测 83/83（test_prd 44 + test_rag_eval 24 + test_rag_intents 15）✓。

**坑与教训**：
1. **服务器构建上下文是 source/ 子目录**：rag/ 在 /data/projects/ai-manufacturing-zone/source/rag/，sftp 直传项目根的 rag/ 会静默传错地方（第一次部署备份文件数为 0 就是这么发现的）。
2. **docker compose exec 的 /tmp 和宿主机 /tmp 是两个世界**：脚本 sftp 到宿主机 /tmp 后 exec 报 No such file，必须先 `docker compose cp` 进容器；容器重建后容器侧 /tmp 还会被清空，要重拷。
3. 容器里跑 `python /tmp/xxx.py` 时 sys.path[0] 是 /tmp 不是 /app，import rag 前必须 `sys.path.insert(0, "/app")`。
4. nohup + & 启动的容器内长任务偶发静默死亡（日志都没有）；PRD 冒烟改**前台 exec 直跑**（SSH 读等 7 分钟超时内）一次成功。fire-and-forget 的正确姿势：`> log 2>&1 < /dev/null &`，且 paramiko 别把 stdout 读到 EOF——读到 EOF 会等后台进程退出，直接超时。
5. WeKnora 评测每题 ~33s（SSE 问答+直查+4 次裁判），30 题一轮 16.7 分钟，比旧链路（7.8 分钟）慢一倍——离线评测可接受，线上问答不受影响（W3 实测 6.8s）。

**已知限制 / 后续建议**：
- WeKnora 语料外硬答是忠实度掉分的根因，W3 已有 refused 口径但答案仍透传——建议下一版门户侧对「引用=0 的知识题」直接给拒答话术。
- PRD sources 未按文档去重（同一篇 PDF 多个分块会重复出现），纯展示层小瑕疵。
- 回滚网语义变化：WEKNORA_ENABLED=false 代码链路仍在，但旧语料已归档，完整回滚需先从 rag_archive_20260907_w4 拷回三件套再重启（与 SPEC「归档不删」一致）。

**改动文件**：`rag/engine.py`、`rag/prd.py`、`rag/evaluate.py`、`rag/eval_questions.json`、14 个旧模块 DEPRECATED 头注释、`tests/test_rag_eval.py`（题集断言 18→30）；服务器备份 backups/w4/（18 个被替换文件的改动前版本）+ data/rag_archive_20260907_w4/（旧检索三件套）。

## 二十九、Slice A1 · 曳光弹：第一个正式垂直智能体「售前方案师」上线（2026-09-08）

**背景**：W4 收官后讨论垂直智能体方向，确定分期 A1 曳光弹（激活卡片）→ A2 编排层（planner+注册表框架）→ A3 第二个垂直智能体 → A4 评测驱动自进化（30 题评测当回归安全网，掉分不放行）。A1 的目标一句话：**把首页智能体卡片从"展示"变成"入口"**。

**功能清单（谁要干什么）**：
- 访客在首页「项目矩阵」区看到一张带"已上线"徽标的在线智能体卡片（售前方案师），点"立即体验"直接弹窗用，不用登录后台。
- 访客填写公司/行业/业务介绍，选择引导或规范化模式，生成一份面向该客户的《AI 智能体平台功能需求 PRD》，可复制全文或下载 .md。
- 管理员在后台的 PRD 生成器保持原样，两边共用同一引擎，互不影响。
- 不做的（边界）：不做多智能体编排、不做智能体间通信、注册表暂写死在 app.py（A2 再抽框架）——一个实现不预建抽象。

**实现（垂直切片）**：
- 后端 `app.py`：`GET /api/agents` 公开注册表（AGENT_REGISTRY，一条记录 = id/name/role/emoji/color/desc/caps/status/endpoint，status=live 的会被首页渲染成入口）；`POST /api/agents/prd/run` 公开版 PRD 生成，与 admin 版同一 `kb_prd.generate_prd`，限流从紧：每 IP 每小时 5 次。
- **顺带修了一个真隐患**：原 `rate_limited()` 所有端点共用一个按 IP 计数的字典——知识问答（10 次/分）会把公开 PRD 的 5 次/小时额度吃掉。给 `rate_limited` 加了 `bucket` 参数，公开 PRD 用独立桶 `agent_prd`，旧端点默认桶行为不变。
- 前端 `AgentPRD.jsx`（新）：公开版 PRD 弹窗，复用 AdminPRD 导出的 `MarkdownView`（导出而非复制，避免两份渲染器漂移），无需 admin token；说明文字放大到 14px（面向客户可读性）。
- 前端 `main.jsx`：挂载时拉一次 `/api/agents`（失败静默降级，不影响原有卡片），在项目卡片网格上方渲染"在线智能体"行；`style.css` 加已上线徽标/弹窗样式约 20 行。

**测试结果**：
- 本地：py_compile 通过；test_prd 44/44；vite build 43 modules；自写冒烟 10/10（注册表形状/空入参 400/admin 401/限流 429/桶隔离结构断言，generate_prd 打桩零 LLM 成本）。
- 真机：容器重建后首页 200 且引用新包 index-Bbhljq53.js；`/api/agents` 返回注册表；公开端点空入参 400；admin 版未登录仍 401；**真机真实生成一次：grounded=True，hits=10，prd_len=8013**（知识库接地生效）。浏览器实开页面标题正常。
- 视觉验证兜底：QoderWork 截图通道故障（sharp 依赖缺失）+ SPA 元素树截断，改用等效验证——从服务器拉正在服役的 JS 包确认包含 立即体验/已上线/售前方案师/agent-prd-modal/prd-run 等新字符串，加上注册表端点返回 live 数据，渲染链路成立。

**坑与教训**：
1. **本地冒烟先查 key**：写冒烟脚本时没注意本机配了 DASHSCOPE_API_KEY，合法入参循环直接打了 2-3 次真 LLM 才被杀掉。零成本冒烟必须先打桩 `has_api_key`/`generate_prd`，别赌环境变量。
2. 服务器 source/ 下没有 src/（前端源码从不上服务器，本地构建只传 dist/），sftp 往 source/src/ 传文件直接 ENOENT；部署脚本先探路再上传。
3. 限流字典跨端点共享这种"以前没事"的隐患，会在新端点把限额收紧时变成用户可见 bug——加严限额前先审共享状态。
4. 截图通道坏掉时的真机验证替代方案：拉线上静态资源 grep 关键字符串 + curl 端点链路，比只看 HTTP 200 强得多。

**已知限制**：限流是进程内存态，重启清零；注册表硬编码在 app.py（A2 迁注册表框架）；弹窗在窄屏（<720px）下未做专门适配（modal 自带 overflow 滚动）。

**改动文件**：`app.py`（注册表+公开端点+rate_limited bucket）、`src/AgentPRD.jsx`（新）、`src/main.jsx`、`src/AdminPRD.jsx`（导出 MarkdownView）、`src/style.css`；服务器备份 backups/a1/（app.py + dist）。


---

## §三十 · A2 编排层（注册表框架 + planner）+ 预约演示（邮件通知）

**日期**：2026-09-08　**切片**：A2 + 预约演示　**状态**：已部署真机验证 ✅

**功能清单**：
1. A2 编排层：新建 `agents/` 包（base 统一契约 / registry 注册表 / runtime KB 注入 / prd_advisor 收编），app.py 硬编码注册表迁出，import 即注册。
2. 新端点：`GET /api/agents`（注册表，驱动首页）、`POST /api/agents/dispatch`（planner：triggers 关键词路由，支持 auto_run 代跑）、`POST /api/agents/<id>/run`（通用运行）、`POST /api/agents/prd/run`（A1 兼容别名，返回扁平形状给旧缓存页面）。
3. 预约演示：`POST /api/demo/booking`（限流 3次/h/IP）→ `notify.py` QQ SMTP 465 SSL 真邮件 → 落盘 `data/demo_bookings.json`（留 200 条）；`GET /api/admin/demo/bookings` 后台列表。
4. 前端：离线项目卡「离线」→「待演示」，死链「访问项目」换成「预约演示」按钮 → DemoBooking 弹窗；AgentPRD 改用注册表 endpoint + 新契约解包；AdminPanel 新增「预约演示」页签（AdminBookings）。
5. compose 透传 SMTP_HOST/PORT/USER/PASS/NOTIFY_TO；服务器 Dockerfile 增补 `COPY source/notify.py` 与 `COPY source/agents/`；.env 追加 SMTP_USER/SMTP_PASS（授权码）。

**背景结论（对用户两个疑问的答案）**：
- 项目卡全「离线」是**真实的**：演示容器平时被销毁省磁盘，心跳系统本身健康（last_check 每分钟刷新）。
- 「预约演示功能之前做过、还测过邮件」是**记忆偏差**：全库（代码/DEV_LOG/记忆）无任何 smtp/booking 痕迹，此前只做过 Server酱/Win通知实验；本切片为首次实现。

**测试结果**：test_agents 51/51、test_booking 28/28 全过（邮件打桩，不发真件）；回归 test_prd 44/44、test_rag_unit 11/11；build 45 模块。真机：注册表/triggers 正确，dispatch 命中，400/404 语义正确，新 bundle 上线，**真预约邮件已发出（notified=true，QQ 邮箱 465 SSL 通）**，admin 列表 login-token 后 200，真生成一次（grounded=True hits=10 refs=10 prd_len=7798 confidence=0.6）。

**坑与教训**：
1. **_run_agent 元组返回吞状态码**：辅助函数返回 `(jsonify(...), 400)`，调用方只 `return res` → 400/502 全变 200；dispatch auto_run 更是把 Response 对象塞进 jsonify 直接 500。教训：辅助函数要**把状态码写回 Response 本体**再返回；单测先行这次真的抓到了。
2. **服务器 Dockerfile 与本地是两套**：服务器版在项目根、路径全带 `source/` 前缀（context=项目根）；本地版 context=项目根本身。改 Dockerfile 必须分头维护，不能拿本地的直接覆盖服务器。
3. `curl -w '%{http_code}'` 出现在 Python %-格式串里必炸（`%{` 被当格式符）——W4 踩过，A2 部署脚本又踩，验证命令一律改字符串拼接。
4. **token 公式有"双盐"**：`hash_password(account+password+SECRET_KEY)` 内部再拼一次 SECRET_KEY = sha256(A+P+S+S)。外部验算只拼一次必 401；验 admin 鉴权最稳的姿势是**直接调 login 端点拿 token**。
5. `/api/options` 是 W4 冒烟脚本的幻影路径（app 里从不存在，落 SPA 兜底返回 index.html 还 200）——冒烟命令要对着路由表写，别互相抄。
6. 本机测试顺序陷阱：`register()` 对纯空白 id 原先不报错，残缺类混进注册表让 route_task AttributeError——注册器现在对 id 做 strip+非空强校验。

**已知限制 / 后续建议**：
- 预约邮件同步发送（SMTP 3-8s），极端慢时用户等待变长；量大可改后台线程+前端轮询。
- 预约列表无删除/导出；限流内存态重启清零（沿用现状）。
- dispatch 的 planner 目前是关键词匹配，多智能体并存后的优先级/协同留待 A3。

**改动文件**：`agents/`（新，5 文件）、`notify.py`（新）、`app.py`（agent/booking 端点 + _run_agent 修复）、`Dockerfile`、`docker-compose.yml`、`src/AgentPRD.jsx`、`src/DemoBooking.jsx`（新）、`src/AdminBookings.jsx`（新）、`src/main.jsx`、`src/style.css`、`tests/test_agents.py`（新）、`tests/test_booking.py`（新）；服务器 backups/a2/（app.py、Dockerfile、docker-compose.yml、dist）。
