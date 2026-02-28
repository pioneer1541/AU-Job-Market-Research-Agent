"""
LangGraph Node Definitions
"""
import logging
import asyncio
import re
from typing import Literal, Optional, Tuple

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
    
    # 聚合分析结果（包含薪资统计）
    market_insights = _aggregate_insights(analysis_results, jobs)
    
    return {
        "analysis_results": analysis_results,
        "market_insights": market_insights,
        "errors": errors,
        "next_action": "generate_report"
    }


def parse_salary_range(salary_str: Optional[str]) -> Optional[Tuple[float, float, str]]:
    """
    解析薪资范围字符串，返回 (min, max, currency) 或 None。
    
    支持格式:
    - "$120,000 - $150,000"
    - "$100k - $120k"
    - "100000-150000 AUD/year"
    - "$80k+"
    - "120000-150000 AUD/year"
    """
    if not salary_str:
        return None
    
    # 统一处理
    s = salary_str.lower().replace(',', '').replace(' ', '')
    
    # 检测货币
    currency = 'AUD'  # 默认澳元（澳洲市场）
    if 'usd' in s:
        currency = 'USD'
    elif 'gbp' in s:
        currency = 'GBP'
    
    # 匹配 k 后缀 (如 100k)
    k_pattern = r'(\d+)k'
    k_matches = re.findall(k_pattern, s)
    if k_matches:
        nums = [float(m) * 1000 for m in k_matches]
        if len(nums) >= 2:
            return (min(nums), max(nums), currency)
        elif len(nums) == 1:
            return (nums[0], nums[0], currency)
    
    # 匹配普通数字（薪资通常 >= 30000）
    num_pattern = r'(\d+(?:\.\d+)?)'
    nums = [float(m) for m in re.findall(num_pattern, s)]
    
    # 过滤掉年份等干扰数字（薪资应该 >= 30000）
    nums = [n for n in nums if n >= 30000]
    
    if len(nums) >= 2:
        return (min(nums), max(nums), currency)
    elif len(nums) == 1:
        return (nums[0], nums[0], currency)
    
    return None


def _aggregate_insights(
    analysis_results: list[dict],
    jobs: list[dict],
) -> dict:
    """
    聚合多个职位的分析结果，生成市场洞察。
    包含薪资统计功能。
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
            "total_analyzed": 0,
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
    
    # 薪资统计 - 新增功能
    salaries = []
    salary_by_experience = {"Junior": [], "Mid": [], "Senior": [], "Lead": [], "Unknown": []}
    salary_by_industry = {}
    
    for result in analysis_results:
        salary_str = result.get("salary_estimate")
        parsed = parse_salary_range(salary_str)
        if parsed:
            min_sal, max_sal, currency = parsed
            # 使用薪资范围的中间值
            mid_salary = (min_sal + max_sal) / 2
            salaries.append({
                "min": min_sal,
                "max": max_sal,
                "mid": mid_salary,
                "currency": currency,
            })
            
            # 按经验级别分组
            exp_level = result.get("experience_level", "Unknown")
            if exp_level in salary_by_experience:
                salary_by_experience[exp_level].append(mid_salary)
            else:
                salary_by_experience["Unknown"].append(mid_salary)
            
            # 按行业分组
            industry = result.get("industry", "Unknown")
            if industry:
                if industry not in salary_by_industry:
                    salary_by_industry[industry] = []
                salary_by_industry[industry].append(mid_salary)
    
    # 计算薪资统计
    salary_stats = None
    if salaries:
        all_mids = [s["mid"] for s in salaries]
        avg_salary = sum(all_mids) / len(all_mids)
        min_salary = min(s["min"] for s in salaries)
        max_salary = max(s["max"] for s in salaries)
        
        salary_stats = {
            "average": round(avg_salary, 0),
            "min": round(min_salary, 0),
            "max": round(max_salary, 0),
            "count": len(salaries),
            "currency": salaries[0]["currency"] if salaries else "AUD",
        }
        
        # 按经验级别的薪资统计
        salary_by_exp_stats = {}
        for exp, vals in salary_by_experience.items():
            if vals:
                salary_by_exp_stats[exp] = {
                    "average": round(sum(vals) / len(vals), 0),
                    "min": round(min(vals), 0),
                    "max": round(max(vals), 0),
                    "count": len(vals),
                }
        
        # 按行业的薪资统计
        salary_by_ind_stats = {}
        for industry, vals in salary_by_industry.items():
            if vals and len(vals) >= 2:  # 至少2个样本才统计
                salary_by_ind_stats[industry] = {
                    "average": round(sum(vals) / len(vals), 0),
                    "min": round(min(vals), 0),
                    "max": round(max(vals), 0),
                    "count": len(vals),
                }
        
        salary_stats["by_experience"] = salary_by_exp_stats
        salary_stats["by_industry"] = salary_by_ind_stats
    
    return {
        "top_skills": top_skills,
        "experience_distribution": experience_distribution,
        "industry_distribution": industry_distribution,
        "top_locations": top_locations,
        "total_analyzed": len(analysis_results),
        "salary_stats": salary_stats,  # 新增薪资统计
    }


def format_salary(value: float, currency: str = "AUD") -> str:
    """格式化薪资数字为可读字符串"""
    if value >= 1000:
        return f"{currency} {value/1000:.0f}k"
    return f"{currency} {value:.0f}"


def report_generator_node(state: GraphState) -> dict:
    """
    Report generator node: Creates final market research report.
    包含薪资分析章节。
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
    
    # Salary Analysis - 新增章节
    salary_stats = market_insights.get("salary_stats")
    if salary_stats:
        report_sections.append("\n## Salary Analysis\n")
        currency = salary_stats.get("currency", "AUD")
        
        # 总体薪资统计
        avg = salary_stats.get("average", 0)
        min_sal = salary_stats.get("min", 0)
        max_sal = salary_stats.get("max", 0)
        count = salary_stats.get("count", 0)
        
        report_sections.append(f"\n### Overall Salary Range\n")
        report_sections.append(f"- **Average Salary**: {format_salary(avg, currency)}\n")
        report_sections.append(f"- **Salary Range**: {format_salary(min_sal, currency)} - {format_salary(max_sal, currency)}\n")
        report_sections.append(f"- **Based on**: {count} job listings with salary data\n")
        
        # 按经验级别的薪资
        by_exp = salary_stats.get("by_experience", {})
        if by_exp:
            report_sections.append(f"\n### Salary by Experience Level\n")
            # 按平均薪资排序
            sorted_exp = sorted(by_exp.items(), key=lambda x: x[1].get("average", 0), reverse=True)
            for exp, stats in sorted_exp:
                if stats.get("count", 0) > 0:
                    report_sections.append(
                        f"- **{exp}**: {format_salary(stats['average'], currency)} " 
                        f"(range: {format_salary(stats['min'], currency)} - {format_salary(stats['max'], currency)}, " 
                        f"n={stats['count']})\n"
                    )
        
        # 按行业的薪资
        by_ind = salary_stats.get("by_industry", {})
        if by_ind:
            report_sections.append(f"\n### Salary by Industry\n")
            sorted_ind = sorted(by_ind.items(), key=lambda x: x[1].get("average", 0), reverse=True)
            for industry, stats in sorted_ind[:5]:  # 只显示前5个行业
                report_sections.append(
                    f"- **{industry}**: {format_salary(stats['average'], currency)} " 
                    f"(range: {format_salary(stats['min'], currency)} - {format_salary(stats['max'], currency)}, " 
                    f"n={stats['count']})\n"
                )
    else:
        report_sections.append("\n## Salary Analysis\n")
        report_sections.append("\n*No salary data available for analysis.*\n")
    
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
