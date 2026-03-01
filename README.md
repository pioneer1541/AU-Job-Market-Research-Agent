# Job Market Research Agent

一个基于 AI Agent 的职位市场研究工具，用于自动抓取职位信息、解析 JD 内容并生成可视化分析结果，帮助你快速理解技能需求、薪资分布与市场趋势。

仓库地址：<https://github.com/pioneer1541/AU-Job-Market-Research-Agent.git>

## 功能概览

- 自动职位采集：通过 Apify Seek Scraper 抓取职位数据
- JD 智能解析：用 LLM 提取技能、经验、薪资、岗位画像
- 数据去重与清洗：降低重复职位对分析结果的干扰
- 可视化分析：提供图表化洞察和历史记录追踪
- 多模型支持：兼容 OpenAI 接口风格模型与可配置提供商

## 技术栈

- 后端：FastAPI、LangGraph、LangChain
- 前端：Streamlit、Plotly
- 数据源：Apify（Seek Scraper）
- 测试：pytest
- 部署：Docker、Docker Compose、Railway（可选）

## 项目结构

```text
job-market-research-agent/
├── backend/                    # 后端服务与 Agent 工作流
│   ├── agents/                 # LangGraph 节点与流程
│   ├── api/                    # FastAPI 路由与数据模型
│   ├── services/               # LLM、Apify 等外部服务封装
│   ├── utils/                  # 通用工具函数
│   └── tests/                  # 后端测试
├── frontend/                   # Streamlit 前端应用
│   ├── components/             # 可复用组件
│   ├── pages/                  # 多页面 UI
│   └── utils/                  # 前端工具函数
├── docs/                       # 文档（环境变量、测试报告等）
├── scripts/                    # 辅助脚本
├── tests/                      # 项目级测试
├── .env.example                # 开发环境变量模板
├── .env.production.example     # 生产环境变量模板
├── docker-compose.yml          # 本地/部署编排示例
└── README.md
```

## 安装与运行

### 1) 本地开发

1. 创建虚拟环境并安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

2. 配置环境变量

```bash
cp .env.example .env
# 按 docs/environment-variables.md 填写真实值
```

3. 启动后端

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

4. 启动前端（新终端）

```bash
streamlit run frontend/app.py
```

### 2) 运行测试

```bash
pytest -q
```

## 环境变量说明

已提供完整说明文档：

- [docs/environment-variables.md](docs/environment-variables.md)
- 开发模板：`.env.example`
- 生产模板：`.env.production.example`

重点安全要求：

- 不要提交真实 `.env` 文件
- 不要在代码中硬编码任何密钥或 Token
- 优先使用部署平台 Secret 管理

## 部署说明

### Docker Compose 示例

```bash
cp .env.production.example .env
# 填写生产变量

docker compose up -d --build
docker compose logs -f backend
```

### 生产部署建议

- 至少配置 `LLM_API_KEY`、`LLM_BASE_URL`、`APIFY_API_TOKEN`
- 建议设置 `APP_ENV=production`、`LOG_LEVEL=INFO`
- 使用平台 Secret 管理环境变量，不在镜像和仓库中保存明文

## 开发状态与路线图

当前状态：`Phase 1 - Foundation`

### Roadmap

- [x] 项目基础架构（前后端分离、基础工作流）
- [x] 环境变量规范与部署模板
- [x] 核心 API 与前端页面打通
- [ ] 增强分析维度（岗位级别、地区对比、技能聚类）
- [ ] 报告导出增强（PDF 模板、分享链接）
- [ ] 增加更多数据源与去重策略优化
- [ ] CI/CD 与质量门禁完善

## License

MIT License
