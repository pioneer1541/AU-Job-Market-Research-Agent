"""
LangGraph Node Definitions
"""
import logging
import asyncio
from typing import Literal

try:
    from .state import GraphState, JobListing as StateJobListing
except ImportError:
    # 测试环境下的导入
    from state import GraphState, JobListing as StateJobListing

try:
    from ..services.apify_client import ApifyClient, ApifyError, JobListing
except ImportError:
    # 测试环境下的导入
    from services.apify_client import ApifyClient, ApifyError, JobListing


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


def job_fetcher_node(state: GraphState) -> dict:
    """
    Job fetcher node: Collects job listings from multiple sources.
    
    Uses Apify API to scrape Seek, Indeed, etc.
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
        async def fetch_jobs():
            async with ApifyClient() as client:
                raw_jobs = await client.run_seek_scraper(
                    search_query=search_query,
                    location=location,
                    max_items=50
                )
                return [ApifyClient.parse_to_job_listing(job) for job in raw_jobs]
        
        # 运行异步任务
        jobs = asyncio.run(fetch_jobs())
        logger.info(f"成功获取 {len(jobs)} 条职位数据")
        
    except ApifyError as e:
        error_msg = f"Apify API 错误: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
        
    except Exception as e:
        error_msg = f"获取职位数据失败: {e}"
        logger.exception(error_msg)
        errors.append(error_msg)
    
    return {
        "job_listings": jobs,
        "errors": errors,
        "next_action": "process_data" if jobs else "END"
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


def market_analyzer_node(state: GraphState) -> dict:
    """
    Market analyzer node: Performs statistical analysis on job data.
    """
    processed_data = state.get("processed_data", {})
    jobs = state.get("job_listings", [])
    
    # TODO: Implement analysis
    # 1. Skill frequency analysis
    # 2. Salary distribution
    # 3. Location distribution
    # 4. Experience level distribution
    
    market_insights = {
        "top_skills": [],
        "avg_salary": None,
        "salary_range": {},
        "top_locations": [],
    }
    
    return {
        "market_insights": market_insights,
        "next_action": "generate_report"
    }


def report_generator_node(state: GraphState) -> dict:
    """
    Report generator node: Creates final market research report.
    """
    market_insights = state.get("market_insights", {})
    processed_data = state.get("processed_data", {})
    jobs = state.get("job_listings", [])
    
    # TODO: Use LLM to generate comprehensive report
    
    report = f"""
# Job Market Research Report

## Query: {state.get("query", "N/A")}

## Summary
- Total Jobs Analyzed: {processed_data.get("total_jobs", 0)}
- Unique Companies: {processed_data.get("unique_companies", 0)}

## Top Skills
(To be implemented)

## Salary Analysis
(To be implemented)

## Recommendations
(To be implemented)
"""
    
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
