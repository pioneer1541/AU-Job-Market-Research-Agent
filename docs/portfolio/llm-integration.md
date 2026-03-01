# Phase 4: LLM 集成详解

本文面向开源社区开发者，基于当前仓库实际实现说明 LLM 集成方案。核心代码位于：

- `backend/services/llm_client.py`
- `backend/services/jd_analyzer.py`
- `backend/config.py`

## 1. 概述

### 1.1 LLM 在项目中的角色

在本项目中，LLM 主要承担 **JD（职位描述）语义理解与结构化提取**：

- 输入：职位标题、公司、地点、薪资（可选）、职位描述原文
- 输出：统一的结构化字段（技能、经验级别、行业关键词、职责主题、任职资格等）
- 目标：把非结构化招聘文本转为可统计、可检索、可聚合的分析数据

`analyze_job()` 负责单条分析，`analyze_jobs_batch()` 负责批量并发分析。

### 1.2 为什么选择 OpenAI-compatible API

当前实现通过 `openai.AsyncOpenAI` + `base_url` 方式接入模型服务：

- 代码接口统一：`chat.completions.create()`
- 供应商切换成本低：保持请求格式不变，仅切换 `LLM_BASE_URL` / `LLM_MODEL`
- 对 GLM-5 这类兼容 OpenAI 协议的服务可直接复用

这也是 `backend/config.py` 中默认值 `llm_provider="openai-compatible"` 的原因。

## 2. GLM-5 集成

### 2.1 API 配置

`Settings` 默认配置如下（`backend/config.py`）：

```python
llm_provider: str = "openai-compatible"
llm_model: str = "glm-5"
llm_api_key: str = ""
llm_base_url: str = "https://api.openai.com/v1"
```

若接入 GLM-5，请将 `LLM_BASE_URL` 指向 GLM 的 OpenAI-compatible 网关地址。

### 2.2 环境变量设置

对应环境变量（大小写不敏感，项目按 `.env` 读取）：

```bash
LLM_PROVIDER=openai-compatible
LLM_MODEL=glm-5
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-glm-compatible-endpoint/v1
```

`LLM_API_KEY` 为空时，`LLMClient.__init__()` 会直接抛出 `ValueError`，避免“无密钥启动”。

### 2.3 客户端初始化代码

`LLMClient` 采用异步上下文管理，确保连接创建与关闭一致：

```python
async with LLMClient() as client:
    response = await client.complete(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        temperature=0.3,
        max_tokens=1000,
    )
```

关键点：

- `AsyncOpenAI(api_key=..., base_url=...)`
- 统一入口：`complete()`
- 支持附加参数透传：`**kwargs`

## 3. JD 分析 Prompt 设计

### 3.1 Prompt 模板结构

当前实现是“系统提示 + 用户提示”双层结构：

- `SYSTEM_PROMPT`：定义角色、字段、输出 JSON 约束
- 用户提示：注入职位元数据和 JD 正文

用户提示由 `analyze_job()` 动态拼接：

```text
请分析以下职位描述：

职位标题: {title}
公司: {company}
地点: {location}
薪资: {salary(可选)}

职位描述:
{description}

请提取结构化信息并以 JSON 格式返回。
```

### 3.2 结构化输出设计

系统提示要求输出字段（当前实现消费这些字段）：

- `hard_skills`
- `soft_skills`
- `years_of_experience`
- `industry_keywords`
- `responsibility_themes`
- `qualifications`
- `skills_required`（兼容）
- `experience_level`（Junior/Mid/Senior/Lead）
- `salary_estimate`
- `key_requirements`（兼容）
- `industry`

代码侧做了“抗脏数据”处理：

- `parse_llm_response()`：支持直接 JSON、代码块 JSON、文本中 JSON 片段
- `_normalize_string_list()`：字符串/列表统一成去重字符串列表
- `_normalize_years_of_experience()`：数值、列表、字符串统一
- `validate_experience_level()`：映射中英文变体，未知值兜底为 `Mid`

### 3.3 Few-shot 示例

**现状**：当前代码是 zero-shot（无 few-shot 示例）。

**可选扩展**：在 `SYSTEM_PROMPT` 追加 1-2 组“输入片段 -> 目标 JSON”示例，增强字段稳定性。示例（文档演示用）：

```text
示例输入：
职位标题: Python 后端工程师
职位描述: 负责 FastAPI 服务开发，要求 3 年以上经验，熟悉 PostgreSQL 和 Docker。

示例输出：
{
  "hard_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
  "soft_skills": [],
  "years_of_experience": "3年以上",
  "industry_keywords": [],
  "responsibility_themes": ["后端开发"],
  "qualifications": ["3年以上后端开发经验"],
  "skills_required": ["Python", "FastAPI", "PostgreSQL", "Docker"],
  "experience_level": "Mid",
  "salary_estimate": null,
  "key_requirements": ["3年以上后端开发经验"],
  "industry": null
}
```

## 4. 错误处理与重试

### 4.1 Rate Limit 处理

`LLMClient.complete()` 对 `RateLimitError` 使用指数退避：

- 重试次数：`max_retries`（默认 3）
- 等待时间：`retry_delay * (2 ** attempt)`（默认 1s, 2s, 4s）
- 日志：`logger.warning` 记录当前重试轮次

### 4.2 超时处理

当前代码未显式设置请求级 timeout 参数，依赖底层 SDK 默认行为。项目层面的超时相关能力主要体现在：

- 对 `APIConnectionError` 执行同样指数退避重试
- 批量任务通过分批与延迟降低长时间阻塞概率

如需更强超时控制，可在 `AsyncOpenAI` 初始化或请求参数中补充 timeout 配置。

### 4.3 降级策略

`analyze_job()` 与 `analyze_jobs_batch()` 都实现了“失败返回默认结构”：

- 任何异常都不会中断主流程
- 默认返回空技能、`experience_level="Mid"`、`salary_estimate` 回退为原 JD 薪资
- 批量模式 `asyncio.gather(..., return_exceptions=True)` 保证单条失败不拖垮整批

## 5. 批量分析优化

### 5.1 批次大小选择

`analyze_jobs_batch()` 默认 `batch_size=5`：

- 过大：触发限流概率上升
- 过小：吞吐降低
- `5` 是当前实现下在稳态与速度之间的折中默认值

### 5.2 并发控制

每批内部并发：

```python
batch_results = await asyncio.gather(
    *[analyze_job(job, client=client) for job in batch],
    return_exceptions=True,
)
```

特点：

- 复用同一个 `LLMClient` 连接上下文
- 并发度受 `batch_size` 直接控制
- 异常隔离，逐条落默认结果

### 5.3 延迟策略

批次间使用 `await asyncio.sleep(delay_between_batches)`，默认 `1.0s`：

- 作用：缓解连续突发请求，降低 429 风险
- 调参建议：按供应商 QPS/TPM 限额动态调整

## 6. 最佳实践

### 6.1 Prompt 迭代技巧

- 保持字段契约稳定：字段名不要频繁变动
- 角色与任务分离：系统提示定义规则，用户提示只放业务输入
- 低温度优先：当前 `temperature=0.3`，更利于稳定结构化输出

### 6.2 输出验证

项目已落地的验证层：

- JSON 解析兜底（多模式提取）
- 列表、年限、经验级别规范化
- 关键兼容字段回退（`skills_required`/`key_requirements`）

建议继续增强：

- 增加 schema 校验（如 Pydantic model）
- 对 `industry`、`salary_estimate` 增加格式校验与枚举约束

### 6.3 成本控制

当前代码中的成本控制实践：

- `max_tokens=1000` 限制单次输出上限
- 批处理连接复用，减少额外开销
- 失败降级而非无限重试，避免异常成本放大

建议扩展：

- 按 JD 长度做输入裁剪
- 对重复 JD 做缓存（hash 去重）
- 记录 token 使用量并建立按批次监控

---

## 附：关键调用链

1. `analyze_jobs_batch()` 分批并发调度
2. `analyze_job()` 构建 prompt 并调用 `LLMClient.complete()`
3. `parse_llm_response()` + normalize/validate 生成 `AnalysisResult`
4. 失败场景返回默认结构，保障流水线可用性
