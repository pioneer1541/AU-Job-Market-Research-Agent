"""
LangGraph Node Definitions
"""
import logging
import asyncio
from typing import Literal

try:
    from .state import GraphState, JobListing as StateJobListing, AnalysisResult
except ImportError:
    # 测试环境下的导入
    from state import GraphState, JobListing as StateJobListing, AnalysisResult

try:
    from ..services.apify_client import ApifyClient, ApifyError, JobListing
except ImportError:
    # 测试环境下的导入
    from services.apify_client import ApifyClient, ApifyError, JobListing

try:
    from ..services.jd_analyzer import analyze_jobs_batch
except ImportError:
    # 测试环境下的导入
    from services.jd_analyzer import analyze_jobs_batch


logger = logging.getLogger(__name__)


def coordinator_node(state: GraphState) -> dict:
    """
    Coordinator node: Analyzes user query and determines next action.
    
    This is the entry point that decides which agents to invoke.
    """
    query = state["query"]
    
    # TODO: Use LLM to analyze query and determine:
    # 1. Job titles to search
    # 2. Locations to target
    # 3. Data sources to use
    
    # For now, simple routing
    return {
        "next_action": "fetch_jobs"
    }


async def job_fetcher_node(state: GraphState) -> dict:
    """
    Job fetcher node: Collects job listings from multiple sources.
    
    Uses Apify API to scrape Seek, Indeed, etc.
    
    修复: 改为原生异步函数，移除 asyncio.run()
    """
    query = state["query"]
    errors = []
    jobs: list[JobListing] = []
    
    # 解析查询参数（简单实现，后续可用 LLM 增强）
    # 格式: "job title in location" 或 "job title"
    parts = query.lower().split(" in ")
    search_query = parts[0].strip()
    location = parts[1].strip() if len(parts) > 1 else None
    
    logger.info(f"开始获取职位数据: query={search_query}, location={location}")
    
    try:
        # 使用 Apify Seek Scraper 获取数据
        # 修复: 直接使用 await，不再使用 asyncio.run()
        async with ApifyClient() as client:
            raw_jobs = await client.run_seek_scraper(
                search_query=search_query,
                location=location,
                max_items=50
            )
            jobs = [ApifyClient.parse_to_job_listing(job) for job in raw_jobs]
        
        logger.info(f"成功获取 {len(jobs)} 条职位数据")
        
    except ApifyError as e:
        error_msg = f"Apify API 错误: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
        
    except Exception as e:
        error_msg = f"获取职位数据失败: {e}"
        logger.exception(error_msg)
        errors.append(error_msg)
    
    # 基于 job_id 去重
    seen_ids = set()
    unique_jobs = []
    for job in jobs:
        if job["id"] not in seen_ids:
            seen_ids.add(job["id"])
            unique_jobs.append(job)
    
    if len(jobs) != len(unique_jobs):
        logger.info(f"去重: {len(jobs)} -> {len(unique_jobs)} 条职位数据")
    
    return {
        "job_listings": unique_jobs,
        "errors": errors,
        "next_action": "process_data" if unique_jobs else "END"
    }


def data_processor_node(state: GraphState) -> dict:
    """
    Data processor node: Cleans, deduplicates, and normalizes job data.
    """
    jobs = state.get("job_listings", [])
    
    # TODO: Implement data processing
    # 1. Remove duplicates
    # 2. Normalize salary formats
    # 3. Extract structured data
    
    processed_data = {
        "total_jobs": len(jobs),
        "unique_companies": 0,
        "salary_ranges": {},
    }
    
    return {
        "processed_data": processed_data,
        "next_action": "analyze"
    }


async def market_analyzer_node(state: GraphState) -> dict:
    """
    Market analyzer node: Performs statistical analysis on job data.
    
    使用 LLM 分析职位描述，提取技能、经验级别等信息。
    """
    processed_data = state.get("processed_data", {})
    jobs = state.get("job_listings", [])
    errors = state.get("errors", [])
    
    analysis_results: list[AnalysisResult] = []
    
    if jobs:
        try:
            logger.info(f"开始分析 {len(jobs)} 个职位...")
            analysis_results = await analyze_jobs_batch(jobs, batch_size=5)
            logger.info(f"完成 {len(analysis_results)} 个职位的分析")
        except Exception as e:
            error_msg = f"职位分析失败: {e}"
            logger.exception(error_msg)
            errors.append(error_msg)
    
    # 聚合分析结果
    market_insights = _aggregate_insights(analysis_results, jobs)
    
    return {
        "analysis_results": analysis_results,
        "market_insights": market_insights,
        "errors": errors,
        "next_action": "generate_report"
    }


def _aggregate_insights(
    analysis_results: list[AnalysisResult],
    jobs: list[JobListing],
) -> dict:
    """
    聚合多个职位的分析结果，生成市场洞察。
    """
    from collections import Counter
    
    if not analysis_results:
        return {
            "top_skills": [],
            "experience_distribution": {},
            "avg_salary": None,
            "salary_range": {},
            "top_locations": [],
            "industry_distribution": {},
        }
    
    # 技能频率统计
    all_skills = []
    for result in analysis_results:
        all_skills.extend(result.get("skills_required", []))
    skill_counts = Counter(all_skills)
    top_skills = [{"skill": skill, "count": count} for skill, count in skill_counts.most_common(10)]
    
    # 经验级别分布
    exp_counts = Counter(r.get("experience_level", "Unknown") for r in analysis_results)
    experience_distribution = dict(exp_counts)
    
    # 行业分布
    industry_counts = Counter(r.get("industry") for r in analysis_results if r.get("industry"))
    industry_distribution = dict(industry_counts)
    
    # 地点分布（从原始职位数据）
    location_counts = Counter(job.get("location", "Unknown") for job in jobs)
    top_locations = [{"location": loc, "count": count} for loc, count in location_counts.most_common(5)]
    
    return {
        "top_skills": top_skills,
        "experience_distribution": experience_distribution,
        "industry_distribution": industry_distribution,
        "top_locations": top_locations,
        "total_analyzed": len(analysis_results),
    }


def report_generator_node(state: GraphState) -> dict:
    """
    Report generator node: Creates final market research report.
    """
    market_insights = state.get("market_insights", {})
    processed_data = state.get("processed_data", {})
    analysis_results = state.get("analysis_results", [])
    jobs = state.get("job_listings", [])
    
    # 生成报告
    report_sections = [
        f"# Job Market Research Report\n",
        f"\n## Query: {state.get('query', 'N/A')}\n",
        f"\n## Summary\n",
        f"- Total Jobs Analyzed: {processed_data.get('total_jobs', 0)}",
        f"- Jobs with Analysis: {len(analysis_results)}\n",
    ]
    
    # Top Skills
    top_skills = market_insights.get("top_skills", [])
    if top_skills:
        report_sections.append("\n## Top Skills\n")
        for item in top_skills:
            report_sections.append(f"- {item['skill']}: {item['count']} mentions\n")
    
    # Experience Distribution
    exp_dist = market_insights.get("experience_distribution", {})
    if exp_dist:
        report_sections.append("\n## Experience Level Distribution\n")
        for level, count in sorted(exp_dist.items(), key=lambda x: -x[1]):
            report_sections.append(f"- {level}: {count} positions\n")
    
    # Industry Distribution
    industry_dist = market_insights.get("industry_distribution", {})
    if industry_dist:
        report_sections.append("\n## Industry Distribution\n")
        for industry, count in sorted(industry_dist.items(), key=lambda x: -x[1])[:5]:
            report_sections.append(f"- {industry}: {count} positions\n")
    
    # Top Locations
    top_locations = market_insights.get("top_locations", [])
    if top_locations:
        report_sections.append("\n## Top Locations\n")
        for item in top_locations:
            report_sections.append(f"- {item['location']}: {item['count']} positions\n")
    
    # TODO: Use LLM to generate recommendations and insights
    
    report = "".join(report_sections)
    
    return {
        "report": report,
        "next_action": "END"
    }


# Router functions for conditional edges

def supervisor_router(state: GraphState) -> Literal["fetch_jobs", "process_data", "analyze", "generate_report", "END"]:
    """Routes to the next node based on state."""
    next_action = state.get("next_action", "fetch_jobs")
    
    action_map = {
        "fetch_jobs": "fetch_jobs",
        "process_data": "process_data",
        "analyze": "analyze",
        "generate_report": "generate_report",
        "END": "END"
    }
    
    return action_map.get(next_action, "END")
