import streamlit as st
import sys
import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, '.')
from components.charts import create_salary_chart, create_location_chart, create_skills_chart
from utils.api import APIClient, APIError, get_default_api_url

st.set_page_config(page_title="市场分析", page_icon="📊", layout="wide")

st.title("📊 市场分析")
st.markdown("分析职位市场趋势和数据")


def parse_salary_to_range(salary_text: str) -> Dict[str, Any]:
    """将后端字符串薪资解析为图表可用结构。"""
    if not salary_text:
        return {}
    numbers = re.findall(r"\d[\d,]*", salary_text)
    values = [int(item.replace(",", "")) for item in numbers if item]
    if not values:
        return {}
    if len(values) == 1:
        return {"min": values[0], "max": values[0], "currency": "AUD", "period": "year"}
    return {"min": values[0], "max": values[1], "currency": "AUD", "period": "year"}


def normalize_jobs_for_chart(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for job in jobs:
        item = dict(job)
        if not item.get("salary_range") and item.get("salary"):
            item["salary_range"] = parse_salary_to_range(item.get("salary", ""))
        normalized.append(item)
    return normalized


def _render_error(message: str) -> None:
    st.markdown(
        (
            "<div style='padding: 0.75rem 1rem; border-radius: 0.5rem;"
            "border: 1px solid #f5c2c7; background: #f8d7da; color: #842029; margin: 0.5rem 0;'>"
            f"<strong>分析失败：</strong>{message}</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_empty_state(title: str, description: str) -> None:
    st.markdown(
        (
            "<div style='padding: 1.2rem; border-radius: 0.5rem; border: 1px dashed #bae6fd;"
            "background: #f8fafc; margin-top: 0.8rem;'>"
            f"<h4 style='margin:0;'>📭 {title}</h4>"
            f"<p style='margin:0.4rem 0 0 0; color:#475569;'>{description}</p>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _append_analysis_history(
    query: str,
    location: Optional[str],
    max_results: int,
    result: Dict[str, Any],
) -> None:
    market_insights = result.get("market_insights", {}) or {}
    history = st.session_state.setdefault("analysis_history", [])
    history.insert(
        0,
        {
            "id": f"a-{uuid.uuid4().hex[:10]}",
            "type": "analysis",
            "query": query,
            "location": location or "",
            "max_results": max_results,
            "results_count": market_insights.get("total_jobs", len(result.get("jobs", []))),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        },
    )
    st.session_state["analysis_history"] = history[:100]


def _execute_analysis(query: str, location: Optional[str], max_results: int) -> None:
    client = APIClient(st.session_state["api_url"])
    progress = st.progress(0, text="准备分析任务...")

    try:
        progress.progress(20, text="正在请求市场数据...")
        time.sleep(0.1)
        result = client.analyze_market(
            query=query,
            location=location,
            max_results=max_results,
        )
        progress.progress(75, text="正在生成可视化数据...")
        time.sleep(0.1)
        st.session_state["market_analysis_result"] = result
        _append_analysis_history(
            query=query,
            location=location,
            max_results=max_results,
            result=result,
        )
        progress.progress(100, text="分析完成")
        st.success("分析完成，已写入历史记录。")
    except APIError as exc:
        _render_error(str(exc))
    except Exception as exc:
        _render_error(f"发生未知错误：{exc}")
    finally:
        time.sleep(0.05)
        progress.empty()


if "api_url" not in st.session_state:
    st.session_state["api_url"] = get_default_api_url()

if "market_analysis_result" not in st.session_state:
    st.session_state["market_analysis_result"] = None

if "analysis_history" not in st.session_state:
    st.session_state["analysis_history"] = []

with st.sidebar:
    st.header("⚙️ 配置")
    api_url = st.text_input("API 地址", value=st.session_state["api_url"], key="market_api_url")
    st.session_state["api_url"] = (api_url or get_default_api_url()).rstrip("/")
    st.caption("优先使用侧边栏配置；未配置时读取环境变量 `BACKEND_URL`、`JOB_MARKET_API_URL` 或 `API_BASE_URL`。")

# 处理历史页触发的重跑
pending_analysis = st.session_state.pop("pending_analysis", None)
if pending_analysis:
    st.info("已从历史记录载入参数，正在重新分析...")
    _execute_analysis(
        query=pending_analysis.get("query", "").strip(),
        location=(pending_analysis.get("location") or "").strip() or None,
        max_results=int(pending_analysis.get("max_results", 20)),
    )

# 分析表单
col1, col2, col3 = st.columns([3, 2, 1])
with col1:
    analysis_query = st.text_input("分析关键词", placeholder="例如: Python 开发")
with col2:
    analysis_location = st.text_input("地点筛选", placeholder="例如: 墨尔本")
with col3:
    analysis_max_results = st.number_input("结果数量", min_value=5, max_value=50, value=20)

if st.button("生成分析", type="primary"):
    if not analysis_query.strip():
        st.warning("请输入分析关键词后再生成。")
    else:
        _execute_analysis(
            query=analysis_query.strip(),
            location=analysis_location.strip() or None,
            max_results=int(analysis_max_results),
        )

result = st.session_state.get("market_analysis_result")

if not result:
    _render_empty_state("暂无分析结果", "输入关键词并点击“生成分析”后展示图表与市场洞察。")
    st.stop()

market_insights: Dict[str, Any] = result.get("market_insights", {})
jobs: List[Dict[str, Any]] = result.get("jobs", [])
report: str = result.get("report", "")
jobs_for_chart = normalize_jobs_for_chart(jobs)
skills_list: List[str] = market_insights.get("top_skills", []) or []
skills_data = {
    skill: len(skills_list) - idx
    for idx, skill in enumerate(skills_list)
}

# 显示市场概览
st.subheader("市场概览")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("职位总数", f"{market_insights.get('total_jobs', len(jobs)):,}")
with col2:
    st.metric("平均薪资范围", market_insights.get("avg_salary_range") or "暂无数据")
with col3:
    st.metric("热门技能数", len(skills_list))
with col4:
    st.metric("样本职位数", len(jobs))

st.divider()

# 图表区域
col1, col2 = st.columns(2)

with col1:
    st.subheader("薪资分布")
    fig_salary = create_salary_chart(jobs_for_chart)
    st.plotly_chart(fig_salary, use_container_width=True)

with col2:
    st.subheader("地点分布")
    fig_location = create_location_chart(jobs_for_chart)
    st.plotly_chart(fig_location, use_container_width=True)

st.subheader("热门技能需求")
fig_skills = create_skills_chart(skills_data)
st.plotly_chart(fig_skills, use_container_width=True)

st.subheader("经验分布")
experience_distribution = market_insights.get("experience_distribution", {})
if experience_distribution:
    st.bar_chart(experience_distribution)
else:
    st.info("暂无经验分布数据。")

st.subheader("地点分布（统计）")
location_distribution = market_insights.get("location_distribution", {})
if location_distribution:
    st.bar_chart(location_distribution)
else:
    st.info("暂无地点分布统计。")

if report:
    with st.expander("查看分析报告", expanded=False):
        st.markdown(report)
