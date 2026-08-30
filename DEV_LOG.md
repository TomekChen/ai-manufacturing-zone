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
