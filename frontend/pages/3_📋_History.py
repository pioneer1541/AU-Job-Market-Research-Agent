import streamlit as st
from datetime import datetime
from typing import List, Dict, Any
import sys
sys.path.insert(0, '.')
from utils.helpers import format_date

# Mock 历史记录
MOCK_HISTORY = [
    {
        "id": "h1",
        "type": "search",
        "query": "Python 开发",
        "location": "墨尔本",
        "timestamp": "2024-01-15T10:30:00",
        "results_count": 25
    },
    {
        "id": "h2",
        "type": "analysis",
        "query": "前端开发 市场趋势",
        "location": "悉尼",
        "timestamp": "2024-01-14T14:20:00",
        "results_count": 1
    },
    {
        "id": "h3",
        "type": "search",
        "query": "数据科学家",
        "location": "",
        "timestamp": "2024-01-13T09:15:00",
        "results_count": 18
    },
    {
        "id": "h4",
        "type": "search",
        "query": "DevOps",
        "location": "布里斯班",
        "timestamp": "2024-01-12T16:45:00",
        "results_count": 12
    },
    {
        "id": "h5",
        "type": "analysis",
        "query": "AI/ML 职位市场",
        "location": "墨尔本",
        "timestamp": "2024-01-11T11:00:00",
        "results_count": 1
    }
]

st.set_page_config(page_title="历史记录", page_icon="📋", layout="wide")

st.title("📋 历史记录")
st.markdown("查看过往的研究记录")

# 筛选选项
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    search_filter = st.text_input("搜索记录", placeholder="输入关键词")
with col2:
    type_filter = st.selectbox("类型", ["全部", "搜索", "分析"])
with col3:
    limit = st.selectbox("显示数量", [10, 20, 50, 100], index=1)

# 筛选逻辑
filtered_history = MOCK_HISTORY.copy()
if search_filter:
    filtered_history = [h for h in filtered_history if search_filter.lower() in h["query"].lower()]
if type_filter != "全部":
    type_map = {"搜索": "search", "分析": "analysis"}
    filtered_history = [h for h in filtered_history if h["type"] == type_map[type_filter]]

st.write(f"共 {len(filtered_history)} 条记录")

# 显示历史记录
for record in filtered_history:
    with st.container():
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col1:
            icon = "🔍" if record["type"] == "search" else "📊"
            type_name = "搜索" if record["type"] == "search" else "分析"
            st.markdown(f"{icon} **{record['query']}**")
            if record["location"]:
                st.caption(f"📍 {record['location']}")
        
        with col2:
            st.caption(f"📅 {format_date(record['timestamp'])}")
            st.caption(f"类型: {type_name}")
        
        with col3:
            st.metric("结果数", record["results_count"])
        
        # 操作按钮
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("重新搜索", key=f"rerun_{record['id']}"):
                st.info(f"重新搜索: {record['query']}")
        with btn_col2:
            if st.button("删除", key=f"delete_{record['id']}"):
                st.warning(f"已删除记录: {record['id']}")
        
        st.divider()

# 清空历史
st.subheader("管理历史记录")
col1, col2 = st.columns(2)
with col1:
    if st.button("清空所有记录", type="secondary"):
        st.warning("确认要清空所有历史记录吗？")
with col2:
    if st.button("导出记录"):
        st.info("导出功能开发中...")
