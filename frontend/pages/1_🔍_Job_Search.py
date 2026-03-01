import streamlit as st
from typing import Dict, Any, List
import sys

sys.path.insert(0, '.')
from components.job_card import render_job_card, render_job_detail
from utils.api import APIClient, APIError, get_default_api_url

st.set_page_config(page_title="职位搜索", page_icon="🔍", layout="wide")

st.title("🔍 职位搜索")
st.markdown("搜索并浏览职位信息")


def _normalize_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """适配后端字段到前端展示结构。"""
    normalized = dict(job)
    normalized.setdefault("job_type", "未知类型")
    if normalized.get("salary") and not normalized.get("salary_range"):
        normalized["salary_range"] = None
    return normalized


if "api_url" not in st.session_state:
    st.session_state["api_url"] = get_default_api_url()

with st.sidebar:
    st.header("⚙️ 配置")
    api_url = st.text_input("API 地址", value=st.session_state["api_url"], key="job_search_api_url")
    st.session_state["api_url"] = (api_url or get_default_api_url()).rstrip("/")
    st.caption("优先使用侧边栏配置；未配置时读取环境变量 `JOB_MARKET_API_URL` 或 `API_BASE_URL`。")

if "search_result" not in st.session_state:
    st.session_state["search_result"] = {"jobs": [], "total": 0, "query": ""}

if "selected_job" not in st.session_state:
    st.session_state["selected_job"] = None

# 搜索表单
with st.form("search_form"):
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        query = st.text_input("职位关键词", placeholder="例如: Python 开发")
    with col2:
        location = st.text_input("地点", placeholder="例如: 墨尔本")
    with col3:
        max_results = st.number_input("结果数量", min_value=5, max_value=50, value=20)

    submitted = st.form_submit_button("搜索", type="primary")

if submitted:
    if not query.strip():
        st.warning("请输入职位关键词后再搜索。")
    else:
        client = APIClient(st.session_state["api_url"])
        with st.spinner("正在搜索职位，请稍候..."):
            try:
                result = client.search_jobs(
                    query=query.strip(),
                    location=location.strip() or None,
                    max_results=int(max_results),
                )
                jobs = result.get("jobs", [])
                if not isinstance(jobs, list):
                    raise APIError("返回数据格式错误：`jobs` 字段不是列表。")
                st.session_state["search_result"] = {
                    "jobs": [_normalize_job(job) for job in jobs],
                    "total": result.get("total", len(jobs)),
                    "query": result.get("query", query.strip()),
                }
                st.session_state["selected_job"] = None
            except APIError as exc:
                st.error(f"搜索失败：{exc}")
            except Exception as exc:
                st.error(f"发生未知错误：{exc}")

search_result = st.session_state["search_result"]
jobs: List[Dict[str, Any]] = search_result.get("jobs", [])
search_query = search_result.get("query", "")

if search_query:
    st.subheader(f"搜索结果: {search_query}")
    st.write(f"找到 {search_result.get('total', len(jobs))} 个职位")

if jobs:
    for idx, job in enumerate(jobs):
        render_job_card(job, idx)
        if st.button("查看详情", key=f"detail_{job.get('id', idx)}"):
            st.session_state["selected_job"] = idx

    if st.session_state["selected_job"] is not None:
        selected_idx = st.session_state["selected_job"]
        if 0 <= selected_idx < len(jobs):
            with st.expander("职位详情", expanded=True):
                render_job_detail(jobs[selected_idx])
elif search_query:
    st.info("未找到匹配职位，请尝试更换关键词或地点。")

else:
    st.subheader("开始搜索")
    st.info("输入关键词并点击“搜索”后显示真实职位结果。")
