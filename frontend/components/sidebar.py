import streamlit as st
from typing import Optional

def render_sidebar() -> dict:
    """渲染侧边栏配置"""
    with st.sidebar:
        st.header("⚙️ 配置")
        api_url = st.text_input("API 地址", value="http://localhost:8000")
        
        st.divider()
        
        st.header("📊 显示设置")
        results_per_page = st.slider("每页结果数", 5, 50, 20)
        
        st.divider()
        
        st.header("ℹ️ 关于")
        st.markdown("""
        **Job Market Research Agent**
        
        AI 驱动的职位市场研究工具
        
        - 🔍 职位搜索
        - 📊 市场分析
        - 📋 历史记录
        """)
    
    return {
        "api_url": api_url,
        "results_per_page": results_per_page
    }
