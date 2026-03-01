# Job Market Research Agent

An AI-powered tool that automatically scrapes job listings from Seek, analyzes job descriptions using LLM agents, and generates visual market intelligence reports.

## Features

- **Automated Job Data Collection**: Fetch job listings from Seek via Apify API
- **LLM-Powered Analysis**: Extract tech stack, salary, experience requirements from JDs
- **Intelligent Deduplication**: Fuzzy matching to remove duplicate listings
- **Visual Reports**: Interactive charts and downloadable PDF reports
- **Multi-LLM Support**: Switch between OpenAI, Anthropic, and other providers

## Tech Stack

- **Backend**: FastAPI + LangGraph + LangChain
- **Frontend**: Streamlit + Plotly
- **Data Source**: Apify Seek Scraper API
- **Deployment**: Docker + Railway

## Project Structure

```
job-market-research-agent/
├── backend/
│   ├── agents/          # LangGraph agent nodes
│   ├── services/        # External API clients (Apify, LLM)
│   ├── api/             # FastAPI routes and schemas
│   ├── utils/           # Helper functions
│   └── tests/           # Unit and integration tests
├── frontend/            # Streamlit UI
├── requirements.txt     # Production dependencies
└── requirements-dev.txt # Development dependencies
```

## Quick Start

1. Clone the repository
2. Create virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements-dev.txt`
5. Copy `.env.example` to `.env` and fill in your API keys
6. Run backend: `uvicorn backend.main:app --reload`

## Configuration

环境变量配置请参考：

- 开发模板：`.env.example`
- 生产模板：`.env.production.example`
- 详细文档：`docs/environment-variables.md`

必需变量：

- `LLM_API_KEY`：LLM API 密钥
- `LLM_BASE_URL`：LLM API 地址
- `APIFY_API_TOKEN`：Apify API Token

可选变量：

- `APP_ENV`：运行环境（`development`/`production`）
- `LOG_LEVEL`：日志级别（`DEBUG`/`INFO`/`WARNING`/`ERROR`）

## Deployment

### Docker Compose（示例）

1. 复制生产模板并填写真实值：
   `cp .env.production.example .env`
2. 启动服务：
   `docker compose up -d --build`
3. 查看日志：
   `docker compose logs -f backend`

### 生产环境建议

- 不要将真实 `.env` 文件提交到仓库。
- 优先使用部署平台的 Secret 管理功能配置敏感变量。
- 部署时至少设置所有必需变量，并建议设置 `APP_ENV=production`。

## Development Status

🚧 Currently in Phase 1: Foundation & Learning

## License

MIT
