import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _empty_figure(title: str, message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(size=15, color="#64748b"))
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=360,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(t=70, l=30, r=30, b=30),
    )
    return fig


def _extract_salary_numbers(salary_text: str) -> List[int]:
    if not salary_text:
        return []
    numbers = re.findall(r"\d[\d,]*", salary_text)
    values: List[int] = []
    for item in numbers:
        try:
            values.append(int(item.replace(",", "")))
        except ValueError:
            continue
    return values


def _to_count_mapping(raw: Any) -> Dict[str, int]:
    """统一将 list/dict 结构转换为计数字典。"""
    if isinstance(raw, dict):
        out: Dict[str, int] = {}
        for key, value in raw.items():
            try:
                out[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
        return out

    if isinstance(raw, list):
        out: Dict[str, int] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            label = item.get("skill") or item.get("company") or item.get("location") or item.get("name")
            count = item.get("count", 0)
            if not label:
                continue
            try:
                out[str(label)] = int(count)
            except (TypeError, ValueError):
                continue
        return out

    return {}


def _extract_trend_series(jobs: List[Dict[str, Any]], trend_analysis: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """优先使用后端 trend_analysis.series，缺失时回退到 jobs 聚合。"""
    if isinstance(trend_analysis, dict):
        raw_series = trend_analysis.get("series", [])
        if isinstance(raw_series, list):
            rows: List[Dict[str, Any]] = []
            for item in raw_series:
                if not isinstance(item, dict):
                    continue
                date_value = item.get("date")
                count_value = item.get("count", 0)
                if not date_value:
                    continue
                try:
                    rows.append({"date": str(date_value), "count": int(count_value)})
                except (TypeError, ValueError):
                    continue
            if rows:
                return sorted(rows, key=lambda x: x["date"])

    date_counter: Counter[str] = Counter()
    for job in jobs:
        posted_date = job.get("posted_date")
        if not posted_date:
            continue
        try:
            date_obj = datetime.fromisoformat(str(posted_date).replace("Z", "+00:00")).date()
        except ValueError:
            continue
        date_counter[str(date_obj)] += 1
    return [{"date": date_key, "count": count} for date_key, count in sorted(date_counter.items())]


def _infer_job_type(job: Dict[str, Any]) -> str:
    for key in ["job_type", "employment_type", "work_type", "type"]:
        if job.get(key):
            return str(job[key])

    title = str(job.get("title", "")).lower()
    if any(word in title for word in ["contract", "contractor"]):
        return "Contract"
    if any(word in title for word in ["part time", "part-time"]):
        return "Part-time"
    if any(word in title for word in ["intern", "internship"]):
        return "Internship"
    if any(word in title for word in ["temporary", "temp"]):
        return "Temporary"
    return "Full-time"


def create_job_trend_chart(
    jobs: List[Dict[str, Any]],
    chart_type: str = "line",
    trend_analysis: Optional[Dict[str, Any]] = None,
) -> go.Figure:
    """职位量趋势图（按 posted_date 聚合）。"""
    rows = _extract_trend_series(jobs, trend_analysis)
    if not rows:
        return _empty_figure("职位量趋势", "暂无可用发布日期数据")

    df = pd.DataFrame(rows)
    if "count" not in df.columns:
        trend_df = df.groupby("date").size().reset_index(name="count").sort_values("date")
    else:
        trend_df = df.sort_values("date")

    if chart_type == "bar":
        fig = px.bar(trend_df, x="date", y="count", title="职位量趋势")
    else:
        fig = px.line(trend_df, x="date", y="count", title="职位量趋势", markers=True)

    fig.update_layout(
        template="plotly_white",
        xaxis_title="发布日期",
        yaxis_title="职位数量",
        margin=dict(t=70, l=20, r=20, b=20),
        height=360,
    )
    return fig


def create_job_type_distribution_chart(jobs: List[Dict[str, Any]]) -> go.Figure:
    """职位类型分布图（饼图）。"""
    type_counts = Counter(_infer_job_type(job) for job in jobs)
    if not type_counts:
        return _empty_figure("职位类型分布", "暂无职位类型数据")

    df = pd.DataFrame(type_counts.items(), columns=["job_type", "count"]).sort_values("count", ascending=False)
    fig = px.pie(df, names="job_type", values="count", title="职位类型分布", hole=0.35)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(template="plotly_white", margin=dict(t=70, l=20, r=20, b=20), height=360)
    return fig


def create_salary_distribution_chart(
    jobs: List[Dict[str, Any]],
    show_box: bool = True,
    salary_analysis: Optional[Dict[str, Any]] = None,
) -> go.Figure:
    """薪资分布图（直方图，可选箱线边际）。"""
    # 优先使用后端结构化薪资带统计，避免前端重复解析差异。
    if isinstance(salary_analysis, dict):
        bands = _to_count_mapping(salary_analysis.get("bands", {}))
        if bands:
            band_df = pd.DataFrame(bands.items(), columns=["band", "count"])
            fig = px.bar(band_df, x="band", y="count", title="薪资分布（薪资带）")
            fig.update_layout(
                template="plotly_white",
                xaxis_title="薪资区间",
                yaxis_title="职位数量",
                margin=dict(t=70, l=20, r=20, b=20),
                height=380,
            )
            return fig

    salary_values: List[int] = []
    for job in jobs:
        salary_range = job.get("salary_range") or {}
        if isinstance(salary_range, dict):
            for key in ["min", "max"]:
                if salary_range.get(key) is not None:
                    try:
                        salary_values.append(int(salary_range[key]))
                    except (TypeError, ValueError):
                        continue

        if not salary_range and job.get("salary"):
            salary_values.extend(_extract_salary_numbers(str(job.get("salary", ""))))

    salary_values = [value for value in salary_values if value > 0]
    if not salary_values:
        return _empty_figure("薪资分布", "暂无薪资数据")

    df = pd.DataFrame({"salary": salary_values})
    fig = px.histogram(
        df,
        x="salary",
        nbins=24,
        title="薪资分布",
        marginal="box" if show_box else None,
        opacity=0.9,
    )
    fig.update_layout(
        template="plotly_white",
        xaxis_title="薪资",
        yaxis_title="职位数量",
        margin=dict(t=70, l=20, r=20, b=20),
        height=380,
    )
    return fig


def create_location_hotspot_chart(
    jobs: Optional[List[Dict[str, Any]]] = None,
    location_distribution: Optional[Dict[str, int]] = None,
    competition_intensity: Optional[Dict[str, Any]] = None,
    top_n: int = 10,
) -> go.Figure:
    """热门地区图（柱状图）。"""
    location_counts: Counter[str] = Counter()

    if location_distribution:
        for key, value in location_distribution.items():
            try:
                location_counts[str(key)] += int(value)
            except (TypeError, ValueError):
                continue

    # 兼容后端 competition_intensity 中可能的地点分布字段
    if isinstance(competition_intensity, dict):
        location_counts.update(_to_count_mapping(competition_intensity.get("location_distribution", {})))

    if jobs:
        location_counts.update(str(job.get("location", "未知")) for job in jobs if job.get("location"))

    if not location_counts:
        return _empty_figure("热门地区", "暂无地区数据")

    rows = location_counts.most_common(top_n)
    df = pd.DataFrame(rows, columns=["location", "count"])
    fig = px.bar(df, x="count", y="location", orientation="h", title="热门地区（Top 10）")
    fig.update_layout(
        template="plotly_white",
        xaxis_title="职位数量",
        yaxis_title="地区",
        yaxis={"categoryorder": "total ascending"},
        margin=dict(t=70, l=20, r=20, b=20),
        height=380,
    )
    return fig


def create_skill_chart(
    skills: Dict[str, int],
    chart_type: str = "bar",
    top_n: int = 20,
    skill_profile: Optional[Dict[str, Any]] = None,
) -> go.Figure:
    """技能画像图（柱状图/词云风格散点）。"""
    if not skills and isinstance(skill_profile, dict):
        skills = _to_count_mapping(skill_profile.get("top_skills", []))

    if not skills:
        return _empty_figure("技能需求", "暂无技能数据")

    df = pd.DataFrame(skills.items(), columns=["skill", "count"]).sort_values("count", ascending=False).head(top_n)

    if chart_type == "wordcloud":
        fig = px.scatter(
            df,
            x="skill",
            y="count",
            size="count",
            color="count",
            text="skill",
            title="技能词频（词云风格）",
            size_max=55,
            color_continuous_scale="Teal",
        )
        fig.update_traces(textposition="top center")
        fig.update_layout(
            template="plotly_white",
            xaxis_title="技能",
            yaxis_title="频次",
            margin=dict(t=70, l=20, r=20, b=20),
            height=390,
        )
        return fig

    fig = px.bar(df.sort_values("count", ascending=True), x="count", y="skill", orientation="h", title="热门技能")
    fig.update_layout(
        template="plotly_white",
        xaxis_title="出现次数",
        yaxis_title="技能",
        margin=dict(t=70, l=20, r=20, b=20),
        height=390,
    )
    return fig


def create_top_employers_chart(
    jobs: Optional[List[Dict[str, Any]]] = None,
    top_companies: Optional[List[str]] = None,
    employer_profile: Optional[Dict[str, Any]] = None,
    top_n: int = 10,
) -> go.Figure:
    """Top 雇主图（柱状图）。"""
    company_counts: Counter[str] = Counter()

    if jobs:
        company_counts.update(
            str(job.get("company", "未知"))
            for job in jobs
            if job.get("company")
        )

    if top_companies:
        company_counts.update(str(company) for company in top_companies if company)

    if isinstance(employer_profile, dict):
        company_counts.update(_to_count_mapping(employer_profile.get("top_employers", [])))

    if not company_counts:
        return _empty_figure("Top 雇主", "暂无雇主数据")

    rows = company_counts.most_common(top_n)
    df = pd.DataFrame(rows, columns=["company", "count"])
    fig = px.bar(df, x="count", y="company", orientation="h", title="Top 雇主（Top 10）")
    fig.update_layout(
        template="plotly_white",
        xaxis_title="职位数量",
        yaxis_title="公司",
        yaxis={"categoryorder": "total ascending"},
        margin=dict(t=70, l=20, r=20, b=20),
        height=390,
    )
    return fig
