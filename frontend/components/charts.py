import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import List, Dict, Any

def create_salary_chart(jobs: List[Dict[str, Any]]) -> go.Figure:
    """创建薪资分布图"""
    salaries = []
    for job in jobs:
        if job.get("salary_range"):
            sal = job["salary_range"]
            if sal.get("min"):
                salaries.append({"title": job.get("title", "Unknown"), "salary": sal["min"]})
            if sal.get("max"):
                salaries.append({"title": job.get("title", "Unknown"), "salary": sal["max"]})
    
    if not salaries:
        fig = go.Figure()
        fig.add_annotation(text="暂无薪资数据", showarrow=False, font=dict(size=16))
        return fig
    
    df = pd.DataFrame(salaries)
    fig = px.histogram(df, x="salary", nbins=20, title="薪资分布")
    fig.update_layout(xaxis_title="薪资 (AUD)", yaxis_title="职位数量")
    return fig

def create_location_chart(jobs: List[Dict[str, Any]]) -> go.Figure:
    """创建地点分布图"""
    locations = {}
    for job in jobs:
        loc = job.get("location", "未知")
        locations[loc] = locations.get(loc, 0) + 1
    
    if not locations:
        fig = go.Figure()
        fig.add_annotation(text="暂无地点数据", showarrow=False, font=dict(size=16))
        return fig
    
    df = pd.DataFrame(list(locations.items()), columns=["location", "count"])
    fig = px.pie(df, values="count", names="location", title="职位地点分布")
    return fig

def create_skills_chart(skills_data: Dict[str, int]) -> go.Figure:
    """创建技能需求图"""
    if not skills_data:
        fig = go.Figure()
        fig.add_annotation(text="暂无技能数据", showarrow=False, font=dict(size=16))
        return fig
    
    df = pd.DataFrame(list(skills_data.items()), columns=["skill", "count"])
    df = df.sort_values("count", ascending=True).tail(15)
    
    fig = px.bar(df, x="count", y="skill", orientation="h", title="热门技能需求")
    fig.update_layout(xaxis_title="出现次数", yaxis_title="技能")
    return fig
