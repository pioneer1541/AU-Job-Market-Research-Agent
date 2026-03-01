"""Pydantic schemas for API request/response models.
请求和响应模型定义
"""

from typing import Optional
from pydantic import BaseModel, Field


# ==================== Job 相关模型 ====================

class JobListing(BaseModel):
    """职位信息模型"""
    id: str = Field(..., description="职位唯一标识")
    title: str = Field(..., description="职位标题")
    company: str = Field(..., description="公司名称")
    location: str = Field(..., description="工作地点")
    salary: Optional[str] = Field(None, description="薪资范围")
    description: str = Field(default="", description="职位描述")
    url: str = Field(default="", description="职位链接")
    source: str = Field(default="unknown", description="数据来源")
    posted_date: Optional[str] = Field(None, description="发布日期")


class JobAnalysis(BaseModel):
    """职位分析结果"""
    job_id: str = Field(..., description="关联的职位ID")
    skills_required: list[str] = Field(default_factory=list, description="所需技能")
    experience_level: str = Field(default="", description="经验要求")
    salary_estimate: Optional[str] = Field(None, description="薪资估算")
    key_requirements: list[str] = Field(default_factory=list, description="关键要求")
    industry: Optional[str] = Field(None, description="所属行业")


class JobDetailResponse(BaseModel):
    """单个职位详情响应"""
    id: str
    title: str
    company: str
    location: str
    salary: Optional[str] = None
    description: str = ""
    url: str = ""
    source: str = "unknown"
    posted_date: Optional[str] = None
    analysis: Optional[JobAnalysis] = None


# ==================== 搜索相关模型 ====================

class SearchRequest(BaseModel):
    """搜索请求模型"""
    query: str = Field(..., description="搜索关键词", min_length=1)
    location: Optional[str] = Field(None, description="工作地点")
    max_results: int = Field(default=20, description="最大结果数", ge=1, le=100)


class JobSearchResponse(BaseModel):
    """职位搜索响应"""
    jobs: list[JobListing] = Field(default_factory=list, description="职位列表")
    total: int = Field(default=0, description="结果总数")
    query: str = Field(..., description="搜索查询")


# ==================== 分析相关模型 ====================

class MarketInsights(BaseModel):
    """市场洞察模型"""
    total_jobs: int = Field(default=0, description="职位总数")
    avg_salary_range: Optional[str] = Field(None, description="平均薪资范围")
    top_skills: list[str] = Field(default_factory=list, description="热门技能")
    top_companies: list[str] = Field(default_factory=list, description="热门公司")
    experience_distribution: dict[str, int] = Field(default_factory=dict, description="经验分布")
    location_distribution: dict[str, int] = Field(default_factory=dict, description="地点分布")
    sample_overview: dict = Field(default_factory=dict, description="样本概览统计")
    trend_analysis: dict = Field(default_factory=dict, description="职位量趋势分析")
    salary_analysis: dict = Field(default_factory=dict, description="薪资分析与解析")
    competition_intensity: dict = Field(default_factory=dict, description="竞争强度统计")
    skill_profile: dict = Field(default_factory=dict, description="技能提取与画像")
    employer_profile: dict = Field(default_factory=dict, description="雇主分析画像")
    report_meta: dict = Field(default_factory=dict, description="报告元信息")
    report_sections: dict[str, str] = Field(default_factory=dict, description="模块化报告章节")


class AnalyzeResponse(BaseModel):
    """市场分析响应"""
    market_insights: MarketInsights = Field(default_factory=MarketInsights, description="市场洞察")
    jobs: list[JobListing] = Field(default_factory=list, description="职位列表")
    report: str = Field(default="", description="分析报告")


# ==================== 报告历史模型 ====================

class ReportSummary(BaseModel):
    """报告摘要模型"""
    id: str = Field(..., description="报告唯一标识")
    query: str = Field(..., description="查询关键词")
    location: str = Field(default="", description="查询地点")
    max_results: int = Field(..., description="样本上限")
    results_count: int = Field(default=0, description="职位数量")
    created_at: str = Field(..., description="报告生成时间")


class ReportListResponse(BaseModel):
    """报告列表响应模型"""
    total: int = Field(default=0, description="报告总数")
    reports: list[ReportSummary] = Field(default_factory=list, description="报告摘要列表")


class ReportDetailResponse(BaseModel):
    """报告详情响应模型"""
    id: str = Field(..., description="报告唯一标识")
    query: str = Field(..., description="查询关键词")
    location: str = Field(default="", description="查询地点")
    max_results: int = Field(..., description="样本上限")
    created_at: str = Field(..., description="报告生成时间")
    market_insights: MarketInsights = Field(default_factory=MarketInsights, description="市场洞察")
    jobs: list[JobListing] = Field(default_factory=list, description="职位样本")
    report: str = Field(default="", description="完整报告文本")


# ==================== 系统状态模型 ====================

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(default="ok", description="服务状态")
    version: str = Field(default="0.1.0", description="版本号")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细信息")


# ==================== 保留旧模型以兼容 ====================

class SearchParams(BaseModel):
    """参数搜索模型（旧版兼容）"""
    search_term: str = Field(..., description="Job search keyword", min_length=1)
    location: str = Field(default="Melbourne", description="City or location")
    state: Optional[str] = Field(default=None, description="State filter (e.g., VIC)")
    max_results: int = Field(default=200, description="Maximum listings to fetch", ge=10, le=550)
    salary_min: Optional[int] = Field(default=None, description="Minimum salary filter")
    salary_max: Optional[int] = Field(default=None, description="Maximum salary filter")
    work_types: list[str] = Field(default=["Full Time", "Contract"], description="Work types")
    work_arrangements: list[str] = Field(
        default=["On-site", "Hybrid", "Remote"], description="Work arrangements"
    )
    date_range: int = Field(default=30, description="Posting age in days", ge=1, le=365)


class SearchResponse(BaseModel):
    """搜索响应（旧版兼容）"""
    search_id: str
    status: str
    message: Optional[str] = None


class StatusResponse(BaseModel):
    """状态响应（旧版兼容）"""
    search_id: str
    stage: str  # pending, fetching, cleaning, analyzing, generating, completed, failed
    progress: int  # 0-100
    message: Optional[str] = None
