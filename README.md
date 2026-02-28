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

Required environment variables:

- `LLM_API_KEY`: Your LLM provider API key
- `LLM_BASE_URL`: API endpoint (for OpenAI-compatible providers)
- `APIFY_API_TOKEN`: Your Apify API token

## Development Status

🚧 Currently in Phase 1: Foundation & Learning

## License

MIT
