import streamlit as st
from typing import Dict, Any
from utils.helpers import format_salary, format_date

def render_job_card(job: Dict[str, Any], index: int = 0):
    """渲染职位卡片"""
    with st.container():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # 标题和公司
            st.markdown(f"### {job.get('title', '未知职位')}")
            st.markdown(f"**{job.get('company', '未知公司')}**")
            
            # 地点和类型
            location = job.get('location', '未知地点')
            job_type = job.get('job_type', '未知类型')
            st.markdown(f"📍 {location} | 📋 {job_type}")
            
            # 薪资
            salary = job.get("salary") or format_salary(job.get('salary_range'))
            st.markdown(f"💰 {salary}")
            
            # 描述摘要
            description = job.get('description', '')
            if len(description) > 200:
                description = description[:200] + "..."
            st.markdown(f"{description}")
            
            # 技能标签
            skills = job.get('skills', [])
            if skills:
                st.markdown("**技能要求:** " + " | ".join(skills[:5]))
        
        with col2:
            # 发布日期
            posted = job.get('posted_date', '')
            if posted:
                st.caption(f"📅 {format_date(posted)}")
            
            # 来源
            source = job.get('source', '')
            if source:
                st.caption(f"🔗 {source}")
        
        st.divider()

def render_job_detail(job: Dict[str, Any]):
    """渲染职位详情"""
    st.markdown(f"## {job.get('title', '未知职位')}")
    st.markdown(f"**公司:** {job.get('company', '未知公司')}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("地点", job.get('location', '未知'))
    with col2:
        st.metric("类型", job.get('job_type', '未知'))
    with col3:
        st.metric("薪资", job.get("salary") or format_salary(job.get('salary_range')))
    
    st.markdown("### 职位描述")
    st.markdown(job.get('description', '暂无描述'))
    
    skills = job.get('skills', [])
    if skills:
        st.markdown("### 技能要求")
        st.markdown(" | ".join(skills))
    
    # 链接
    url = job.get('url', '')
    if url:
        st.markdown(f"[查看原始职位]({url})")
