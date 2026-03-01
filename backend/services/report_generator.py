"""
模块化报告生成服务
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def _fmt_int(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{int(round(value)):,}"


class ReportGenerator:
    """按照 A-G 结构生成报告。"""

    def generate(
        self,
        query: str,
        market_insights: dict[str, Any],
        processed_data: Optional[dict[str, Any]] = None,
        errors: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        processed_data = processed_data or {}
        errors = errors or []

        sample = market_insights.get("sample_overview", {}) or {}
        trend = market_insights.get("trend_analysis", {}) or {}
        salary = market_insights.get("salary_analysis", {}) or {}
        competition = market_insights.get("competition_intensity", {}) or {}
        skills = market_insights.get("skill_profile", {}) or {}
        employers = market_insights.get("employer_profile", {}) or {}
        salary_filter_stats = processed_data.get("salary_filter_stats", {}) or {}

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        sections: dict[str, str] = {}
        sections["A"] = (
            "## A. 报告元信息\n"
            f"- 查询关键词: `{query}`\n"
            f"- 生成时间: {generated_at}\n"
            f"- 数据管道阶段: {processed_data.get('pipeline_stage', 'analyze')}\n"
            f"- 错误数: {len(errors)}\n"
        )

        filter_lines = ""
        if salary_filter_stats:
            # 在报告中展示低薪过滤统计，明确过滤前后样本变化。
            filter_lines = (
                f"- 低薪过滤前职位数: {_fmt_int(salary_filter_stats.get('total_jobs_before_filter'))}\n"
                f"- 低薪过滤后职位数: {_fmt_int(salary_filter_stats.get('total_jobs_after_filter'))}\n"
                f"- 过滤职位数: {_fmt_int(salary_filter_stats.get('filtered_low_salary_jobs'))}\n"
                f"- 过滤占比: {salary_filter_stats.get('filtered_ratio_pct', 0)}%\n"
                f"- 过滤阈值: 时薪 < {salary_filter_stats.get('hourly_threshold_aud', 24)} AUD 或年薪 < {salary_filter_stats.get('annual_threshold_aud', 50000)} AUD\n"
            )

        sections["B"] = (
            "## B. 样本概览\n"
            f"- 样本职位数: {_fmt_int(sample.get('total_jobs'))}\n"
            f"- 雇主数: {_fmt_int(sample.get('unique_companies'))}\n"
            f"- 城市/地点数: {_fmt_int(sample.get('unique_locations'))}\n"
            f"- 薪资覆盖率: {sample.get('salary_coverage_pct', 0)}%\n"
            f"- 分析覆盖率: {sample.get('analysis_coverage_pct', 0)}%\n"
            f"- 日期范围: {sample.get('date_range', {}).get('start', 'N/A')} ~ {sample.get('date_range', {}).get('end', 'N/A')}\n"
            f"{filter_lines}"
        )

        trend_items = trend.get("series", [])[:10]
        trend_lines = "\n".join(
            f"  - {item.get('date')}: {item.get('count')} 条"
            for item in trend_items
        ) or "  - 暂无有效发布日期数据"
        sections["C"] = (
            "## C. 需求侧分析\n"
            f"- 趋势方向: {trend.get('trend', 'unknown')}\n"
            f"- 日均职位量: {trend.get('avg_daily_postings', 0)}\n"
            "- 近期职位量序列:\n"
            f"{trend_lines}\n"
        )

        annual = salary.get("annual", {}) or {}
        sections["D"] = (
            "## D. 薪资分析\n"
            f"- 样本量: {_fmt_int(salary.get('count'))}\n"
            f"- 币种: {salary.get('currency', 'N/A')}\n"
            f"- 年化平均: {_fmt_int(annual.get('avg'))}\n"
            f"- 年化中位数: {_fmt_int(annual.get('median'))}\n"
            f"- 年化范围: {_fmt_int(annual.get('min'))} ~ {_fmt_int(annual.get('max'))}\n"
            f"- 四分位: P25={_fmt_int(annual.get('p25'))}, P75={_fmt_int(annual.get('p75'))}\n"
            f"- 薪资带分布: {salary.get('bands', {})}\n"
        )

        sections["E"] = (
            "## E. 竞争强度\n"
            f"- 竞争等级: {competition.get('competition_level', 'unknown')}\n"
            f"- 单公司平均岗位数: {competition.get('jobs_per_company', 0)}\n"
            f"- 头部公司占比: {competition.get('top_company_share_pct', 0)}%\n"
            f"- 头部地点占比: {competition.get('top_location_share_pct', 0)}%\n"
        )

        top_skills = skills.get("top_skills", [])[:10]
        skill_lines = "\n".join(
            f"  - {item.get('skill')}: {item.get('count')}"
            for item in top_skills
        ) or "  - 暂无技能数据"
        sections["F"] = (
            "## F. 技能画像\n"
            f"- 技能总数(去重): {skills.get('total_unique_skills', 0)}\n"
            "- Top 技能:\n"
            f"{skill_lines}\n"
        )

        top_employers = employers.get("top_employers", [])[:10]
        employer_lines = "\n".join(
            f"  - {item.get('company')}: {item.get('count')}"
            for item in top_employers
        ) or "  - 暂无雇主数据"
        sections["G"] = (
            "## G. 雇主画像\n"
            f"- 雇主总数: {employers.get('unique_employers', 0)}\n"
            f"- 远程/混合岗位占比: {employers.get('remote_ratio_pct', 0)}%\n"
            f"- 雇主集中度(HHI): {employers.get('employer_concentration_hhi', 0)}\n"
            "- Top 雇主:\n"
            f"{employer_lines}\n"
        )

        report = "\n".join(
            [
                "# Job Market Research Report",
                "# 职位市场研究报告",
                "",
                sections["A"],
                sections["B"],
                sections["C"],
                sections["D"],
                sections["E"],
                sections["F"],
                sections["G"],
            ]
        )

        return {
            "report": report,
            "report_sections": sections,
            "report_meta": {
                "query": query,
                "generated_at": generated_at,
                "section_order": ["A", "B", "C", "D", "E", "F", "G"],
            },
        }
