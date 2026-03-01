"""API route definitions.
API 路由定义
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from backend.api.schemas import (
    SearchRequest,
    JobSearchResponse,
    JobListing,
    JobDetailResponse,
    JobAnalysis,
    AnalyzeResponse,
    MarketInsights,
    HealthResponse,
    ErrorResponse,
    # 旧版兼容
    SearchParams,
    SearchResponse,
    StatusResponse,
)

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
        当前返回 mock 数据，后续会接入真实 API
    """
    logger.info(f"搜索职位: query={request.query}, location={request.location}, max_results={request.max_results}")
    
    try:
        # TODO: 接入真实的 Apify API
        # 当前使用 mock 数据
        all_jobs = list(MOCK_JOBS.values())
        
        # 简单过滤：根据查询关键词过滤标题
        query_lower = request.query.lower()
        filtered_jobs = [
            job for job in all_jobs
            if query_lower in job.title.lower() or query_lower in job.description.lower()
        ]
        
        # 如果指定了地点，进一步过滤
        if request.location:
            location_lower = request.location.lower()
            filtered_jobs = [
                job for job in filtered_jobs
                if location_lower in job.location.lower()
            ]
        
        # 限制结果数量
        result_jobs = filtered_jobs[:request.max_results]
        
        logger.info(f"找到 {len(result_jobs)} 个职位")
        
        return JobSearchResponse(
            jobs=result_jobs,
            total=len(result_jobs),
            query=request.query,
        )
        
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
        当前使用 mock 数据，后续会接入真实分析流程
    """
    logger.info(f"市场分析: query={query}, location={location}, max_results={max_results}")
    
    try:
        # TODO: 接入真实的分析流程
        # 当前使用 mock 数据
        
        # 获取职位列表
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
        
        result_jobs = filtered_jobs[:max_results]
        
        # 生成市场洞察
        insights = MarketInsights(
            total_jobs=len(result_jobs),
            avg_salary_range="$140,000 - $170,000",
            top_skills=["Python", "PyTorch", "TensorFlow", "AWS", "Docker"],
            top_companies=["TechCorp Melbourne", "DataDriven Inc", "Innovation Labs"],
            experience_distribution={"Senior": 2, "Mid-Senior": 1},
            location_distribution={"Melbourne, VIC": 1, "Sydney, NSW": 1, "Remote": 1},
        )
        
        # 生成报告
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
        
        logger.info(f"市场分析完成: {len(result_jobs)} 个职位")
        
        return AnalyzeResponse(
            market_insights=insights,
            jobs=result_jobs,
            report=report,
        )
        
    except Exception as e:
        logger.error(f"市场分析失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"分析失败: {str(e)}"
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
