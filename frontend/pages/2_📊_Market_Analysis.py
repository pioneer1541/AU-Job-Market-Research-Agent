import re
import sys
import time
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

sys.path.insert(0, '.')
from components.charts import (
    create_job_trend_chart,
    create_job_type_distribution_chart,
    create_location_hotspot_chart,
    create_salary_distribution_chart,
    create_skill_chart,
    create_top_employers_chart,
)
from components.report_cards import (
    inject_report_styles,
    render_meta_card,
    render_section_title,
    render_stat_card,
)
from utils.api import APIClient, APIError, get_default_api_url

st.set_page_config(page_title="市场分析", page_icon="📊", layout="wide")
inject_report_styles()

st.title("📊 市场分析报告")
st.markdown("专业化市场洞察：需求趋势、薪资结构、竞争强度、技能与雇主画像")


def parse_salary_to_range(salary_text: str) -> Dict[str, Any]:
    if not salary_text:
        return {}

    numbers = re.findall(r"\d[\d,]*", salary_text)
    values = [int(item.replace(",", "")) for item in numbers if item]
    if not values:
        return {}

    if len(values) == 1:
        return {"min": values[0], "max": values[0], "currency": "AUD", "period": "year"}
    return {"min": values[0], "max": values[1], "currency": "AUD", "period": "year"}


def normalize_jobs_for_chart(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for job in jobs:
        item = dict(job)
        if not item.get("salary_range") and item.get("salary"):
            item["salary_range"] = parse_salary_to_range(item.get("salary", ""))
        normalized.append(item)
    return normalized


def build_skill_counts(skills: List[str]) -> Dict[str, int]:
    if not skills:
        return {}

    if len(set(skills)) == len(skills):
        return {skill: len(skills) - idx for idx, skill in enumerate(skills)}

    return dict(Counter(skills))


def ranked_items_to_df(items: Any, label_col: str, top_n: int = 10) -> pd.DataFrame:
    """将 [{'item': 'xxx', 'count': n}] 结构转换为图表数据。"""
    if not isinstance(items, list):
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("item", "")).strip()
        if not label:
            continue
        try:
            count = int(entry.get("count", 0))
        except (TypeError, ValueError):
            continue
        rows.append({label_col: label, "数量": count})

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("数量", ascending=False).head(top_n)


def distribution_to_df(distribution: Any, label_col: str) -> pd.DataFrame:
    """将分布字典转换为图表数据。"""
    if not isinstance(distribution, dict):
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    for key, value in distribution.items():
        label = str(key).strip()
        if not label:
            continue
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        rows.append({label_col: label, "数量": count})

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("数量", ascending=False)


def format_salary_range_from_analysis(salary_analysis: Dict[str, Any]) -> str:
    """优先使用后端结构化薪资分析字段。"""
    annual = salary_analysis.get("annual", {}) if isinstance(salary_analysis, dict) else {}
    if not isinstance(annual, dict):
        return "暂无数据"

    min_val = annual.get("min")
    max_val = annual.get("max")
    if min_val is None or max_val is None:
        return "暂无数据"

    currency = salary_analysis.get("currency") or "AUD"
    try:
        return f"{currency} {int(min_val):,} - {int(max_val):,}"
    except (TypeError, ValueError):
        return "暂无数据"


def format_meta_time(meta: Dict[str, Any]) -> str:
    generated = str(meta.get("generated_at", "")).strip()
    if not generated:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return generated.replace("T", " ")


def _render_error(message: str) -> None:
    st.markdown(
        (
            "<div style='padding: 0.9rem 1rem; border-radius: 12px; border: 1px solid #f5c2c7; "
            "background: #fff1f2; color: #9f1239; margin: 0.7rem 0;'>"
            f"<strong>分析失败：</strong>{message}</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_empty_state(title: str, description: str) -> None:
    st.markdown(
        (
            "<div style='padding: 1.2rem; border-radius: 12px; border: 1px dashed #cbd5e1; "
            "background: #f8fafc; margin-top: 0.8rem;'>"
            f"<h4 style='margin:0; color:#0f172a;'>📭 {title}</h4>"
            f"<p style='margin:0.4rem 0 0 0; color:#475569;'>{description}</p>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _execute_analysis(query: str, location: Optional[str], max_results: int) -> None:
    client = APIClient(st.session_state["api_url"])
    progress = st.progress(0, text="准备分析任务...")

    try:
        with st.spinner("正在从后端拉取数据并生成报告..."):
            progress.progress(20, text="正在请求市场数据...")
            result = client.analyze_market(query=query, location=location, max_results=max_results)
            progress.progress(80, text="正在整理图表数据...")
            st.session_state["market_analysis_result"] = result
            st.session_state["analysis_defaults"] = {
                "query": query,
                "location": location or "",
                "max_results": int(max_results),
            }
            time.sleep(0.1)

        progress.progress(100, text="分析完成")
        st.success("报告已生成并写入历史记录。")

    except APIError as exc:
        _render_error(str(exc))
    except Exception as exc:
        _render_error(f"发生未知错误：{exc}")
    finally:
        time.sleep(0.05)
        progress.empty()


if "api_url" not in st.session_state:
    st.session_state["api_url"] = get_default_api_url()

if "market_analysis_result" not in st.session_state:
    st.session_state["market_analysis_result"] = None

if "analysis_defaults" not in st.session_state:
    st.session_state["analysis_defaults"] = {
        "query": "",
        "location": "",
        "max_results": 20,
    }

with st.sidebar:
    st.header("⚙️ 配置")
    api_url = st.text_input("API 地址", value=st.session_state["api_url"], key="market_api_url")
    st.session_state["api_url"] = (api_url or get_default_api_url()).rstrip("/")
    st.caption("可配置 `BACKEND_URL`、`JOB_MARKET_API_URL`、`API_BASE_URL`。")

pending_analysis = st.session_state.pop("pending_analysis", None)
if pending_analysis:
    st.info("已从历史记录载入参数，正在重新分析...")
    st.session_state["analysis_defaults"] = {
        "query": pending_analysis.get("query", "").strip(),
        "location": (pending_analysis.get("location") or "").strip(),
        "max_results": int(pending_analysis.get("max_results", 20)),
    }
    _execute_analysis(
        query=pending_analysis.get("query", "").strip(),
        location=(pending_analysis.get("location") or "").strip() or None,
        max_results=int(pending_analysis.get("max_results", 20)),
    )

analysis_defaults = st.session_state.get("analysis_defaults", {})

with st.expander("分析参数", expanded=True):
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        analysis_query = st.text_input(
            "分析关键词",
            value=str(analysis_defaults.get("query", "")),
            placeholder="例如: Data Scientist",
        )
    with c2:
        analysis_location = st.text_input(
            "地点筛选",
            value=str(analysis_defaults.get("location", "")),
            placeholder="例如: Melbourne",
        )
    with c3:
        default_max_results = int(analysis_defaults.get("max_results", 20))
        if default_max_results < 5 or default_max_results > 100:
            default_max_results = 20
        analysis_max_results = st.number_input("结果数量", min_value=5, max_value=100, value=default_max_results)

    if st.button("生成分析报告", type="primary", use_container_width=True):
        if not analysis_query.strip():
            st.warning("请输入分析关键词后再生成。")
        else:
            st.session_state["analysis_defaults"] = {
                "query": analysis_query.strip(),
                "location": analysis_location.strip(),
                "max_results": int(analysis_max_results),
            }
            _execute_analysis(
                query=analysis_query.strip(),
                location=analysis_location.strip() or None,
                max_results=int(analysis_max_results),
            )

result = st.session_state.get("market_analysis_result")
if not result:
    _render_empty_state("暂无分析结果", "输入关键词并点击“生成分析报告”后展示完整模块。")
    st.stop()

if not isinstance(result, dict):
    _render_error("返回结果格式异常，请检查后端接口。")
    st.stop()

market_insights: Dict[str, Any] = result.get("market_insights", {}) or {}
jobs: List[Dict[str, Any]] = result.get("jobs", []) or []
report: str = str(result.get("report", "") or "")
meta: Dict[str, Any] = result.get("meta", {}) or {}

sample_overview: Dict[str, Any] = market_insights.get("sample_overview", {}) or {}
trend_analysis: Dict[str, Any] = market_insights.get("trend_analysis", {}) or {}
salary_analysis: Dict[str, Any] = market_insights.get("salary_analysis", {}) or {}
applicant_analysis: Dict[str, Any] = market_insights.get("applicant_analysis", {}) or {}
competition_intensity: Dict[str, Any] = market_insights.get("competition_intensity", {}) or {}
skill_profile: Dict[str, Any] = market_insights.get("skill_profile", {}) or {}
deep_analysis: Dict[str, Any] = market_insights.get("deep_analysis", {}) or {}
employer_profile: Dict[str, Any] = market_insights.get("employer_profile", {}) or {}
top_jobs: Dict[str, Any] = market_insights.get("top_jobs", {}) or {}

jobs_for_chart = normalize_jobs_for_chart(jobs)
skills_from_profile = skill_profile.get("top_skills", []) if isinstance(skill_profile, dict) else []
if skills_from_profile and isinstance(skills_from_profile, list) and isinstance(skills_from_profile[0], dict):
    skills_list = [str(item.get("skill", "")).strip() for item in skills_from_profile if item.get("skill")]
else:
    skills_list = market_insights.get("top_skills", []) or []
skills_list = [skill for skill in skills_list if skill]

skills_data = build_skill_counts(skills_list)
location_distribution: Dict[str, int] = (
    market_insights.get("location_distribution")
    or sample_overview.get("location_distribution")
    or {}
)
company_list: List[str] = market_insights.get("top_companies", []) or []
if not company_list and isinstance(employer_profile, dict):
    company_list = [
        str(item.get("company", "")).strip()
        for item in employer_profile.get("top_employers", []) or []
        if isinstance(item, dict) and item.get("company")
    ]

salary_range_text = market_insights.get("avg_salary_range") or format_salary_range_from_analysis(salary_analysis)
total_jobs = int(sample_overview.get("total_jobs") or market_insights.get("total_jobs") or len(jobs))
company_count = len(set(company_list)) if company_list else len(set(job.get("company") for job in jobs if job.get("company")))

# A. 报告元信息卡片
render_section_title("A. 报告元信息", "当前报告的查询条件和生成上下文")
render_meta_card(
    query=analysis_query.strip() or "已加载历史报告",
    location=analysis_location.strip(),
    max_results=int(analysis_max_results),
    generated_at=format_meta_time(meta),
)

# B. 样本概览卡片
render_section_title("B. 样本概览", "快速了解样本规模和核心统计")
c1, c2, c3, c4 = st.columns(4)
with c1:
    render_stat_card("职位总数", f"{total_jobs:,}", "本次分析覆盖职位数量")
with c2:
    render_stat_card("平均薪资范围", str(salary_range_text), "来自含薪资样本的区间")
with c3:
    render_stat_card("热门技能数", str(len(skills_list)), "按出现频次排序")
with c4:
    render_stat_card("覆盖公司数", str(company_count), "去重后企业数量")

# C. 需求侧分析
render_section_title("C. 需求侧分析", "观察职位发布时间趋势与岗位类型结构")
d1, d2 = st.columns(2)
with d1:
    st.plotly_chart(
        create_job_trend_chart(jobs_for_chart, chart_type="line", trend_analysis=trend_analysis),
        use_container_width=True,
    )
with d2:
    st.plotly_chart(create_job_type_distribution_chart(jobs_for_chart), use_container_width=True)
with st.expander("查看需求侧解读", expanded=False):
    st.markdown(
        f"- 当前样本共 **{total_jobs}** 个职位。\n"
        f"- 岗位类型分布可用于识别全职/合同工机会占比。\n"
        "- 若趋势图数据点较少，通常是职位发布时间字段缺失导致。"
    )

# D. 薪资分析
render_section_title("D. 薪资分析", "通过直方图和箱线边际识别薪资密集区间")
st.plotly_chart(
    create_salary_distribution_chart(jobs_for_chart, show_box=True, salary_analysis=salary_analysis),
    use_container_width=True,
)
with st.expander("查看薪资分析说明", expanded=False):
    st.markdown(
        "- 直方图反映样本薪资在各区间的密度。\n"
        "- 箱线图可快速识别中位数与异常高/低值。\n"
        f"- API 提供的平均薪资区间：**{salary_range_text}**。"
    )

# E. 竞争强度
render_section_title("E. 竞争强度", "从地区集中度与申请人数判断竞争压力")
e1, e2, e3 = st.columns(3)
with e1:
    render_stat_card(
        "平均申请人数/职位",
        str(applicant_analysis.get("avg_applicants_per_job", 0)),
        "基于含申请人数字段的职位样本",
    )
with e2:
    render_stat_card(
        "申请人数样本量",
        str(applicant_analysis.get("count", 0)),
        "可用于计算竞争强度",
    )
with e3:
    render_stat_card(
        "申请人数覆盖率",
        f"{applicant_analysis.get('coverage_pct', 0)}%",
        "申请人数字段覆盖的职位比例",
    )

left_e, right_e = st.columns(2)
with left_e:
    st.plotly_chart(
        create_location_hotspot_chart(
            jobs=jobs_for_chart,
            location_distribution=location_distribution,
            competition_intensity=competition_intensity,
        ),
        use_container_width=True,
    )
with right_e:
    # 将经验级别平均申请人数转为柱状图，快速比较不同层级竞争压力。
    exp_groups = applicant_analysis.get("by_experience", {}) if isinstance(applicant_analysis, dict) else {}
    exp_rows = []
    if isinstance(exp_groups, dict):
        for level, item in exp_groups.items():
            if not isinstance(item, dict):
                continue
            try:
                exp_rows.append({"经验级别": str(level), "平均申请人数": float(item.get("avg_applicants", 0))})
            except (TypeError, ValueError):
                continue
    if exp_rows:
        exp_df = pd.DataFrame(exp_rows).sort_values("平均申请人数", ascending=False)
        st.bar_chart(exp_df.set_index("经验级别"))
    else:
        st.info("暂无按经验级别的申请人数统计。")

salary_groups = applicant_analysis.get("by_salary_band", {}) if isinstance(applicant_analysis, dict) else {}
salary_rows = []
if isinstance(salary_groups, dict):
    for band, item in salary_groups.items():
        if not isinstance(item, dict):
            continue
        try:
            salary_rows.append({"薪资区间": str(band), "平均申请人数": float(item.get("avg_applicants", 0))})
        except (TypeError, ValueError):
            continue

if salary_rows:
    # 统一薪资区间展示顺序，避免图表顺序抖动。
    band_order = ["<100k", "100k-150k", "150k-200k", ">=200k"]
    salary_df = pd.DataFrame(salary_rows)
    salary_df["order"] = salary_df["薪资区间"].apply(
        lambda x: band_order.index(x) if x in band_order else len(band_order)
    )
    salary_df = salary_df.sort_values(["order", "平均申请人数"], ascending=[True, False]).drop(columns=["order"])
    st.bar_chart(salary_df.set_index("薪资区间"))
else:
    st.info("暂无按薪资区间的申请人数统计。")

with st.expander("查看竞争强度解读", expanded=False):
    if location_distribution:
        top3_total = sum(sorted(location_distribution.values(), reverse=True)[:3])
        ratio = (top3_total / total_jobs * 100) if total_jobs else 0
        st.markdown(f"- Top 3 地区占比约 **{ratio:.1f}%**，可用于判断市场是否集中。")
    else:
        st.markdown("- 当前样本缺少完整地区分布，建议增加 `max_results` 或切换关键词。")
    if applicant_analysis.get("count", 0):
        st.markdown(
            f"- 平均每个职位申请人数约 **{applicant_analysis.get('avg_applicants_per_job', 0)}**，"
            "可结合经验级别与薪资区间评估投递难度。"
        )

# F. 技能画像
render_section_title("F. 技能画像", "结合词频识别技能栈优先级")
skill_chart_type = st.radio("技能图表样式", options=["bar", "wordcloud"], horizontal=True, label_visibility="collapsed")
st.plotly_chart(
    create_skill_chart(skills_data, chart_type=skill_chart_type, skill_profile=skill_profile),
    use_container_width=True,
)
with st.expander("查看技能画像解读", expanded=False):
    if skills_list:
        top_text = "、".join(skills_list[:5])
        st.markdown(f"- Top 技能：**{top_text}**。\n- 可据此调整简历关键词与项目展示重点。")
    else:
        st.markdown("- 暂无技能统计，可能是后端未返回技能字段。")

# G. 雇主画像
render_section_title("G. 雇主画像", "识别持续招聘的关键雇主")
st.plotly_chart(
    create_top_employers_chart(
        jobs=jobs_for_chart,
        top_companies=company_list,
        employer_profile=employer_profile,
    ),
    use_container_width=True,
)
with st.expander("查看雇主画像解读", expanded=False):
    if company_list:
        st.markdown(f"- 高频雇主包括：**{'、'.join(company_list[:5])}**。")
    else:
        st.markdown("- 当前样本未提供 Top 雇主列表，图表已根据职位公司字段自动聚合。")

# H. TOP3 职位分析
render_section_title("H. TOP3 职位分析", "申请人数与薪资双维度的头部岗位")
top_by_applicants: List[Dict[str, Any]] = top_jobs.get("top_by_applicants", []) if isinstance(top_jobs, dict) else []
top_by_salary: List[Dict[str, Any]] = top_jobs.get("top_by_salary", []) if isinstance(top_jobs, dict) else []

left_col, right_col = st.columns(2)
with left_col:
    st.markdown("#### 申请人数最多 TOP3")
    if top_by_applicants:
        for idx, item in enumerate(top_by_applicants[:3], start=1):
            raw_applicants = item.get("num_applicants", 0)
            try:
                applicants = int(raw_applicants)
            except (TypeError, ValueError):
                applicants = 0
            st.markdown(
                (
                    f"**{idx}. {item.get('title', '未知职位')}**  \n"
                    f"公司：{item.get('company', '未知公司')}  \n"
                    f"申请人数：{applicants:,}  \n"
                    f"招聘网址：{item.get('url', 'N/A')}"
                )
            )
    else:
        st.info("暂无申请人数数据。")

with right_col:
    st.markdown("#### 薪资最高 TOP3")
    if top_by_salary:
        for idx, item in enumerate(top_by_salary[:3], start=1):
            st.markdown(
                (
                    f"**{idx}. {item.get('title', '未知职位')}**  \n"
                    f"公司：{item.get('company', '未知公司')}  \n"
                    f"薪资：{item.get('salary', '暂无数据')}  \n"
                    f"招聘网址：{item.get('url', 'N/A')}"
                )
            )
    else:
        st.info("暂无薪资数据。")

# I. 深度分析展示区域
render_section_title("I. 深度分析", "硬技能、软技能、关键词与任职要求的细粒度统计")

# 将 deep_analysis 的不同字段标准化为 DataFrame，统一用于柱状图展示。
hard_skills_df = ranked_items_to_df(deep_analysis.get("top_hard_skills", []), "硬技能")
soft_skills_df = ranked_items_to_df(deep_analysis.get("top_soft_skills", []), "软技能")
industry_keywords_df = ranked_items_to_df(deep_analysis.get("top_industry_keywords", []), "行业关键词")
responsibility_df = ranked_items_to_df(deep_analysis.get("top_responsibility_themes", []), "职责主题")
qualifications_df = ranked_items_to_df(deep_analysis.get("top_qualifications", []), "任职资格")
years_dist_df = distribution_to_df(deep_analysis.get("years_of_experience_distribution", {}), "经验年限")

i1, i2 = st.columns(2)
with i1:
    st.markdown("#### 硬技能 Top10")
    if hard_skills_df.empty:
        st.info("暂无硬技能数据。")
    else:
        st.bar_chart(hard_skills_df.set_index("硬技能"))
with i2:
    st.markdown("#### 软技能 Top10")
    if soft_skills_df.empty:
        st.info("暂无软技能数据。")
    else:
        st.bar_chart(soft_skills_df.set_index("软技能"))

i3, i4 = st.columns(2)
with i3:
    st.markdown("#### 行业关键词 Top10")
    if industry_keywords_df.empty:
        st.info("暂无行业关键词数据。")
    else:
        st.bar_chart(industry_keywords_df.set_index("行业关键词"))
with i4:
    st.markdown("#### 职责主题 Top10")
    if responsibility_df.empty:
        st.info("暂无职责主题数据。")
    else:
        st.bar_chart(responsibility_df.set_index("职责主题"))

i5, i6 = st.columns(2)
with i5:
    st.markdown("#### 任职资格 Top10")
    if qualifications_df.empty:
        st.info("暂无任职资格数据。")
    else:
        st.bar_chart(qualifications_df.set_index("任职资格"))
with i6:
    st.markdown("#### 经验年限分布")
    if years_dist_df.empty:
        st.info("暂无经验年限数据。")
    else:
        st.bar_chart(years_dist_df.set_index("经验年限"))

with st.expander("查看完整分析报告（Markdown）", expanded=False):
    if report.strip():
        st.markdown(report)
    else:
        st.info("暂无文本报告内容。")
