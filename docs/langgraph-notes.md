# LangGraph 学习笔记

## 核心概念

### 1. StateGraph（状态图）
LangGraph 的核心是状态图，由节点和边组成：
- 节点（Node）：执行任务的函数
- 边（Edge）：节点之间的连接
- 状态（State）：在节点间传递的数据

### 2. Graph API vs Functional API

Graph API：
- 显式定义节点和边
- 更适合复杂工作流
- 支持条件边和循环

Functional API：
- 用装饰器定义任务
- 更接近普通 Python 代码
- 适合简单线性流程

### 3. 核心组件示例

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict, Annotated
import operator

class State(TypedDict):
    messages: Annotated[list, operator.add]
    
graph = StateGraph(State)
graph.add_node(node_name, node_function)
graph.add_edge(START, node_name)
app = graph.compile()

### 4. 多智能体模式 - Supervisor

适合我们的项目：
- Coordinator（协调器）：分析需求，分配任务
- JobFetcher（职位获取）：从多个源抓取职位  
- DataProcessor（数据处理）：清洗、标准化数据
- MarketAnalyzer（市场分析）：统计、趋势分析
- ReportGenerator（报告生成）：生成最终报告

### 5. 持久化和部署
- Checkpointer：保存状态检查点
- Memory：短期 + 长期记忆
- Human-in-the-loop：人工干预点
- 支持 LangSmith 云托管或自托管
