import streamlit as st
from typing import Dict, Any, List, Optional
from datetime import datetime
import time
import uuid
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


def _render_error(message: str) -> None:
    st.markdown(
        (
            "<div style='padding: 0.75rem 1rem; border-radius: 0.5rem;"
            "border: 1px solid #f5c2c7; background: #f8d7da; color: #842029; margin: 0.5rem 0;'>"
            f"<strong>操作失败：</strong>{message}</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_empty_state(title: str, description: str) -> None:
    st.markdown(
        (
            "<div style='padding: 1.2rem; border-radius: 0.5rem; border: 1px dashed #c7d2fe;"
            "background: #f8fafc; margin-top: 0.8rem;'>"
            f"<h4 style='margin:0;'>📭 {title}</h4>"
            f"<p style='margin:0.4rem 0 0 0; color:#475569;'>{description}</p>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _append_search_history(
    query: str,
    location: Optional[str],
    max_results: int,
    total: int,
) -> None:
    history = st.session_state.setdefault("search_history", [])
    history.insert(
        0,
        {
            "id": f"s-{uuid.uuid4().hex[:10]}",
            "type": "search",
            "query": query,
            "location": location or "",
            "max_results": max_results,
            "results_count": total,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        },
    )
    st.session_state["search_history"] = history[:100]


def _execute_search(query: str, location: Optional[str], max_results: int) -> None:
    client = APIClient(st.session_state["api_url"])
    progress = st.progress(0, text="准备搜索任务...")

    try:
        progress.progress(20, text="正在连接后端服务...")
        time.sleep(0.1)
        progress.progress(50, text="正在拉取职位数据...")
        result = client.search_jobs(query=query, location=location, max_results=max_results)
        progress.progress(80, text="正在整理结果...")
        time.sleep(0.1)

        jobs = result.get("jobs", [])
        if not isinstance(jobs, list):
            raise APIError("返回数据格式错误：`jobs` 字段不是列表。")

        st.session_state["search_result"] = {
            "jobs": [_normalize_job(job) for job in jobs],
            "total": result.get("total", len(jobs)),
            "query": result.get("query", query),
        }
        st.session_state["selected_job"] = None
        _append_search_history(
            query=query,
            location=location,
            max_results=max_results,
            total=st.session_state["search_result"]["total"],
        )

        progress.progress(100, text="搜索完成")
        st.success("搜索完成，已更新结果和历史记录。")
    except APIError as exc:
        _render_error(str(exc))
    except Exception as exc:
        _render_error(f"发生未知错误：{exc}")
    finally:
        time.sleep(0.05)
        progress.empty()


if "api_url" not in st.session_state:
    st.session_state["api_url"] = get_default_api_url()

if "search_result" not in st.session_state:
    st.session_state["search_result"] = {"jobs": [], "total": 0, "query": ""}

if "selected_job" not in st.session_state:
    st.session_state["selected_job"] = None

if "search_history" not in st.session_state:
    st.session_state["search_history"] = []

with st.sidebar:
    st.header("⚙️ 配置")
    api_url = st.text_input("API 地址", value=st.session_state["api_url"], key="job_search_api_url")
    st.session_state["api_url"] = (api_url or get_default_api_url()).rstrip("/")
    st.caption("优先使用侧边栏配置；未配置时读取环境变量 `BACKEND_URL`、`JOB_MARKET_API_URL` 或 `API_BASE_URL`。")

# 处理历史页触发的重跑
pending_search = st.session_state.pop("pending_search", None)
if pending_search:
    st.info("已从历史记录载入参数，正在重新搜索...")
    _execute_search(
        query=pending_search.get("query", "").strip(),
        location=(pending_search.get("location") or "").strip() or None,
        max_results=int(pending_search.get("max_results", 20)),
    )

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
        _execute_search(
            query=query.strip(),
            location=location.strip() or None,
            max_results=int(max_results),
        )

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
    _render_empty_state("未找到匹配职位", "请尝试更换关键词、地点，或扩大结果数量。")
else:
    _render_empty_state("开始搜索", "输入关键词并点击“搜索”后显示职位结果。")
