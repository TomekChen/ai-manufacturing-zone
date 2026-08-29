FROM python:3.12-slim

WORKDIR /app

# Install Python deps
COPY source/requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# Copy application
COPY source/app.py .
COPY source/kb.py .
COPY source/dist/ ./dist/

# Data dir will be mounted as volume
RUN mkdir -p /app/data/uploads

EXPOSE 8804

CMD ["python", "app.py"]
