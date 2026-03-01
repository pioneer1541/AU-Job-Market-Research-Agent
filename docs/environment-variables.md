# 环境变量配置说明

本文档用于说明项目在开发与生产环境中的环境变量配置方式、用途及安全要求。

## 1. 配置原则

- 不要在代码中硬编码任何密钥、Token 或敏感地址。
- 不要提交真实的 `.env` 文件到仓库。
- 开发环境参考 `.env.example`，生产环境参考 `.env.production.example`。
- 生产环境优先使用部署平台的 Secret 管理（如 Railway Variables、GitHub Actions Secrets、容器编排 Secret）。

## 2. 变量清单

### 2.1 必需变量

1. `LLM_API_KEY`
- 用途：访问 LLM 服务的鉴权密钥。
- 是否必需：是。
- 默认值：无（必须显式配置）。
- 示例：`sk-your-llm-api-key`

2. `LLM_BASE_URL`
- 用途：LLM 接口基地址（OpenAI 兼容格式）。
- 是否必需：是。
- 默认值：`https://api.openai.com/v1`
- 示例：`https://api.openai.com/v1`

3. `APIFY_API_TOKEN`
- 用途：访问 Apify Seek Scraper 的授权 Token。
- 是否必需：是。
- 默认值：无（必须显式配置）。
- 示例：`apify_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 2.2 可选变量

1. `APP_ENV`
- 用途：标识运行环境。
- 是否必需：否。
- 默认值：`development`
- 可选值：`development` / `production`

2. `LOG_LEVEL`
- 用途：控制日志输出级别。
- 是否必需：否。
- 默认值：`INFO`
- 建议值：`DEBUG` / `INFO` / `WARNING` / `ERROR`

### 2.3 可选扩展变量（按需配置）

1. `LLM_PROVIDER`
- 用途：标记 LLM 提供商类型。
- 默认值：`openai-compatible`

2. `LLM_MODEL`
- 用途：指定调用的模型名称。
- 默认值：`glm-5`

## 3. 如何获取 API Key

### 3.1 获取 `LLM_API_KEY`

1. 登录你使用的 LLM 提供商控制台（如 OpenAI 或其他 OpenAI 兼容平台）。
2. 进入 API Key 管理页面。
3. 创建新的 Key，并仅在创建时保存明文。
4. 将 Key 写入环境变量 `LLM_API_KEY`，不要写入代码仓库。

### 3.2 获取 `APIFY_API_TOKEN`

1. 登录 [Apify 控制台](https://console.apify.com/)。
2. 打开 `Settings` 或 `Integrations` 下的 API Token 页面。
3. 复制你的 Token。
4. 将 Token 配置到环境变量 `APIFY_API_TOKEN`。

## 4. 本地与生产配置方式

### 4.1 本地开发

1. 复制模板：`cp .env.example .env`
2. 填写真实的 `LLM_API_KEY`、`LLM_BASE_URL`、`APIFY_API_TOKEN`
3. 启动服务前确认 `.env` 不包含在版本控制中

### 4.2 生产部署

1. 参考 `.env.production.example` 创建生产配置。
2. 优先在部署平台的 Secret 管理页面逐项设置变量。
3. 至少配置所有“必需变量”。
4. 建议设置 `APP_ENV=production` 与 `LOG_LEVEL=INFO`。

## 5. 安全建议

- 定期轮换 API Key 与 Token。
- 为不同环境使用不同密钥，避免共用。
- 限制密钥权限范围（最小权限原则）。
- 当密钥泄露时，立即吊销并替换。
