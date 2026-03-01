#!/usr/bin/env bash
set -euo pipefail

# 构建后端生产镜像
IMAGE_NAME="${IMAGE_NAME:-job-market-research-agent}"

echo "开始构建镜像: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" .
echo "镜像构建完成: ${IMAGE_NAME}"
