import streamlit as st
from typing import List, Dict, Any
import sys
sys.path.insert(0, '.')
from components.job_card import render_job_card, render_job_detail
from utils.helpers import format_salary

# Mock 数据用于测试
MOCK_JOBS = [
    {
        "id": "1",
        "title": "高级 Python 开发工程师",
        "company": "TechCorp Pty Ltd",
        "location": "墨尔本",
        "job_type": "全职",
        "salary_range": {"min": 120000, "max": 150000, "currency": "AUD", "period": "year"},
        "description": "我们正在寻找一位经验丰富的 Python 开发工程师，负责设计和开发高性能的后端服务。需要熟练掌握 Python、Django/FastAPI，有分布式系统经验优先。",
        "skills": ["Python", "Django", "FastAPI", "PostgreSQL", "Docker", "AWS"],
        "posted_date": "2024-01-15",
        "source": "Seek"
    },
    {
        "id": "2",
        "title": "前端开发工程师",
        "company": "Digital Solutions",
        "location": "悉尼",
        "job_type": "全职",
        "salary_range": {"min": 90000, "max": 120000, "currency": "AUD", "period": "year"},
        "description": "寻找一位熟练的前端开发工程师，精通 React 和 TypeScript。负责构建响应式 Web 应用，优化用户体验。",
        "skills": ["React", "TypeScript", "CSS", "HTML", "Git"],
        "posted_date": "2024-01-14",
        "source": "Indeed"
    },
    {
        "id": "3",
        "title": "数据科学家",
        "company": "Data Insights Co",
        "location": "墨尔本",
        "job_type": "全职",
        "salary_range": {"min": 130000, "max": 160000, "currency": "AUD", "period": "year"},
        "description": "数据科学家职位，负责构建机器学习模型，进行数据分析和可视化。需要 Python、SQL 和机器学习经验。",
        "skills": ["Python", "Machine Learning", "SQL", "TensorFlow", "Pandas"],
        "posted_date": "2024-01-13",
        "source": "LinkedIn"
    },
    {
        "id": "4",
        "title": "DevOps 工程师",
        "company": "CloudTech Solutions",
        "location": "布里斯班",
        "job_type": "全职",
        "salary_range": {"min": 110000, "max": 140000, "currency": "AUD", "period": "year"},
        "description": "负责 CI/CD 流程、云基础设施管理和自动化部署。熟悉 AWS、Kubernetes 和 Terraform。",
        "skills": ["AWS", "Kubernetes", "Docker", "Terraform", "CI/CD"],
        "posted_date": "2024-01-12",
        "source": "Seek"
    },
    {
        "id": "5",
        "title": "产品经理",
        "company": "InnovateTech",
        "location": "墨尔本",
        "job_type": "全职",
        "salary_range": {"min": 100000, "max": 130000, "currency": "AUD", "period": "year"},
        "description": "产品经理职位，负责产品战略规划、需求分析和项目管理。需要良好的沟通能力和敏捷开发经验。",
        "skills": ["Product Strategy", "Agile", "User Research", "Data Analysis"],
        "posted_date": "2024-01-11",
        "source": "Indeed"
    }
]

st.set_page_config(page_title="职位搜索", page_icon="🔍", layout="wide")

st.title("🔍 职位搜索")
st.markdown("搜索并浏览职位信息")

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

# 显示结果
if submitted and query:
    st.subheader(f"搜索结果: {query}")
    
    # 使用 mock 数据（实际应该调用 API）
    # 这里简单过滤 mock 数据
    filtered_jobs = [job for job in MOCK_JOBS if query.lower() in job["title"].lower()]
    if location:
        filtered_jobs = [job for job in filtered_jobs if location in job["location"]]
    
    if not filtered_jobs:
        filtered_jobs = MOCK_JOBS  # 如果没有匹配，显示所有 mock 数据
    
    st.write(f"找到 {len(filtered_jobs)} 个职位")
    
    # 显示职位列表
    for i, job in enumerate(filtered_jobs):
        render_job_card(job, i)
    
    # 职位详情弹窗
    if st.button("查看详情", key="detail_btn"):
        st.session_state["show_detail"] = True

else:
    # 显示热门职位或示例
    st.subheader("热门职位")
    st.info("输入关键词开始搜索职位")
    
    # 显示 mock 数据作为示例
    for i, job in enumerate(MOCK_JOBS[:3]):
        render_job_card(job, i)
