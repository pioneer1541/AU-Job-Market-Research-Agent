"""API route definitions.
API 路由定义
"""

import logging
import os
from collections import Counter
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from backend.agents.graph import get_compiled_graph
from backend.agents.nodes import job_fetcher_node
from backend.api.schemas import (
    SearchRequest,
    JobSearchResponse,
    JobListing,
    JobDetailResponse,
    JobAnalysis,
    AnalyzeResponse,
    MarketInsights,
    ReportListResponse,
    ReportSummary,
    ReportDetailResponse,
    HealthResponse,
    ErrorResponse,
    # 旧版兼容
    SearchParams,
    SearchResponse,
    StatusResponse,
)
from backend.services.database import get_database_service
from backend.services.statistics import StatisticsService

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Mock 数据 ====================

# Mock 职位数据（用于测试和演示）
MOCK_JOBS: dict[str, JobListing] = {
    "job-001": JobListing(
        id="job-001",
        title="Senior AI Engineer",
        company="TechCorp Melbourne",
        location="Melbourne, VIC",
        salary="$150,000 - $180,000",
        description="We are looking for an experienced AI Engineer to join our team...",
        url="https://seek.com.au/job/001",
        source="seek",
        posted_date="2026-02-28",
        num_applicants=132,
    ),
    "job-002": JobListing(
        id="job-002",
        title="Machine Learning Engineer",
        company="DataDriven Inc",
        location="Sydney, NSW",
        salary="$130,000 - $160,000",
        description="Join our ML team to build cutting-edge models...",
        url="https://seek.com.au/job/002",
        source="seek",
        posted_date="2026-02-27",
        num_applicants=97,
    ),
    "job-003": JobListing(
        id="job-003",
        title="AI Research Scientist",
        company="Innovation Labs",
        location="Remote",
        salary="$140,000 - $170,000",
        description="Research position focusing on LLM and generative AI...",
        url="https://indeed.com/job/003",
        source="indeed",
        posted_date="2026-02-26",
        num_applicants=81,
    ),
}

# Mock 分析结果
MOCK_ANALYSES: dict[str, JobAnalysis] = {
    "job-001": JobAnalysis(
        job_id="job-001",
        skills_required=["Python", "TensorFlow", "PyTorch", "AWS", "Docker"],
        experience_level="Senior",
        salary_estimate="$150,000 - $180,000",
        key_requirements=["5+ years experience", "ML system design", "Team leadership"],
        industry="Technology",
    ),
    "job-002": JobAnalysis(
        job_id="job-002",
        skills_required=["Python", "Scikit-learn", "SQL", "Spark"],
        experience_level="Mid-Senior",
        salary_estimate="$130,000 - $160,000",
        key_requirements=["3+ years experience", "Data pipelines", "Model deployment"],
        industry="Technology",
    ),
    "job-003": JobAnalysis(
        job_id="job-003",
        skills_required=["Python", "PyTorch", "NLP", "Research writing"],
        experience_level="Senior",
        salary_estimate="$140,000 - $170,000",
        key_requirements=["PhD preferred", "Published research", "LLM experience"],
        industry="Research",
    ),
}


def _format_query(query: str, location: Optional[str]) -> str:
    """构造传递给 graph/node 的查询语句。"""
    if location:
        return f"{query} in {location}"
    return query


def _is_paid_api_enabled() -> bool:
    """
    是否允许调用可能产生费用的外部 API。
    默认关闭，避免误触发付费调用。
    """
    return os.getenv("ENABLE_PAID_APIS", "false").lower() in {"1", "true", "yes", "on"}


def _build_mock_search_jobs(query: str, location: Optional[str], max_results: int) -> list[JobListing]:
    """按查询条件过滤 mock 职位。"""
    all_jobs = list(MOCK_JOBS.values())
    query_lower = query.lower()
    filtered_jobs = [
        job for job in all_jobs
        if query_lower in job.title.lower() or query_lower in job.description.lower()
    ]

    if location:
        location_lower = location.lower()
        filtered_jobs = [
            job for job in filtered_jobs
            if location_lower in job.location.lower()
        ]

    return filtered_jobs[:max_results]


def _convert_state_jobs_to_api_jobs(raw_jobs: list[dict], max_results: int) -> list[JobListing]:
    """将 graph state 中的职位结构转换为 API Schema。"""
    jobs: list[JobListing] = []
    for item in raw_jobs:
        try:
            jobs.append(
                JobListing(
                    id=str(item.get("id", "")),
                    title=str(item.get("title", "")),
                    company=str(item.get("company", "")),
                    location=str(item.get("location", "")),
                    salary=item.get("salary"),
                    description=str(item.get("description", "")),
                    url=str(item.get("url", "")),
                    source=str(item.get("source", "unknown")),
                    posted_date=item.get("posted_date"),
                    num_applicants=item.get("num_applicants", item.get("numApplicants")),
                )
            )
        except Exception as e:
            logger.warning(f"跳过无法解析的职位数据: {e}")
            continue
    return jobs[:max_results]


def _build_market_insights_from_graph(jobs: list[JobListing], graph_result: dict) -> MarketInsights:
    """将 LangGraph 输出映射为 API 的 MarketInsights。"""
    market_insights = graph_result.get("market_insights", {}) or {}
    top_skills_raw = market_insights.get("top_skills", []) or []
    top_skills = [item.get("skill", "") for item in top_skills_raw if item.get("skill")]

    company_counts = Counter(job.company for job in jobs if job.company)
    top_companies = [company for company, _ in company_counts.most_common(5)]

    location_counts = Counter(job.location for job in jobs if job.location)

    salary_stats = market_insights.get("salary_stats") or {}
    avg_salary_range = None
    if salary_stats:
        currency = salary_stats.get("currency", "AUD")
        min_salary = salary_stats.get("min")
        max_salary = salary_stats.get("max")
        if min_salary is not None and max_salary is not None:
            avg_salary_range = f"{currency} {int(min_salary):,} - {int(max_salary):,}"

    # 兼容真实流程与旧数据：优先使用统计服务结果，缺失时基于 jobs 兜底计算。
    top_jobs = market_insights.get("top_jobs") or StatisticsService().get_top_jobs(
        jobs=[job.model_dump() for job in jobs],
        top_n=3,
    )

    return MarketInsights(
        total_jobs=len(jobs),
        avg_salary_range=avg_salary_range,
        top_skills=top_skills[:10],
        top_companies=top_companies,
        experience_distribution=market_insights.get("experience_distribution", {}) or {},
        location_distribution=dict(location_counts),
        sample_overview=market_insights.get("sample_overview", {}) or {},
        trend_analysis=market_insights.get("trend_analysis", {}) or {},
        salary_analysis=market_insights.get("salary_analysis", {}) or {},
        competition_intensity=market_insights.get("competition_intensity", {}) or {},
        skill_profile=market_insights.get("skill_profile", {}) or {},
        employer_profile=market_insights.get("employer_profile", {}) or {},
        top_jobs=top_jobs if isinstance(top_jobs, dict) else {},
        report_meta=(graph_result.get("processed_data", {}) or {}).get("report_meta", {}) or {},
        report_sections=(graph_result.get("processed_data", {}) or {}).get("report_sections", {}) or {},
    )


def _build_mock_analyze_response(query: str, location: Optional[str], max_results: int) -> AnalyzeResponse:
    """构建原有 mock 分析响应，作为失败兜底。"""
    result_jobs = _build_mock_search_jobs(query=query, location=location, max_results=max_results)
    top_jobs = StatisticsService().get_top_jobs(jobs=[job.model_dump() for job in result_jobs], top_n=3)

    insights = MarketInsights(
        total_jobs=len(result_jobs),
        avg_salary_range="$140,000 - $170,000",
        top_skills=["Python", "PyTorch", "TensorFlow", "AWS", "Docker"],
        top_companies=["TechCorp Melbourne", "DataDriven Inc", "Innovation Labs"],
        experience_distribution={"Senior": 2, "Mid-Senior": 1},
        location_distribution={"Melbourne, VIC": 1, "Sydney, NSW": 1, "Remote": 1},
        top_jobs=top_jobs,
    )

    report = f"""# {query} 市场分析报告

## 概览
共找到 {len(result_jobs)} 个相关职位。

## 薪资范围
平均薪资范围: {insights.avg_salary_range}

## 热门技能
{chr(10).join(f"- {skill}" for skill in insights.top_skills)}

## 经验分布
{chr(10).join(f"- {level}: {count} 个职位" for level, count in insights.experience_distribution.items())}

## 建议
当前市场对 {query} 需求较高，建议重点关注 Python 和机器学习相关技能。
"""

    return AnalyzeResponse(
        market_insights=insights,
        jobs=result_jobs,
        report=report,
    )


def _attach_report_meta(
    insights: MarketInsights,
    query: str,
    location: Optional[str],
    max_results: int,
    report_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> MarketInsights:
    """为市场洞察补充报告元信息。"""
    meta = dict(insights.report_meta or {})
    meta.update(
        {
            "query": query,
            "location": location or "",
            "max_results": int(max_results),
            "generated_at": created_at or datetime.now().isoformat(timespec="seconds"),
        }
    )
    if report_id:
        meta["report_id"] = report_id

    return insights.model_copy(update={"report_meta": meta})


# ==================== 新版 API 端点 ====================

@router.post(
    "/jobs/search",
    response_model=JobSearchResponse,
    summary="搜索职位",
    description="根据查询条件搜索职位列表",
)
async def search_jobs(request: SearchRequest) -> JobSearchResponse:
    """搜索职位端点
    
    Args:
        request: 搜索请求，包含查询关键词、地点和最大结果数
        
    Returns:
        JobSearchResponse: 包含职位列表、总数和查询信息
        
    Note:
        优先调用 LangGraph 的 job_fetcher_node，失败时回落到 mock 数据
    """
    logger.info(f"搜索职位: query={request.query}, location={request.location}, max_results={request.max_results}")
    
    try:
        result_jobs: list[JobListing] = []

        if _is_paid_api_enabled():
            state = {
                "query": _format_query(request.query, request.location),
                "job_listings": [],
                "analysis_results": [],
                "errors": [],
            }
            fetch_result = await job_fetcher_node(state)
            result_jobs = _convert_state_jobs_to_api_jobs(
                fetch_result.get("job_listings", []),
                request.max_results,
            )
            if fetch_result.get("errors"):
                logger.warning(f"job_fetcher_node 返回错误: {fetch_result['errors']}")
        else:
            logger.info("ENABLE_PAID_APIS 未开启，跳过真实抓取流程，使用 mock fallback")

        if not result_jobs:
            result_jobs = _build_mock_search_jobs(
                query=request.query,
                location=request.location,
                max_results=request.max_results,
            )

        logger.info(f"找到 {len(result_jobs)} 个职位")

        return JobSearchResponse(jobs=result_jobs, total=len(result_jobs), query=request.query)
        
    except Exception as e:
        logger.error(f"搜索职位失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"搜索失败: {str(e)}"
        )


@router.get(
    "/jobs/{job_id}",
    response_model=JobDetailResponse,
    summary="获取职位详情",
    description="根据职位ID获取详细信息，包括分析结果",
    responses={
        404: {"model": ErrorResponse, "description": "职位未找到"}
    }
)
async def get_job(job_id: str) -> JobDetailResponse:
    """获取单个职位详情
    
    Args:
        job_id: 职位唯一标识
        
    Returns:
        JobDetailResponse: 职位详情，包含分析结果
        
    Raises:
        HTTPException: 404 如果职位不存在
    """
    logger.info(f"获取职位详情: job_id={job_id}")
    
    job = MOCK_JOBS.get(job_id)
    if not job:
        logger.warning(f"职位未找到: job_id={job_id}")
        raise HTTPException(
            status_code=404,
            detail=f"职位未找到: {job_id}"
        )
    
    # 获取分析结果
    analysis = MOCK_ANALYSES.get(job_id)
    
    return JobDetailResponse(
        **job.model_dump(),
        analysis=analysis,
    )


@router.get(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="市场分析",
    description="根据搜索条件分析就业市场并生成报告",
)
async def analyze_market(
    query: str = Query(..., description="搜索关键词"),
    location: Optional[str] = Query(None, description="工作地点"),
    max_results: int = Query(default=20, ge=1, le=100, description="最大结果数"),
) -> AnalyzeResponse:
    """市场分析端点
    
    Args:
        query: 搜索关键词
        location: 可选的地点过滤
        max_results: 最大返回结果数
        
    Returns:
        AnalyzeResponse: 包含市场洞察、职位列表和分析报告
        
    Note:
        优先调用 LangGraph 完整流程，失败时回落到 mock 数据
    """
    logger.info(f"市场分析: query={query}, location={location}, max_results={max_results}")
    
    try:
        db_service = get_database_service()
        response_payload: Optional[AnalyzeResponse] = None

        if _is_paid_api_enabled():
            app = get_compiled_graph()
            initial_state = {
                "query": _format_query(query, location),
                "job_listings": [],
                "analysis_results": [],
                "errors": [],
            }
            graph_result = await app.ainvoke(initial_state)

            result_jobs = _convert_state_jobs_to_api_jobs(
                graph_result.get("job_listings", []),
                max_results,
            )
            if result_jobs:
                insights = _build_market_insights_from_graph(result_jobs, graph_result)
                report = graph_result.get("report", "") or f"# {query} 市场分析报告\n\n暂无详细报告。"
                response_payload = AnalyzeResponse(
                    market_insights=insights,
                    jobs=result_jobs,
                    report=report,
                )
                logger.info(f"市场分析完成（LangGraph）: {len(result_jobs)} 个职位")

            if not response_payload:
                logger.warning("LangGraph 未返回职位数据，切换到 mock fallback")
        else:
            logger.info("ENABLE_PAID_APIS 未开启，跳过 LangGraph 真实流程，使用 mock fallback")

        if not response_payload:
            response_payload = _build_mock_analyze_response(
                query=query,
                location=location,
                max_results=max_results,
            )
            logger.info(f"市场分析完成（mock fallback）: {len(response_payload.jobs)} 个职位")

        report_id = db_service.save_report(
            query=query,
            location=location,
            max_results=max_results,
            report=response_payload.report,
            market_insights=response_payload.market_insights.model_dump(),
            jobs=[job.model_dump() for job in response_payload.jobs],
        )
        response_payload.market_insights = _attach_report_meta(
            insights=response_payload.market_insights,
            query=query,
            location=location,
            max_results=max_results,
            report_id=report_id,
        )
        return response_payload
        
    except Exception as e:
        logger.error(f"市场分析失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"分析失败: {str(e)}"
        )


@router.get(
    "/reports",
    response_model=ReportListResponse,
    summary="查询历史报告",
    description="按时间倒序返回已保存的市场分析报告摘要",
)
async def list_reports(
    limit: int = Query(default=20, ge=1, le=100, description="返回条数"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
) -> ReportListResponse:
    """历史报告列表端点。"""
    db_service = get_database_service()
    reports = db_service.list_reports(limit=limit, offset=offset)
    total = db_service.count_reports()
    return ReportListResponse(
        total=total,
        reports=[ReportSummary(**item) for item in reports],
    )


@router.get(
    "/reports/{report_id}",
    response_model=ReportDetailResponse,
    summary="查看报告详情",
    description="根据报告 ID 返回完整报告内容和市场洞察",
    responses={404: {"model": ErrorResponse, "description": "报告不存在"}},
)
async def get_report_detail(report_id: str) -> ReportDetailResponse:
    """报告详情端点。"""
    db_service = get_database_service()
    report_data = db_service.get_report(report_id)
    if not report_data:
        raise HTTPException(status_code=404, detail=f"报告不存在: {report_id}")

    insights = _attach_report_meta(
        insights=MarketInsights(**(report_data.get("market_insights") or {})),
        query=report_data["query"],
        location=report_data.get("location"),
        max_results=report_data["max_results"],
        report_id=report_data["id"],
        created_at=report_data.get("created_at"),
    )

    jobs = [
        JobListing(**item)
        for item in (report_data.get("jobs") or [])
        if isinstance(item, dict)
    ]

    return ReportDetailResponse(
        id=report_data["id"],
        query=report_data["query"],
        location=report_data.get("location", ""),
        max_results=report_data["max_results"],
        created_at=report_data.get("created_at", ""),
        market_insights=insights,
        jobs=jobs,
        report=report_data.get("report", ""),
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="健康检查",
    description="检查 API 服务状态",
)
async def health_check() -> HealthResponse:
    """健康检查端点
    
    Returns:
        HealthResponse: 服务状态信息
    """
    return HealthResponse(status="ok", version="0.1.0")


# ==================== 旧版兼容端点 ====================

@router.post("/search", response_model=SearchResponse, deprecated=True)
async def create_search(params: SearchParams):
    """触发搜索流程（旧版，已弃用）"""
    logger.warning("使用了已弃用的 /search 端点")
    return SearchResponse(
        search_id="placeholder",
        status="pending",
        message="请使用 /jobs/search 端点",
    )


@router.get("/search/{search_id}/status", response_model=StatusResponse, deprecated=True)
async def get_status(search_id: str):
    """获取搜索状态（旧版，已弃用）"""
    logger.warning("使用了已弃用的 /search/{search_id}/status 端点")
    return StatusResponse(
        search_id=search_id,
        stage="pending",
        progress=0,
        message="请使用 /jobs/search 和 /analyze 端点",
    )
