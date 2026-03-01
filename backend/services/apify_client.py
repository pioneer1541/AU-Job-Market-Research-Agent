"""
Apify API 客户端

用于与 Apify Seek Job Scraper API 交互的异步客户端。
"""
import os
import asyncio
import logging
import json
import re
from typing import Optional, Any, TypedDict
from datetime import datetime

import httpx


logger = logging.getLogger(__name__)


class JobListing(TypedDict):
    """Single job listing data structure"""
    id: str
    title: str
    company: str
    location: str
    salary: Optional[str]
    description: str
    url: str
    source: str
    posted_date: Optional[str]
    num_applicants: Optional[int]


class ApifyError(Exception):
    """Apify API 错误基类"""
    pass


class ApifyRateLimitError(ApifyError):
    """API 速率限制错误"""
    pass


def clean_salary(salary: str | None) -> str | None:
    """
    清洗薪资字段，提取标准格式
    
    支持格式:
    - $xxx 或 $xxxk
    - $xxx - $xxx 或 $xxxk - $xxxk (hyphen 或 en-dash)
    - $xxx to $xxx
    - AUD xxx - xxx per annum
    
    如果薪资字段包含换行或过长，返回 None
    
    Args:
        salary: 原始薪资字符串
        
    Returns:
        清洗后的薪资格式字符串，或 None
    """
    if not salary:
        return None
    
    # 如果包含换行符，说明格式混乱，返回 None
    if "\n" in salary or "\r" in salary:
        return None
    
    # 如果过长（超过50字符），可能包含其他信息，返回 None
    if len(salary) > 50:
        return None
    
    # 如果是 N/A 或类似的无意义值，返回 None
    if salary.upper() in ("N/A", "NA", "NONE", "TBD"):
        return None
    
    # 尝试匹配标准薪资格式
    # 支持 hyphen (-) 和 en-dash (–) 以及 em-dash (—)
    dash_pattern = r"[-–—]"
    
    # 格式1: $xxx - $xxx 或 $xxxk - $xxxk (支持各种 dash)
    range_pattern = rf"\$[\d,]+(?:k|K)?\s*{dash_pattern}\s*\$?[\d,]+(?:k|K)?"
    
    # 格式2: AUD xxx - xxx per annum
    aud_pattern = rf"AUD\s*[\d,]+\s*{dash_pattern}\s*[\d,]+(?:\s+per\s+annum)?"
    
    # 格式3: $xxx 或 $xxxk (单个数字)
    single_pattern = r"\$[\d,]+"
    
    # 格式4: xxx - xxx p.d. (daily rate)
    daily_pattern = rf"[\d,]+\s*{dash_pattern}\s*\$?[\d,]+k?\s*p\.d\."
    
    # 优先匹配范围格式
    range_match = re.search(range_pattern, salary, re.IGNORECASE)
    if range_match:
        return range_match.group(0).strip()
    
    # 匹配 AUD 格式
    aud_match = re.search(aud_pattern, salary, re.IGNORECASE)
    if aud_match:
        return aud_match.group(0).strip()
    
    # 匹配 daily rate
    daily_match = re.search(daily_pattern, salary, re.IGNORECASE)
    if daily_match:
        return daily_match.group(0).strip()
    
    # 其次匹配单个数字
    single_match = re.search(single_pattern, salary)
    if single_match:
        return single_match.group(0).strip()
    
    # 如果都不匹配，返回 None
    return None


class ApifyClient:
    """
    Apify API 异步客户端
    
    用于调用 Apify Seek Job Scraper 获取职位数据。
    """
    
    BASE_URL = "https://api.apify.com/v2"
    # 使用 websift/seek-job-scraper actor (注意: Apify API 使用 ~ 分隔符)
    SEEK_SCRAPER_ACTOR_ID = "websift~seek-job-scraper"
    
    def __init__(self, api_token: Optional[str] = None):
        """
        初始化 Apify 客户端
        
        Args:
            api_token: Apify API Token，如果不提供则从环境变量读取
        """
        self.api_token = api_token or os.getenv("APIFY_API_TOKEN")
        if not self.api_token:
            raise ApifyError("APIFY_API_TOKEN 未设置，请在环境变量中配置或传入 api_token 参数")
        
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "ApifyClient":
        """异步上下文管理器入口"""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(180.0, connect=30.0),
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if not self._client:
            raise ApifyError("客户端未初始化，请使用 async with 语句")
        return self._client
    
    async def run_seek_scraper(
        self,
        search_query: str,
        location: Optional[str] = None,
        max_items: int = 50,
        **kwargs
    ) -> list[dict[str, Any]]:
        """
        运行 Seek Scraper 并获取职位数据
        
        Args:
            search_query: 搜索关键词（职位名称）
            location: 工作地点
            max_items: 最大获取数量 (10-550)
            **kwargs: 其他 Scraper 参数
                - dateRange: 时间范围（天数）
                - sortBy: 排序方式 ("date" 或 "relevance")
                - salaryMin: 最低薪资
                - salaryMax: 最高薪资
                - workTypes: 工作类型列表
                - workArrangements: 工作安排列表
                
        Returns:
            职位数据列表
            
        Raises:
            ApifyError: API 调用失败
            ApifyRateLimitError: 触发速率限制
        """
        # 构建输入参数 - websift/seek-job-scraper 格式
        run_input = {
            "searchTerm": search_query,
            "maxResults": min(max(10, max_items), 550),  # 限制在 10-550 范围内
        }
        
        # 添加可选参数
        if location:
            run_input["location"] = location
        
        # 传递其他 kwargs 参数
        for key in ["dateRange", "sortBy", "salaryType", "salaryMin", "salaryMax", 
                    "workTypes", "workArrangements", "state", "postCode", "radius"]:
            if key in kwargs:
                run_input[key] = kwargs[key]
        
        logger.info(f"启动 Seek Scraper: query={search_query}, location={location}, maxResults={run_input['maxResults']}")
        
        # 运行 Actor
        run_id = await self._start_actor_run(run_input, self.SEEK_SCRAPER_ACTOR_ID)
        
        # 等待完成
        dataset_id = await self._wait_for_completion(run_id)
        
        # 获取结果
        results = await self._fetch_dataset_items(dataset_id)
        
        logger.info(f"Seek Scraper 完成，获取 {len(results)} 条职位数据")
        return results
    
    async def get_run_logs(self, run_id: str) -> str:
        """获取 Actor 运行日志"""
        url = f"{self.BASE_URL}/actor-runs/{run_id}/log"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.warning(f"获取日志失败: {e}")
            return ""
    
    async def _start_actor_run(self, run_input: dict, actor_id: str) -> str:
        """
        启动 Actor 运行
        
        Args:
            run_input: Actor 输入参数
            actor_id: Actor ID
            
        Returns:
            运行 ID
        """
        url = f"{self.BASE_URL}/acts/{actor_id}/runs"
        
        try:
            response = await self.client.post(url, json=run_input)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise ApifyRateLimitError("触发 Apify API 速率限制") from e
            error_detail = e.response.text[:500]
            raise ApifyError(f"启动 Actor 失败: {e.response.status_code} - {error_detail}") from e
        except httpx.RequestError as e:
            raise ApifyError(f"网络请求失败: {e}") from e
        
        data = response.json()
        run_id = data["data"]["id"]
        logger.info(f"Actor 运行已启动: {run_id}")
        return run_id
    
    async def _wait_for_completion(
        self,
        run_id: str,
        poll_interval: float = 5.0,
        max_wait: float = 600.0
    ) -> str:
        """
        等待 Actor 运行完成
        
        Args:
            run_id: 运行 ID
            poll_interval: 轮询间隔（秒）
            max_wait: 最大等待时间（秒）
            
        Returns:
            Dataset ID
            
        Raises:
            ApifyError: 运行失败或超时
        """
        url = f"{self.BASE_URL}/actor-runs/{run_id}"
        start_time = datetime.now()
        
        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > max_wait:
                raise ApifyError(f"Actor 运行超时 ({max_wait}秒)")
            
            try:
                response = await self.client.get(url)
                response.raise_for_status()
            except httpx.RequestError as e:
                raise ApifyError(f"获取运行状态失败: {e}") from e
            
            data = response.json()["data"]
            status = data.get("status")
            stats = data.get("stats", {})
            
            logger.info(f"Actor 状态: {status}, 已运行: {stats.get('durationMillis', 0)/1000:.1f}秒")
            
            if status == "SUCCEEDED":
                logger.info(f"Actor 运行成功: {run_id}")
                return data.get("defaultDatasetId")
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                error_msg = data.get("statusMessage", "未知错误")
                # 获取日志
                logs = await self.get_run_logs(run_id)
                logger.error(f"Actor 日志:\n{logs[-2000:]}")  # 最后 2000 字符
                raise ApifyError(f"Actor 运行失败: {status} - {error_msg}")
            
            # 等待后继续轮询
            await asyncio.sleep(poll_interval)
    
    async def _fetch_dataset_items(self, dataset_id: str) -> list[dict[str, Any]]:
        """
        获取 Dataset 中的数据项
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            数据项列表
        """
        url = f"{self.BASE_URL}/datasets/{dataset_id}/items"
        
        try:
            response = await self.client.get(url, params={"clean": "true"})
            response.raise_for_status()
        except httpx.RequestError as e:
            raise ApifyError(f"获取 Dataset 数据失败: {e}") from e
        
        return response.json()
    
    @staticmethod
    def parse_to_job_listing(raw_job: dict[str, Any]) -> JobListing:
        """
        将 Apify 原始数据转换为 JobListing 格式
        
        websift/seek-job-scraper 输出格式:
        {
            "id": "86136632",
            "jobLink": "https://www.seek.com.au/job/86136632",
            "title": "Senior Software Engineer",
            "salary": "Daily rates up to $1,100!",
            "workTypes": "Contract/Temp",
            "workArrangements": "Remote",
            "joblocationInfo": {"location": "Sydney", "displayLocation": "Sydney NSW"},
            "advertiser": {"name": "Company Name"},
            "companyProfile": {"name": "Company Name"},
            "content": {"bulletPoints": [...], "unEditedContent": "..."},
            "listedAt": "2025-07-30T23:46:54.688Z"
        }
        
        Args:
            raw_job: Apify 返回的原始职位数据
            
        Returns:
            标准化的 JobListing 对象
        """
        # 解析职位 ID
        job_id = str(raw_job.get("id", ""))
        
        # 解析职位标题
        title = raw_job.get("title", "Untitled")
        
        # 解析公司名称 - 优先使用 advertiser.name, 其次 companyProfile.name
        advertiser = raw_job.get("advertiser") or {}
        company_profile = raw_job.get("companyProfile") or {}
        company = (
            advertiser.get("name") or
            company_profile.get("name") or
            raw_job.get("company") or
            "Unknown"
        )
        
        # 解析位置
        location_info = raw_job.get("joblocationInfo") or {}
        location = (
            location_info.get("displayLocation") or
            location_info.get("location") or
            raw_job.get("location") or
            "Unknown"
        )
        
        # 解析薪资 - 清洗后
        raw_salary = raw_job.get("salary")
        salary = clean_salary(raw_salary)
        
        # 解析 URL
        url = raw_job.get("jobLink") or raw_job.get("url") or f"https://www.seek.com.au/job/{job_id}"
        
        # 解析描述 - 从 content 字段提取
        content = raw_job.get("content") or {}
        description_parts = []
        
        # 添加 bullet points
        bullet_points = content.get("bulletPoints") or []
        if bullet_points:
            description_parts.append("Key Points:\n" + "\n".join(f"- {bp}" for bp in bullet_points[:5]))
        
        # 添加 job hook (简短描述)
        job_hook = content.get("jobHook") or ""
        if job_hook:
            description_parts.insert(0, job_hook)
        
        # 添加 sections
        sections = content.get("sections") or []
        if sections:
            # 只取前几个 section，避免描述过长
            description_parts.append("\n".join(sections[:3]))
        
        # 如果没有任何描述，使用 unEditedContent 的前 500 字符
        if not description_parts:
            unedited = content.get("unEditedContent") or ""
            if unedited:
                # 移除 HTML 标签
                clean_text = re.sub(r'<[^>]+>', '', unedited)
                description_parts.append(clean_text[:500])
        
        description = "\n\n".join(description_parts) or "No description available"
        
        # 解析发布日期
        posted_date = raw_job.get("listedAt") or raw_job.get("posted_date")
        if posted_date:
            try:
                datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                posted_date = None

        # 解析申请人数（Seek 字段通常为 numApplicants）
        num_applicants = raw_job.get("numApplicants")
        try:
            num_applicants = int(num_applicants) if num_applicants is not None else None
        except (TypeError, ValueError):
            num_applicants = None

        return JobListing(
            id=job_id,
            title=title,
            company=company,
            location=location,
            salary=salary,
            description=description,
            url=url,
            source="seek",
            posted_date=posted_date,
            num_applicants=num_applicants,
        )


# 便捷函数
async def fetch_jobs_from_seek(
    query: str,
    location: Optional[str] = None,
    max_items: int = 50
) -> list[JobListing]:
    """
    从 Seek 获取职位的便捷函数
    
    Args:
        query: 搜索关键词
        location: 工作地点
        max_items: 最大获取数量
        
    Returns:
        标准化的职位列表
    """
    async with ApifyClient() as client:
        raw_jobs = await client.run_seek_scraper(query, location, max_items)
        return [ApifyClient.parse_to_job_listing(job) for job in raw_jobs]
