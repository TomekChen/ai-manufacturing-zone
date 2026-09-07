FROM python:3.12-slim

WORKDIR /app

# Python 依赖（清华源，容器内构建更快）
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 后端源码：app.py + kb.py 兼容层 + rag/ 包（含离线评测题集）+ agents/ 智能体包 + notify.py 邮件
COPY app.py kb.py notify.py ./
COPY rag/ ./rag/
COPY agents/ ./agents/

# 前端构建产物（本地 vite build 生成 dist/ 后再构建镜像）
COPY dist/ ./dist/

# 运行时数据目录（由 compose 挂载 ./data 覆盖）
RUN mkdir -p /app/data/uploads

EXPOSE 8804

CMD ["python", "app.py"]
