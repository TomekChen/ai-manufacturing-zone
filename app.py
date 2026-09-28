# -*- coding: utf-8 -*-
"""智能制造专区 · 后端装配入口。

R5 起 app.py 只做三件事：
1. 创建 Flask app 与知识库实例；
2. 装配区——按唯一顺序把共享设施注入各域模块、注册 Blueprint；
3. 转出口——把测试与运维引用的名字原样暴露在 app 模块上（公共 API 冻结）。

各域实现（一个文件一个变更理由，全部走 Blueprint+依赖注入，不 import app）：
  core.py       共享基础设施（路径/凭据/JSON 读写/鉴权/限流）
  portal.py     门户展示（外观配置/项目卡/探活心跳）
  qa.py         门户问答（公开上传/WeKnora 映射/问答内核/ask/feedback）
  agents_api.py 智能体门面（注册表/派发/直跑/后台 PRD 生成）
  webapp.py     站点服务（登录/图片上传/预约/SPA 静态）
  kb_admin.py   知识库管理（文档审核/采集/重建/遥测/评测/友链）
  kb_weknora.py WeKnora 引擎转发
  prd_sessions.py 方案会话账本（存档/回放/分享/入库飞轮）
  mcp_endpoint.py MCP 远程端点（Streamable HTTP /mcp）
"""
import os

from flask import Flask

from rag.store import KnowledgeStore
import agents  # import 即注册（agents/registry.py 底部挂载所有智能体实现）
import kb_admin
import kb_weknora
import portal
import qa
import agents_api
import webapp
import prd_sessions
import mcp_endpoint

# 供测试/运维引用的兼容转出口（app.<name> 与拆分前同一对象）
from core import (DATA_DIR, PROJECTS_FILE, ADMIN_ACCOUNT, ADMIN_PASSWORD,  # noqa: F401
                  SECRET_KEY, load_json, save_json, hash_password, rate_limited,
                  limiter, require_admin, _ask_limits)
from rag import prd as kb_prd  # noqa: F401  测试打桩用（app.kb_prd.*）
import notify  # noqa: F401  测试打桩用（app.notify.send_email）

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 全局上传上限 20MB（知识库文档放宽到 10MB）

# ── 共享设施 ────────────────────────────────────────────────────────────────
# 全局知识库存储（数据文件在 data/ 挂载卷内，容器重建不丢）
KB = KnowledgeStore(DATA_DIR)
# 智能体运行时注入（agents 包不反向依赖 app）：WeKnora 关闭时 PRD 回退检索用
agents.runtime.store = KB
# 知识管家与公开问答视图共用同一条问答内核（A3）
agents.runtime.kb_ask = qa.kb_ask_core

# ── 装配区：依赖注入 + Blueprint 注册（顺序即初始化顺序，一处看全） ──────────
qa.init(KB)
agents_api.init(KB)
portal.start_heartbeat()

prd_sessions.init(DATA_DIR, load_json, save_json, rate_limited, require_admin, KB)
kb_admin.init(KB, require_admin, DATA_DIR)
kb_weknora.init(require_admin)

for module in (portal, qa, agents_api, webapp, kb_admin, kb_weknora, prd_sessions,
               mcp_endpoint):
    app.register_blueprint(module.bp)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8804"))
    app.run(host="0.0.0.0", port=port, threaded=True)
