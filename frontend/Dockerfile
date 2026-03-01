FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 优化 Python 容器运行行为
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 先安装依赖，便于利用 Docker 构建缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制前端应用代码
COPY . .

# Streamlit 默认端口
EXPOSE 8501

# Railway 会注入 PORT；本地未注入时回退到 8501
CMD ["sh", "-c", "streamlit run app.py --server.port ${PORT:-8501} --server.address 0.0.0.0"]
