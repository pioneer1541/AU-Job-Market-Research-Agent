"""
LangGraph Node Definitions
"""
import logging
import asyncio
from typing import Literal, Optional

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

try:
    from ..services.statistics import StatisticsService
    from ..services.report_generator import ReportGenerator
except ImportError:
    from services.statistics import StatisticsService
    from services.report_generator import ReportGenerator


logger = logging.getLogger(__name__)
statistics_service = StatisticsService()
report_service = ReportGenerator()


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
    
    sample_overview = statistics_service.compute_sample_overview(jobs, [])
    processed_data = {
        **sample_overview,
        "pipeline_stage": "process_data",
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
    
    # 聚合统计分析（需求趋势/薪资/竞争强度/技能/雇主）
    market_insights = statistics_service.generate_market_insights(jobs, analysis_results)
    
    return {
        "analysis_results": analysis_results,
        "market_insights": market_insights,
        "errors": errors,
        "next_action": "generate_report"
    }


def report_generator_node(state: GraphState) -> dict:
    """
    Report generator node: Creates final market research report.
    包含薪资分析章节。
    """
    generated = report_service.generate(
        query=state.get("query", "N/A"),
        market_insights=state.get("market_insights", {}) or {},
        processed_data=state.get("processed_data", {}) or {},
        errors=state.get("errors", []) or [],
    )
    return {
        "report": generated["report"],
        "processed_data": {
            **(state.get("processed_data", {}) or {}),
            "report_meta": generated.get("report_meta", {}),
            "report_sections": generated.get("report_sections", {}),
        },
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
