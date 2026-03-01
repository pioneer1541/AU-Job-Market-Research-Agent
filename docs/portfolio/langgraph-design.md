# Phase 4: LangGraph 架构设计

本文面向开源社区开发者，基于当前仓库实际实现说明 LangGraph 工作流设计。核心代码位于：

- `backend/agents/graph.py`
- `backend/agents/nodes.py`
- `backend/agents/state.py`

## 1. 概述

### 1.1 什么是 LangGraph

LangGraph 是一个用于构建可控 Agent 工作流的图编排框架。开发者可以把每个步骤建模为节点（Node），通过状态（State）在节点间传递数据，并通过条件边（Conditional Edges）实现动态路由。

在本项目中，它用于编排“职位抓取 -> 数据处理 -> 市场分析 -> 报告生成”的完整流水线。

### 1.2 为什么选择 LangGraph

当前实现选择 LangGraph 的原因主要是：

- **状态驱动**：`GraphState` 统一承载输入、中间结果、聚合结果和错误信息。
- **路由灵活**：通过 `next_action` + `supervisor_router` 支持条件跳转，而不是写死单一路径。
- **同步/异步混编**：图中同时存在同步节点和异步节点（如抓取、LLM 分析），与项目 I/O 场景匹配。
- **可扩展性好**：新增节点时只需扩展状态、注册节点并补充路由映射。

## 2. StateGraph 设计

### 2.1 状态定义（GraphState）

`backend/agents/state.py` 中的 `GraphState` 使用 `TypedDict` 定义，核心字段如下：

- 输入字段：
  - `query: str`
- 中间数据：
  - `job_listings: Annotated[list[JobListing], operator.add]`
  - `analysis_results: Annotated[list[AnalysisResult], operator.add]`
- 聚合结果：
  - `processed_data: dict`
  - `market_insights: dict`
  - `report: str`
- 错误处理：
  - `errors: Annotated[list[str], operator.add]`
- 控制流：
  - `next_action: str`

其中 `Annotated[..., operator.add]` 表示该字段在多节点更新时采用“列表追加”语义，适合累积 `job_listings`、`analysis_results` 和 `errors`。

### 2.2 节点定义

图中注册了 5 个业务节点（`backend/agents/graph.py`）：

- `coordinator`
- `fetch_jobs`
- `process_data`
- `analyze`
- `generate_report`

对应实现分别在 `backend/agents/nodes.py` 中：

- `coordinator_node`
- `job_fetcher_node`（异步）
- `data_processor_node`
- `market_analyzer_node`（异步）
- `report_generator_node`

### 2.3 边与路由

入口和路由机制如下：

- 固定入口：`START -> coordinator`
- 节点间跳转：每个节点都通过 `add_conditional_edges(..., supervisor_router, route_map)` 做条件路由
- 终止条件：当路由返回 `"END"` 时进入 LangGraph 的 `END`

当前 `route_map` 支持以下动作：

- `"fetch_jobs"`
- `"process_data"`
- `"analyze"`
- `"generate_report"`
- `"END"`

`supervisor_router` 的实现很轻量：读取 `state["next_action"]`，映射到目标节点，不在映射中的值默认回落到 `"END"`。

## 3. 节点详解

### 3.1 coordinator_node: 协调器

职责：

- 作为图入口读取 `query`
- 决定下一步动作

当前实现状态：

- 暂未接入 LLM 做 query 拆解（代码中保留 TODO）
- 直接返回 `{"next_action": "fetch_jobs"}`，即默认先抓取职位

### 3.2 job_fetcher_node: 职位获取

职责：

- 解析查询（当前按 `" in "` 粗分职位关键词与地点）
- 通过 `ApifyClient.run_seek_scraper()` 抓取职位
- 将原始数据转换为统一 `JobListing`
- 基于 `job["id"]` 去重

实现要点：

- 原生异步节点（`async def`）
- 出错时将错误追加到 `errors`
- 若抓取到有效职位：`next_action = "process_data"`
- 若无职位：`next_action = "END"`

### 3.3 data_processor_node: 数据处理

职责：

- 对职位数据做预处理，当前重点是薪资过滤与样本概览统计

实现要点：

- 调用 `statistics_service.filter_low_salary_jobs(jobs)` 过滤低薪岗位
- 调用 `compute_sample_overview(filtered_jobs, [])` 生成样本统计
- 组装 `processed_data`，包含：
  - `salary_filter_stats`
  - `filtered_job_listings`
  - `pipeline_stage = "process_data"`
- 设置 `next_action = "analyze"`

### 3.4 market_analyzer_node: 市场分析

职责：

- 对职位描述做批量语义分析
- 聚合市场洞察指标

实现要点：

- 原生异步节点（`async def`）
- 优先使用 `processed_data.filtered_job_listings` 作为分析输入；不存在时回退到 `job_listings`
- 调用 `analyze_jobs_batch(jobs, batch_size=5)` 生成 `analysis_results`
- 调用 `StatisticsService().generate_market_insights(jobs, analysis_results)` 生成 `market_insights`
- 异常写入 `errors`，流程继续
- 设置 `next_action = "generate_report"`

### 3.5 report_generator_node: 报告生成

职责：

- 汇总前序阶段结果并生成最终文本报告

实现要点：

- 调用 `report_service.generate(...)`
- 写入：
  - `report`
  - `processed_data.report_meta`
  - `processed_data.report_sections`
- 设置 `next_action = "END"`

## 4. 数据流转

### 4.1 状态更新机制

当前图遵循“节点返回局部更新字典，框架合并到全局状态”的方式：

1. 输入至少提供 `query`（测试入口中也初始化了空列表字段）
2. `coordinator` 只更新控制字段 `next_action`
3. `fetch_jobs` 写入 `job_listings/errors/next_action`
4. `process_data` 写入 `processed_data/next_action`
5. `analyze` 写入 `analysis_results/market_insights/errors/next_action`
6. `generate_report` 写入 `report/processed_data/next_action`

由于 `errors`、`job_listings`、`analysis_results` 使用追加语义，适合在多节点连续累计。

### 4.2 错误处理

当前实现的错误策略是“记录错误 + 尽量不中断”：

- `job_fetcher_node`：
  - 捕获 `ApifyError` 与通用异常
  - 将错误消息写入 `errors`
  - 若无可用职位则提前结束
- `market_analyzer_node`：
  - 捕获分析异常并追加到 `errors`
  - 仍继续生成 `market_insights`（可能基于空或部分分析结果）
- `report_generator_node`：
  - 将 `errors` 作为输入之一，保证报告层可感知上游异常

这使得流水线在外部依赖不稳定（抓取源、LLM）时仍能产出可解释结果。

## 5. 扩展指南

### 5.1 如何添加新节点

以新增 `salary_benchmark_node` 为例，推荐步骤：

1. 在 `backend/agents/nodes.py` 实现新函数，输入 `GraphState`，返回局部状态更新（含 `next_action`）。
2. 在 `backend/agents/graph.py` 的 `create_job_research_graph()` 中 `add_node(...)` 注册。
3. 在条件路由 `route_map` 中加入新动作（如 `"salary_benchmark"`）。
4. 更新 `supervisor_router` 的 `Literal` 和 `action_map`。
5. 在前置节点中把 `next_action` 指向新节点，或由 `coordinator` 动态分流。

### 5.2 如何修改状态

推荐遵循以下约束：

1. 在 `backend/agents/state.py` 的 `GraphState` 明确定义新字段类型。
2. 若字段需要跨节点累积（列表拼接），使用 `Annotated[..., operator.add]`。
3. 确保写入该字段的节点返回值与类型一致，避免“字段形态漂移”。
4. 如字段参与路由决策，更新 `supervisor_router` 与相关节点分支逻辑。

最小实践建议：

- 对新增字段先在一个节点写入、一个节点消费，确保链路可验证；
- 再逐步扩展到多节点共享，避免一次性引入过多状态耦合。
