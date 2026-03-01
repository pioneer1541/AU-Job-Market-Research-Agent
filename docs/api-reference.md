# API 参考文档

面向开源社区开发者的后端 API 文档。本文档基于当前代码实现（`backend/main.py`、`backend/api/routes.py`、`backend/api/schemas.py`）。

## 1. 概述

### API 基础 URL

- 本地开发：`http://localhost:8000`
- 统一前缀：`/api`
- 完整示例：`http://localhost:8000/api/health`

### 认证方式

- 当前版本：**无需认证**（无 Token / API Key）
- 未来扩展：可在 `FastAPI` 中通过中间件或依赖注入加入鉴权机制

### 通用响应格式

当前实现中，成功响应按各端点 `response_model` 返回；错误响应有两类：

1. `HTTPException`（例如 404）
```json
{
  "detail": "职位未找到: job-999"
}
```

2. 全局异常处理器（422/400/500）
```json
{
  "error": "ValidationError",
  "message": "请求数据验证失败",
  "detail": "[...]"
}
```

> 注意：错误响应在当前版本并非完全统一结构，调用方应同时兼容 `detail` 与 `error/message/detail` 两种格式。

## 2. 端点列表

以下为当前主要端点（含你指定的 7 个）：

- `GET /api/health` - 健康检查
- `POST /api/jobs/search` - 职位搜索
- `GET /api/jobs/{job_id}` - 获取职位详情
- `GET /api/analyze` - 市场分析
- `GET /api/reports` - 报告列表
- `GET /api/reports/{report_id}` - 报告详情（代码实际为复数 `reports`）
- `GET /api/report/pdf` - PDF 下载（通过查询参数 `report_id`）

兼容旧版（已弃用）端点：

- `POST /api/search`（deprecated）
- `GET /api/search/{search_id}/status`（deprecated）

## 3. 每个端点详细说明

### 3.1 GET /api/health

- 请求方法：`GET`
- 路径参数：无
- 查询参数：无
- 请求体：无

响应体 JSON Schema：

```json
{
  "type": "object",
  "properties": {
    "status": { "type": "string", "example": "ok" },
    "version": { "type": "string", "example": "0.1.0" }
  },
  "required": ["status", "version"]
}
```

示例请求：

```bash
curl -X GET "http://localhost:8000/api/health"
```

示例响应：

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### 3.2 POST /api/jobs/search

- 请求方法：`POST`
- 路径参数：无
- 查询参数：无
- 请求体：`SearchRequest`

请求体 JSON Schema：

```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string", "minLength": 1 },
    "location": { "type": ["string", "null"] },
    "max_results": { "type": "integer", "minimum": 1, "maximum": 100, "default": 20 }
  },
  "required": ["query"]
}
```

响应体 JSON Schema：

```json
{
  "type": "object",
  "properties": {
    "jobs": {
      "type": "array",
      "items": { "$ref": "#/components/schemas/JobListing" }
    },
    "total": { "type": "integer" },
    "query": { "type": "string" }
  },
  "required": ["jobs", "total", "query"]
}
```

示例请求：

```bash
curl -X POST "http://localhost:8000/api/jobs/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AI Engineer",
    "location": "Melbourne",
    "max_results": 10
  }'
```

示例响应：

```json
{
  "jobs": [
    {
      "id": "job-001",
      "title": "Senior AI Engineer",
      "company": "TechCorp Melbourne",
      "location": "Melbourne, VIC",
      "salary": "$150,000 - $180,000",
      "description": "We are looking for an experienced AI Engineer to join our team...",
      "url": "https://seek.com.au/job/001",
      "source": "seek",
      "posted_date": "2026-02-28",
      "num_applicants": 132
    }
  ],
  "total": 1,
  "query": "AI Engineer"
}
```

### 3.3 GET /api/jobs/{job_id}

- 请求方法：`GET`
- 路径参数：
  - `job_id` (`string`, required)：职位 ID
- 查询参数：无
- 请求体：无

响应体 JSON Schema：

```json
{
  "type": "object",
  "properties": {
    "id": { "type": "string" },
    "title": { "type": "string" },
    "company": { "type": "string" },
    "location": { "type": "string" },
    "salary": { "type": ["string", "null"] },
    "description": { "type": "string" },
    "url": { "type": "string" },
    "source": { "type": "string" },
    "posted_date": { "type": ["string", "null"] },
    "num_applicants": { "type": ["integer", "null"] },
    "analysis": { "$ref": "#/components/schemas/AnalysisResult" }
  },
  "required": ["id", "title", "company", "location", "description", "url", "source"]
}
```

示例请求：

```bash
curl -X GET "http://localhost:8000/api/jobs/job-001"
```

示例响应：

```json
{
  "id": "job-001",
  "title": "Senior AI Engineer",
  "company": "TechCorp Melbourne",
  "location": "Melbourne, VIC",
  "salary": "$150,000 - $180,000",
  "description": "We are looking for an experienced AI Engineer to join our team...",
  "url": "https://seek.com.au/job/001",
  "source": "seek",
  "posted_date": "2026-02-28",
  "num_applicants": 132,
  "analysis": {
    "job_id": "job-001",
    "hard_skills": ["Python", "TensorFlow", "PyTorch", "AWS", "Docker"],
    "soft_skills": [],
    "years_of_experience": null,
    "industry_keywords": [],
    "responsibility_themes": [],
    "qualifications": [],
    "skills_required": ["Python", "TensorFlow", "PyTorch", "AWS", "Docker"],
    "experience_level": "Senior",
    "salary_estimate": "$150,000 - $180,000",
    "key_requirements": ["5+ years experience", "ML system design", "Team leadership"],
    "industry": "Technology"
  }
}
```

404 示例：

```json
{
  "detail": "职位未找到: nonexistent-job"
}
```

### 3.4 GET /api/analyze

- 请求方法：`GET`
- 路径参数：无
- 查询参数：
  - `query` (`string`, required)：搜索关键词
  - `location` (`string`, optional)：工作地点
  - `max_results` (`integer`, optional, 默认 20, 范围 1-100)
- 请求体：无

响应体 JSON Schema：

```json
{
  "type": "object",
  "properties": {
    "market_insights": { "$ref": "#/components/schemas/MarketInsights" },
    "jobs": {
      "type": "array",
      "items": { "$ref": "#/components/schemas/JobListing" }
    },
    "report": { "type": "string" }
  },
  "required": ["market_insights", "jobs", "report"]
}
```

示例请求：

```bash
curl -G "http://localhost:8000/api/analyze" \
  --data-urlencode "query=AI Engineer" \
  --data-urlencode "location=Melbourne" \
  --data-urlencode "max_results=5"
```

示例响应（节选）：

```json
{
  "market_insights": {
    "total_jobs": 1,
    "avg_salary_range": "$140,000 - $170,000",
    "top_skills": ["Python", "PyTorch", "TensorFlow", "AWS", "Docker"],
    "top_companies": ["TechCorp Melbourne", "DataDriven Inc", "Innovation Labs"],
    "experience_distribution": {"Senior": 2, "Mid-Senior": 1},
    "location_distribution": {"Melbourne, VIC": 1, "Sydney, NSW": 1, "Remote": 1},
    "report_meta": {
      "query": "AI Engineer",
      "location": "Melbourne",
      "max_results": 5,
      "generated_at": "2026-03-01T12:00:00",
      "report_id": "r-1234567890abcdef"
    }
  },
  "jobs": [],
  "report": "# AI Engineer 市场分析报告\n..."
}
```

### 3.5 GET /api/reports

- 请求方法：`GET`
- 路径参数：无
- 查询参数：
  - `limit` (`integer`, optional, 默认 20, 范围 1-100)
  - `offset` (`integer`, optional, 默认 0, 最小 0)
- 请求体：无

响应体 JSON Schema：

```json
{
  "type": "object",
  "properties": {
    "total": { "type": "integer" },
    "reports": {
      "type": "array",
      "items": { "$ref": "#/components/schemas/ReportMeta" }
    }
  },
  "required": ["total", "reports"]
}
```

示例请求：

```bash
curl -X GET "http://localhost:8000/api/reports?limit=10&offset=0"
```

示例响应：

```json
{
  "total": 2,
  "reports": [
    {
      "id": "r-9f65f2b0d7f94a21",
      "query": "AI Engineer",
      "location": "Melbourne",
      "max_results": 20,
      "results_count": 3,
      "created_at": "2026-03-01T10:25:38"
    }
  ]
}
```

### 3.6 GET /api/reports/{report_id}

- 请求方法：`GET`
- 路径参数：
  - `report_id` (`string`, required)：报告 ID
- 查询参数：无
- 请求体：无

响应体 JSON Schema：

```json
{
  "type": "object",
  "properties": {
    "id": { "type": "string" },
    "query": { "type": "string" },
    "location": { "type": "string" },
    "max_results": { "type": "integer" },
    "created_at": { "type": "string" },
    "market_insights": { "$ref": "#/components/schemas/MarketInsights" },
    "jobs": {
      "type": "array",
      "items": { "$ref": "#/components/schemas/JobListing" }
    },
    "report": { "type": "string" }
  },
  "required": ["id", "query", "location", "max_results", "created_at", "market_insights", "jobs", "report"]
}
```

示例请求：

```bash
curl -X GET "http://localhost:8000/api/reports/r-9f65f2b0d7f94a21"
```

示例响应（节选）：

```json
{
  "id": "r-9f65f2b0d7f94a21",
  "query": "AI Engineer",
  "location": "Melbourne",
  "max_results": 20,
  "created_at": "2026-03-01T10:25:38",
  "market_insights": {
    "total_jobs": 3,
    "top_skills": ["Python", "FastAPI", "Docker"],
    "report_meta": {
      "report_id": "r-9f65f2b0d7f94a21"
    }
  },
  "jobs": [],
  "report": "# AI Engineer 市场分析报告\n..."
}
```

404 示例：

```json
{
  "detail": "报告不存在: r-not-found"
}
```

### 3.7 GET /api/report/pdf

- 请求方法：`GET`
- 路径参数：无
- 查询参数：
  - `report_id` (`string`, required, min_length=1)
- 请求体：无
- 响应体：`application/pdf` 二进制流

响应头示例：

```http
Content-Type: application/pdf
Content-Disposition: attachment; filename="AI_Engineer_r-9f65f2b0d7f94a21.pdf"
```

示例请求：

```bash
curl -X GET "http://localhost:8000/api/report/pdf?report_id=r-9f65f2b0d7f94a21" \
  --output market-report.pdf
```

404 示例：

```json
{
  "detail": "报告不存在: r-not-found"
}
```

## 4. 数据模型

以下为常用数据模型（与代码命名对齐）。

### JobListing

```json
{
  "type": "object",
  "properties": {
    "id": { "type": "string" },
    "title": { "type": "string" },
    "company": { "type": "string" },
    "location": { "type": "string" },
    "salary": { "type": ["string", "null"] },
    "description": { "type": "string" },
    "url": { "type": "string" },
    "source": { "type": "string", "default": "unknown" },
    "posted_date": { "type": ["string", "null"] },
    "num_applicants": { "type": ["integer", "null"] }
  },
  "required": ["id", "title", "company", "location"]
}
```

### AnalysisResult

代码中的响应模型名称是 `JobAnalysis`，语义上可视为 `AnalysisResult`：

```json
{
  "type": "object",
  "properties": {
    "job_id": { "type": "string" },
    "hard_skills": { "type": "array", "items": { "type": "string" } },
    "soft_skills": { "type": "array", "items": { "type": "string" } },
    "years_of_experience": { "type": ["string", "null"] },
    "industry_keywords": { "type": "array", "items": { "type": "string" } },
    "responsibility_themes": { "type": "array", "items": { "type": "string" } },
    "qualifications": { "type": "array", "items": { "type": "string" } },
    "skills_required": { "type": "array", "items": { "type": "string" } },
    "experience_level": { "type": "string" },
    "salary_estimate": { "type": ["string", "null"] },
    "key_requirements": { "type": "array", "items": { "type": "string" } },
    "industry": { "type": ["string", "null"] }
  },
  "required": ["job_id"]
}
```

### MarketInsights

```json
{
  "type": "object",
  "properties": {
    "total_jobs": { "type": "integer" },
    "avg_salary_range": { "type": ["string", "null"] },
    "top_skills": { "type": "array", "items": { "type": "string" } },
    "top_companies": { "type": "array", "items": { "type": "string" } },
    "experience_distribution": { "type": "object", "additionalProperties": { "type": "integer" } },
    "location_distribution": { "type": "object", "additionalProperties": { "type": "integer" } },
    "sample_overview": { "type": "object" },
    "trend_analysis": { "type": "object" },
    "salary_analysis": { "type": "object" },
    "applicant_analysis": { "type": "object" },
    "competition_intensity": { "type": "object" },
    "skill_profile": { "type": "object" },
    "deep_analysis": { "type": "object" },
    "employer_profile": { "type": "object" },
    "top_jobs": { "type": "object" },
    "report_meta": { "type": "object" },
    "report_sections": { "type": "object", "additionalProperties": { "type": "string" } }
  },
  "required": ["total_jobs", "top_skills", "top_companies"]
}
```

### ReportMeta

代码中的响应模型名称是 `ReportSummary`，语义上可视为 `ReportMeta`：

```json
{
  "type": "object",
  "properties": {
    "id": { "type": "string" },
    "query": { "type": "string" },
    "location": { "type": "string" },
    "max_results": { "type": "integer" },
    "results_count": { "type": "integer" },
    "created_at": { "type": "string", "description": "ISO 8601" }
  },
  "required": ["id", "query", "max_results", "created_at"]
}
```

## 5. 错误处理

### 错误响应格式

1. `HTTPException`（典型 404）

```json
{
  "detail": "报告不存在: r-xxxx"
}
```

2. 请求校验错误（422，来自全局异常处理器）

```json
{
  "error": "ValidationError",
  "message": "请求数据验证失败",
  "detail": "[...]"
}
```

3. 未捕获异常（500）

```json
{
  "error": "InternalServerError",
  "message": "服务器内部错误",
  "detail": null
}
```

### 常见错误码

- `400 Bad Request`：业务值错误（`ValueError`）
- `404 Not Found`：资源不存在（职位/报告）
- `422 Unprocessable Entity`：参数或请求体校验失败
- `500 Internal Server Error`：服务端异常

## 6. 使用示例

### curl 示例

```bash
# 1) 职位搜索
curl -X POST "http://localhost:8000/api/jobs/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"AI Engineer","location":"Melbourne","max_results":5}'

# 2) 市场分析
curl -G "http://localhost:8000/api/analyze" \
  --data-urlencode "query=AI Engineer" \
  --data-urlencode "location=Melbourne" \
  --data-urlencode "max_results=5"

# 3) 获取报告列表
curl "http://localhost:8000/api/reports?limit=10&offset=0"

# 4) 下载 PDF
curl "http://localhost:8000/api/report/pdf?report_id=r-xxxxxxxxxxxxxxxx" --output report.pdf
```

### Python requests 示例

```python
import requests

BASE_URL = "http://localhost:8000/api"

# 1) 搜索职位
search_resp = requests.post(
    f"{BASE_URL}/jobs/search",
    json={
        "query": "AI Engineer",
        "location": "Melbourne",
        "max_results": 5,
    },
    timeout=30,
)
search_resp.raise_for_status()
search_data = search_resp.json()
print("search total:", search_data["total"])

# 2) 执行市场分析
analyze_resp = requests.get(
    f"{BASE_URL}/analyze",
    params={"query": "AI Engineer", "location": "Melbourne", "max_results": 5},
    timeout=60,
)
analyze_resp.raise_for_status()
analyze_data = analyze_resp.json()
report_id = analyze_data.get("market_insights", {}).get("report_meta", {}).get("report_id")
print("report_id:", report_id)

# 3) 拉取报告详情
if report_id:
    detail_resp = requests.get(f"{BASE_URL}/reports/{report_id}", timeout=30)
    detail_resp.raise_for_status()
    print("report query:", detail_resp.json()["query"])

    # 4) 下载 PDF
    pdf_resp = requests.get(f"{BASE_URL}/report/pdf", params={"report_id": report_id}, timeout=60)
    pdf_resp.raise_for_status()
    with open("market-report.pdf", "wb") as f:
        f.write(pdf_resp.content)
    print("PDF saved: market-report.pdf")
```
