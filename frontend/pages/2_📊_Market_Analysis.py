import re
import sys
import time
import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

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


def _append_analysis_history(
    query: str,
    location: Optional[str],
    max_results: int,
    result: Dict[str, Any],
) -> None:
    market_insights = result.get("market_insights", {}) or {}
    history = st.session_state.setdefault("analysis_history", [])
    history.insert(
        0,
        {
            "id": f"a-{uuid.uuid4().hex[:10]}",
            "type": "analysis",
            "query": query,
            "location": location or "",
            "max_results": max_results,
            "results_count": market_insights.get("total_jobs", len(result.get("jobs", []))),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        },
    )
    st.session_state["analysis_history"] = history[:100]


def _execute_analysis(query: str, location: Optional[str], max_results: int) -> None:
    client = APIClient(st.session_state["api_url"])
    progress = st.progress(0, text="准备分析任务...")

    try:
        with st.spinner("正在从后端拉取数据并生成报告..."):
            progress.progress(20, text="正在请求市场数据...")
            result = client.analyze_market(query=query, location=location, max_results=max_results)
            progress.progress(80, text="正在整理图表数据...")
            st.session_state["market_analysis_result"] = result
            _append_analysis_history(query=query, location=location, max_results=max_results, result=result)
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

if "analysis_history" not in st.session_state:
    st.session_state["analysis_history"] = []

with st.sidebar:
    st.header("⚙️ 配置")
    api_url = st.text_input("API 地址", value=st.session_state["api_url"], key="market_api_url")
    st.session_state["api_url"] = (api_url or get_default_api_url()).rstrip("/")
    st.caption("可配置 `BACKEND_URL`、`JOB_MARKET_API_URL`、`API_BASE_URL`。")

pending_analysis = st.session_state.pop("pending_analysis", None)
if pending_analysis:
    st.info("已从历史记录载入参数，正在重新分析...")
    _execute_analysis(
        query=pending_analysis.get("query", "").strip(),
        location=(pending_analysis.get("location") or "").strip() or None,
        max_results=int(pending_analysis.get("max_results", 20)),
    )

with st.expander("分析参数", expanded=True):
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        analysis_query = st.text_input("分析关键词", placeholder="例如: Data Scientist")
    with c2:
        analysis_location = st.text_input("地点筛选", placeholder="例如: Melbourne")
    with c3:
        analysis_max_results = st.number_input("结果数量", min_value=5, max_value=100, value=20)

    if st.button("生成分析报告", type="primary", use_container_width=True):
        if not analysis_query.strip():
            st.warning("请输入分析关键词后再生成。")
        else:
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

jobs_for_chart = normalize_jobs_for_chart(jobs)
skills_list: List[str] = market_insights.get("top_skills", []) or []
skills_data = build_skill_counts(skills_list)
location_distribution: Dict[str, int] = market_insights.get("location_distribution", {}) or {}
company_list: List[str] = market_insights.get("top_companies", []) or []

salary_range_text = market_insights.get("avg_salary_range") or "暂无数据"
total_jobs = int(market_insights.get("total_jobs") or len(jobs))
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
    st.plotly_chart(create_job_trend_chart(jobs_for_chart, chart_type="line"), use_container_width=True)
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
st.plotly_chart(create_salary_distribution_chart(jobs_for_chart, show_box=True), use_container_width=True)
with st.expander("查看薪资分析说明", expanded=False):
    st.markdown(
        "- 直方图反映样本薪资在各区间的密度。\n"
        "- 箱线图可快速识别中位数与异常高/低值。\n"
        f"- API 提供的平均薪资区间：**{salary_range_text}**。"
    )

# E. 竞争强度
render_section_title("E. 竞争强度", "从地区职位集中度判断竞争热点")
st.plotly_chart(
    create_location_hotspot_chart(jobs=jobs_for_chart, location_distribution=location_distribution),
    use_container_width=True,
)
with st.expander("查看竞争强度解读", expanded=False):
    if location_distribution:
        top3_total = sum(sorted(location_distribution.values(), reverse=True)[:3])
        ratio = (top3_total / total_jobs * 100) if total_jobs else 0
        st.markdown(f"- Top 3 地区占比约 **{ratio:.1f}%**，可用于判断市场是否集中。")
    else:
        st.markdown("- 当前样本缺少完整地区分布，建议增加 `max_results` 或切换关键词。")

# F. 技能画像
render_section_title("F. 技能画像", "结合词频识别技能栈优先级")
skill_chart_type = st.radio("技能图表样式", options=["bar", "wordcloud"], horizontal=True, label_visibility="collapsed")
st.plotly_chart(create_skill_chart(skills_data, chart_type=skill_chart_type), use_container_width=True)
with st.expander("查看技能画像解读", expanded=False):
    if skills_list:
        top_text = "、".join(skills_list[:5])
        st.markdown(f"- Top 技能：**{top_text}**。\n- 可据此调整简历关键词与项目展示重点。")
    else:
        st.markdown("- 暂无技能统计，可能是后端未返回技能字段。")

# G. 雇主画像
render_section_title("G. 雇主画像", "识别持续招聘的关键雇主")
st.plotly_chart(create_top_employers_chart(jobs=jobs_for_chart, top_companies=company_list), use_container_width=True)
with st.expander("查看雇主画像解读", expanded=False):
    if company_list:
        st.markdown(f"- 高频雇主包括：**{'、'.join(company_list[:5])}**。")
    else:
        st.markdown("- 当前样本未提供 Top 雇主列表，图表已根据职位公司字段自动聚合。")

with st.expander("查看完整分析报告（Markdown）", expanded=False):
    if report.strip():
        st.markdown(report)
    else:
        st.info("暂无文本报告内容。")
