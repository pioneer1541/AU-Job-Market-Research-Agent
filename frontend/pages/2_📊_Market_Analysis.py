import streamlit as st
import sys
sys.path.insert(0, '.')
from components.charts import create_salary_chart, create_location_chart, create_skills_chart
from typing import Dict, Any

# Mock 分析数据
MOCK_MARKET_DATA = {
    "total_jobs": 1234,
    "avg_salary": 115000,
    "salary_range": {"min": 75000, "max": 180000},
    "top_locations": {
        "墨尔本": 450,
        "悉尼": 380,
        "布里斯班": 180,
        "珀斯": 120,
        "阿德莱德": 104
    },
    "top_skills": {
        "Python": 320,
        "JavaScript": 280,
        "AWS": 240,
        "React": 210,
        "SQL": 190,
        "Docker": 175,
        "TypeScript": 165,
        "Kubernetes": 140,
        "Java": 130,
        "Git": 125
    },
    "job_types": {
        "全职": 980,
        "兼职": 120,
        "合同": 85,
        "远程": 49
    },
    "trend": "上升"
}

# Mock 职位数据用于图表
MOCK_JOBS_FOR_CHARTS = [
    {"title": "Python Dev", "location": "墨尔本", "salary_range": {"min": 100000, "max": 130000}},
    {"title": "React Dev", "location": "悉尼", "salary_range": {"min": 95000, "max": 120000}},
    {"title": "Data Scientist", "location": "墨尔本", "salary_range": {"min": 120000, "max": 150000}},
    {"title": "DevOps Engineer", "location": "布里斯班", "salary_range": {"min": 110000, "max": 140000}},
    {"title": "Product Manager", "location": "墨尔本", "salary_range": {"min": 100000, "max": 130000}},
    {"title": "Backend Dev", "location": "悉尼", "salary_range": {"min": 90000, "max": 115000}},
    {"title": "ML Engineer", "location": "墨尔本", "salary_range": {"min": 130000, "max": 160000}},
    {"title": "Frontend Dev", "location": "珀斯", "salary_range": {"min": 85000, "max": 110000}},
]

st.set_page_config(page_title="市场分析", page_icon="📊", layout="wide")

st.title("📊 市场分析")
st.markdown("分析职位市场趋势和数据")

# 分析表单
col1, col2 = st.columns([3, 1])
with col1:
    analysis_query = st.text_input("分析关键词", placeholder="例如: Python 开发")
with col2:
    analysis_location = st.text_input("地点筛选", placeholder="例如: 墨尔本")

if st.button("生成分析", type="primary"):
    st.info("正在分析市场数据...")

# 显示市场概览
st.subheader("市场概览")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("职位总数", f"{MOCK_MARKET_DATA['total_jobs']:,}")
with col2:
    st.metric("平均薪资", f"{MOCK_MARKET_DATA['avg_salary']:,} AUD")
with col3:
    salary_range = MOCK_MARKET_DATA['salary_range']
    st.metric("薪资范围", f"{salary_range['min']:,} - {salary_range['max']:,}")
with col4:
    st.metric("市场趋势", MOCK_MARKET_DATA['trend'], delta="5%")

st.divider()

# 图表区域
col1, col2 = st.columns(2)

with col1:
    st.subheader("薪资分布")
    fig_salary = create_salary_chart(MOCK_JOBS_FOR_CHARTS)
    st.plotly_chart(fig_salary, use_container_width=True)

with col2:
    st.subheader("地点分布")
    fig_location = create_location_chart(MOCK_JOBS_FOR_CHARTS)
    st.plotly_chart(fig_location, use_container_width=True)

# 技能需求
st.subheader("热门技能需求")
fig_skills = create_skills_chart(MOCK_MARKET_DATA['top_skills'])
st.plotly_chart(fig_skills, use_container_width=True)

# 职位类型分布
st.subheader("职位类型分布")
job_types = MOCK_MARKET_DATA['job_types']
cols = st.columns(len(job_types))
for i, (job_type, count) in enumerate(job_types.items()):
    with cols[i]:
        st.metric(job_type, count)

# 地区薪资对比
st.subheader("地区平均薪资")
location_salary = {
    "墨尔本": 118000,
    "悉尼": 122000,
    "布里斯班": 108000,
    "珀斯": 105000,
    "阿德莱德": 98000
}
for loc, salary in location_salary.items():
    st.markdown(f"**{loc}**: {salary:,} AUD")
