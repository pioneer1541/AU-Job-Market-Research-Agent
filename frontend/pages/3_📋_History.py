import sys
from typing import Any, Dict, List

import streamlit as st

sys.path.insert(0, '.')
from utils.api import APIClient, APIError, get_default_api_url
from utils.helpers import format_date

st.set_page_config(page_title="历史记录", page_icon="📋", layout="wide")

st.title("📋 历史报告")
st.markdown("查看已持久化保存到 SQLite 的市场分析报告")

if "api_url" not in st.session_state:
    st.session_state["api_url"] = get_default_api_url()

with st.sidebar:
    st.header("⚙️ 配置")
    api_url = st.text_input("API 地址", value=st.session_state["api_url"], key="history_api_url")
    st.session_state["api_url"] = (api_url or get_default_api_url()).rstrip("/")


def _load_reports(limit: int) -> Dict[str, Any]:
    """从后端加载历史报告列表。"""
    client = APIClient(st.session_state["api_url"])
    return client.list_reports(limit=limit, offset=0)


def _view_report(report_id: str) -> None:
    """加载报告详情并跳转到分析详情页。"""
    client = APIClient(st.session_state["api_url"])
    detail = client.get_report_detail(report_id)

    st.session_state["market_analysis_result"] = {
        "market_insights": detail.get("market_insights", {}),
        "jobs": detail.get("jobs", []),
        "report": detail.get("report", ""),
        "meta": detail.get("meta", {}),
    }
    st.session_state["analysis_defaults"] = {
        "query": detail.get("query", ""),
        "location": detail.get("location", ""),
        "max_results": int(detail.get("max_results", 20)),
    }

    try:
        st.switch_page("pages/2_📊_Market_Analysis.py")
    except Exception:
        st.success("报告详情已载入，请前往“市场分析”页面查看。")


col1, col2 = st.columns([2, 1])
with col1:
    keyword = st.text_input("筛选关键词", placeholder="输入关键词")
with col2:
    limit = st.selectbox("加载数量", [10, 20, 50, 100], index=2)

try:
    data = _load_reports(limit=int(limit))
except APIError as exc:
    st.error(f"加载历史报告失败：{exc}")
    st.stop()
except Exception as exc:
    st.error(f"加载历史报告失败：{exc}")
    st.stop()

reports: List[Dict[str, Any]] = data.get("reports", []) if isinstance(data, dict) else []
total = int(data.get("total", len(reports))) if isinstance(data, dict) else len(reports)

if keyword.strip():
    key = keyword.strip().lower()
    reports = [
        item for item in reports
        if key in str(item.get("query", "")).lower() or key in str(item.get("location", "")).lower()
    ]

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("已保存报告", total)
with m2:
    st.metric("当前展示", len(reports))
with m3:
    st.metric("数据库", "SQLite")

st.divider()

if not reports:
    st.info("暂无已保存报告，请先在“市场分析”页面生成报告。")
    st.stop()

for report in reports:
    with st.container():
        a, b, c = st.columns([4, 2, 2])
        with a:
            st.markdown(f"📊 **{report.get('query', '未命名报告')}**")
            location = str(report.get("location", "")).strip()
            st.caption(f"📍 {location if location else '不限'}")
            st.caption(f"报告ID: {report.get('id', '')}")

        with b:
            st.caption(f"📅 {format_date(str(report.get('created_at', '')))}")
            st.caption(f"样本上限: {int(report.get('max_results', 20))}")

        with c:
            st.metric("职位数", int(report.get("results_count", 0)))
            if st.button("查看详情", key=f"view_{report.get('id', '')}", use_container_width=True):
                try:
                    _view_report(str(report.get("id", "")))
                except APIError as exc:
                    st.error(f"读取报告详情失败：{exc}")
                except Exception as exc:
                    st.error(f"读取报告详情失败：{exc}")

        st.divider()
