import streamlit as st
from typing import List, Dict, Any
import sys

sys.path.insert(0, '.')
from utils.helpers import format_date

st.set_page_config(page_title="历史记录", page_icon="📋", layout="wide")

st.title("📋 历史记录")
st.markdown("查看过往的搜索与分析记录")

if "search_history" not in st.session_state:
    st.session_state["search_history"] = []
if "analysis_history" not in st.session_state:
    st.session_state["analysis_history"] = []

search_history: List[Dict[str, Any]] = st.session_state.get("search_history", [])
analysis_history: List[Dict[str, Any]] = st.session_state.get("analysis_history", [])

all_history = sorted(
    [*search_history, *analysis_history],
    key=lambda x: x.get("timestamp", ""),
    reverse=True,
)

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("搜索历史", len(search_history))
with col_b:
    st.metric("分析历史", len(analysis_history))
with col_c:
    st.metric("总记录", len(all_history))

st.divider()

# 筛选选项
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    search_filter = st.text_input("筛选关键词", placeholder="输入关键词")
with col2:
    type_filter = st.selectbox("类型", ["全部", "搜索", "分析"])
with col3:
    limit = st.selectbox("显示数量", [10, 20, 50, 100], index=1)

filtered_history = all_history.copy()
if search_filter:
    keyword = search_filter.lower().strip()
    filtered_history = [
        h for h in filtered_history
        if keyword in (h.get("query", "").lower())
    ]
if type_filter != "全部":
    type_map = {"搜索": "search", "分析": "analysis"}
    filtered_history = [h for h in filtered_history if h.get("type") == type_map[type_filter]]

filtered_history = filtered_history[:limit]
st.write(f"共 {len(filtered_history)} 条记录")


def _rerun_record(record: Dict[str, Any]) -> None:
    if record.get("type") == "search":
        st.session_state["pending_search"] = {
            "query": record.get("query", ""),
            "location": record.get("location", ""),
            "max_results": record.get("max_results", 20),
        }
        try:
            st.switch_page("pages/1_🔍_Job_Search.py")
        except Exception:
            st.success("参数已载入，请前往“职位搜索”页面继续。")
    else:
        st.session_state["pending_analysis"] = {
            "query": record.get("query", ""),
            "location": record.get("location", ""),
            "max_results": record.get("max_results", 20),
        }
        try:
            st.switch_page("pages/2_📊_Market_Analysis.py")
        except Exception:
            st.success("参数已载入，请前往“市场分析”页面继续。")


def _delete_record(record_id: str) -> None:
    st.session_state["search_history"] = [
        item for item in st.session_state.get("search_history", [])
        if item.get("id") != record_id
    ]
    st.session_state["analysis_history"] = [
        item for item in st.session_state.get("analysis_history", [])
        if item.get("id") != record_id
    ]
    st.success("记录已删除。")
    st.rerun()


if not filtered_history:
    st.markdown(
        (
            "<div style='padding: 1.2rem; border-radius: 0.5rem; border: 1px dashed #cbd5e1;"
            "background: #f8fafc;'>"
            "<h4 style='margin:0;'>📭 暂无历史记录</h4>"
            "<p style='margin:0.4rem 0 0 0; color:#475569;'>"
            "先在“职位搜索”或“市场分析”页面执行一次操作，记录会自动保存在当前会话中。"
            "</p></div>"
        ),
        unsafe_allow_html=True,
    )
else:
    for record in filtered_history:
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])

            with col1:
                item_type = record.get("type", "search")
                icon = "🔍" if item_type == "search" else "📊"
                type_name = "搜索" if item_type == "search" else "分析"
                st.markdown(f"{icon} **{record.get('query', '未命名记录')}**")
                if record.get("location"):
                    st.caption(f"📍 {record.get('location')}")
                st.caption(f"类型: {type_name}")

            with col2:
                st.caption(f"📅 {format_date(record.get('timestamp', ''))}")
                st.caption(f"最大结果数: {record.get('max_results', 20)}")

            with col3:
                st.metric("结果数", int(record.get("results_count", 0)))

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                action_label = "重新搜索" if record.get("type") == "search" else "重新分析"
                if st.button(action_label, key=f"rerun_{record.get('id')}"):
                    _rerun_record(record)
            with btn_col2:
                if st.button("删除", key=f"delete_{record.get('id')}"):
                    _delete_record(record.get("id", ""))

            st.divider()

st.subheader("管理历史记录")
if st.button("清空全部历史", type="secondary"):
    st.session_state["search_history"] = []
    st.session_state["analysis_history"] = []
    st.success("已清空全部历史记录。")
    st.rerun()
