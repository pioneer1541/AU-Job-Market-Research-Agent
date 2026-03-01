#!/usr/bin/env bash
set -euo pipefail

# 运行后端容器，默认读取项目根目录 .env
IMAGE_NAME="${IMAGE_NAME:-job-market-research-agent}"
CONTAINER_NAME="${CONTAINER_NAME:-job-market-research-agent}"
PORT="${PORT:-8000}"

if [[ ! -f ".env" ]]; then
  echo "未找到 .env 文件，请先创建后再运行容器。"
  exit 1
fi

echo "启动容器: ${CONTAINER_NAME} (端口 ${PORT})"
docker run --rm \
  --name "${CONTAINER_NAME}" \
  --env-file .env \
  -p "${PORT}:8000" \
  "${IMAGE_NAME}"
