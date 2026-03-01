# syntax=docker/dockerfile:1

# 构建阶段：安装依赖到独立虚拟环境，避免把构建工具带入最终镜像
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VENV_PATH=/opt/venv

WORKDIR /app

# 某些依赖可能需要编译，构建阶段安装编译工具
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && python -m venv ${VENV_PATH} \
    && ${VENV_PATH}/bin/pip install --upgrade pip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN ${VENV_PATH}/bin/pip install -r requirements.txt


# 运行阶段：仅保留运行所需内容，减小镜像体积
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# 运行阶段补齐 PDF 渲染依赖：
# - WeasyPrint 依赖 pango/pixbuf/ffi/mime 数据
# - Matplotlib 中文字体依赖 Noto CJK
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi-dev \
        shared-mime-info \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY backend ./backend
COPY .env.example ./.env.example

EXPOSE 8000

# 兼容 Railway 的 PORT 环境变量，未设置时默认 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
