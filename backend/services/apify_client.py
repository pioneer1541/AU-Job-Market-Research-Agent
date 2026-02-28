"""
Apify API 客户端

用于与 Apify Web Scraper API 交互的异步客户端。
"""
import os
import asyncio
import logging
import json
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


class ApifyError(Exception):
    """Apify API 错误基类"""
    pass


class ApifyRateLimitError(ApifyError):
    """API 速率限制错误"""
    pass


# Seek 搜索页面的 Page Function (在浏览器中执行)
# 使用更通用的选择器来提取职位数据
SEEK_PAGE_FUNCTION = """
async function pageFunction(context) {
    const $ = context.jQuery;
    const results = [];
    
    context.log.info('Page URL: ' + context.request.url);
    context.log.info('Page title: ' + $('title').text());
    
    // 等待页面加载
    await context.waitFor(3000);
    
    // 尝试多种选择器
    let jobCards = $('article[data-job-id]');
    context.log.info('Found ' + jobCards.length + ' article[data-job-id]');
    
    if (jobCards.length === 0) {
        jobCards = $('article');
        context.log.info('Found ' + jobCards.length + ' article elements');
    }
    
    if (jobCards.length === 0) {
        jobCards = $('[data-automation="job-list-item"]');
        context.log.info('Found ' + jobCards.length + ' [data-automation="job-list-item"]');
    }
    
    if (jobCards.length === 0) {
        jobCards = $('a[href*="/job/"]');
        context.log.info('Found ' + jobCards.length + ' a[href*="/job/"]');
    }
    
    // 如果还是没有找到，尝试提取整个页面的文本用于调试
    if (jobCards.length === 0) {
        context.log.warning('No job cards found, returning page info for debugging');
        return [{
            id: 'debug',
            title: 'Debug - Page Structure',
            company: 'N/A',
            location: 'N/A',
            salary: null,
            description: $('body').text().substring(0, 2000),
            url: context.request.url,
            posted_date: null,
            source: 'seek',
            debug: true
        }];
    }
    
    for (let i = 0; i < jobCards.length && i < 20; i++) {
        const card = $(jobCards[i]);
        
        try {
            // 尝试多种方式获取职位 ID
            let jobId = card.attr('data-job-id') || 
                       card.find('[data-job-id]').attr('data-job-id') || '';
            
            // 如果是链接元素，从 href 提取
            if (!jobId && card.is('a')) {
                const href = card.attr('href') || '';
                const match = href.match(/job\\/(\\d+)/);
                if (match) jobId = match[1];
            }
            
            // 获取职位标题
            let title = card.find('h1, h2, h3, [data-automation="jobTitle"], [data-automation="jobListTitle"]').first().text().trim() ||
                       card.find('a[role="link"], span[role="link"]').first().text().trim() ||
                       card.text().trim().split('\\n')[0].substring(0, 100);
            
            // 获取公司名称
            const company = card.find('[data-automation="jobCompany"], [data-automation="companyName"], [data-automation="advertiserName"]').text().trim() ||
                           card.find('span, div').filter(function() {
                               const text = $(this).text().trim();
                               return text.length > 2 && text.length < 100 && 
                                      !$(this).find('span, div').length &&
                                      /^[A-Z]/.test(text);
                           }).first().text().trim() || 'Unknown';
            
            // 获取职位链接
            const jobLink = card.find('a[href*="/job/"]').first().attr('href') || 
                           (card.is('a') ? card.attr('href') : '') || '';
            const url = jobLink.startsWith('http') ? jobLink : 
                        (jobLink ? 'https://www.seek.com.au' + jobLink : '');
            
            // 获取位置
            const location = card.find('[data-automation="jobLocation"], [data-automation="jobDetailLocation"]').text().trim() ||
                             card.find('span, div').filter(function() {
                                 const text = $(this).text().trim();
                                 return text.includes('VIC') || text.includes('NSW') || 
                                        text.includes('QLD') || text.includes('Melbourne') ||
                                        text.includes('Sydney') || text.includes('Brisbane');
                             }).first().text().trim() || 'Unknown';
            
            // 获取薪资
            const salary = card.find('[data-automation="jobSalary"], [data-automation="jobDetailSalary"]').text().trim() ||
                           card.find('span, div').filter(function() {
                               const text = $(this).text().trim();
                               return text.includes('$') || text.includes('k') && text.includes('-');
                           }).first().text().trim() || null;
            
            // 获取描述
            const description = card.find('[data-automation="jobShortDescription"]').text().trim() ||
                               card.find('p, span').filter(function() {
                                   return $(this).text().trim().length > 30;
                               }).first().text().trim().substring(0, 300) || 'No description';
            
            // 如果没有 ID，生成一个临时 ID
            if (!jobId && url) {
                const match = url.match(/job\\/(\\d+)/);
                if (match) jobId = match[1];
            }
            
            if (title && (jobId || url)) {
                results.push({
                    id: String(jobId || 'temp-' + i),
                    title: title,
                    company: company,
                    location: location,
                    salary: salary,
                    description: description,
                    url: url || context.request.url,
                    posted_date: null,
                    source: 'seek'
                });
                
                context.log.info('Extracted job: ' + title + ' @ ' + company);
            }
        } catch (e) {
            context.log.warning('Error parsing job card: ' + e.message);
        }
    }
    
    context.log.info('Total extracted: ' + results.length + ' jobs');
    return results;
}
"""


class ApifyClient:
    """
    Apify API 异步客户端
    
    用于调用 Apify Web Scraper 获取职位数据。
    """
    
    BASE_URL = "https://api.apify.com/v2"
    # 使用 Web Scraper actor (注意: Apify API 使用 ~ 分隔符)
    WEB_SCRAPER_ACTOR_ID = "apify~web-scraper"
    
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
            max_items: 最大获取数量
            **kwargs: 其他 Scraper 参数
            
        Returns:
            职位数据列表
            
        Raises:
            ApifyError: API 调用失败
            ApifyRateLimitError: 触发速率限制
        """
        # 构建搜索 URL
        search_url = f"https://www.seek.com.au/jobs?keywords={search_query}"
        if location:
            search_url += f"&where={location}"
        
        # 构建输入参数 - Web Scraper 格式
        run_input = {
            "startUrls": [{"url": search_url}],
            "linkSelector": "",  # 空字符串表示不跟随链接
            "globs": [],
            "pseudoUrls": [],
            "pageFunction": SEEK_PAGE_FUNCTION,
            "maxPagesPerCrawl": 1,
            "maxResultRecords": max_items,
            "proxyConfiguration": {"useApifyProxy": True},
            "injectJQuery": True,
            "waitUntil": ["networkidle2"],
        }
        
        logger.info(f"启动 Web Scraper: query={search_query}, location={location}, maxItems={max_items}")
        logger.info(f"搜索 URL: {search_url}")
        
        # 运行 Actor
        run_id = await self._start_actor_run(run_input)
        
        # 等待完成
        dataset_id = await self._wait_for_completion(run_id)
        
        # 获取结果
        results = await self._fetch_dataset_items(dataset_id)
        
        logger.info(f"Web Scraper 完成，获取 {len(results)} 条职位数据")
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
    
    async def _start_actor_run(self, run_input: dict, actor_id: str = None) -> str:
        """
        启动 Actor 运行
        
        Args:
            run_input: Actor 输入参数
            actor_id: Actor ID，默认使用 Web Scraper
            
        Returns:
            运行 ID
        """
        actor_id = actor_id or self.WEB_SCRAPER_ACTOR_ID
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
                logger.error(f"Actor 日志:\\n{logs[-2000:]}")  # 最后 2000 字符
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
        
        Args:
            raw_job: Apify 返回的原始职位数据
            
        Returns:
            标准化的 JobListing 对象
        """
        # 检查是否是 Web Scraper 返回的已处理格式
        # 已处理格式有: id, title, company (直接字段), source
        is_processed = (
            "source" in raw_job or
            ("company" in raw_job and isinstance(raw_job.get("company"), str))
        )
        
        if is_processed:
            # 已经是处理过的格式
            job_id = str(raw_job.get("id", ""))
            return JobListing(
                id=job_id,
                title=raw_job.get("title", "Untitled"),
                company=raw_job.get("company", "Unknown"),
                location=raw_job.get("location", "Unknown"),
                salary=raw_job.get("salary"),
                description=raw_job.get("description", "No description"),
                url=raw_job.get("url") or f"https://www.seek.com.au/job/{job_id}",
                source="seek",
                posted_date=raw_job.get("posted_date"),
            )
        
        # 尝试解析原始 Seek API 格式
        # 解析公司名称
        company = (
            (raw_job.get("companyProfile") or {}).get("name") or
            (raw_job.get("advertiser") or {}).get("name") or
            raw_job.get("company") or  # 可能是直接的字符串
            "Unknown"
        )
        
        # 解析职位描述
        content = raw_job.get("content") or {}
        description_parts = []
        
        # 添加 bullet points
        bullet_points = content.get("bulletPoints") or []
        if bullet_points:
            description_parts.append("Key Skills:\n" + "\n".join(f"- {bp}" for bp in bullet_points))
        
        # 添加 sections
        sections = content.get("sections") or []
        for section in sections:
            section_title = section.get("title", "")
            section_content = section.get("content", "")
            if section_title and section_content:
                description_parts.append(f"\n{section_title}:\n{section_content}")
        
        description = "\n".join(description_parts) or raw_job.get("description") or "No description available"
        
        # 解析发布日期
        posted_date = raw_job.get("listedAt") or raw_job.get("posted_date")
        if posted_date:
            try:
                datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                posted_date = None
        
        # 生成 URL
        job_id = str(raw_job.get("id", ""))
        url = raw_job.get("url") or f"https://www.seek.com.au/job/{job_id}"
        
        return JobListing(
            id=job_id,
            title=raw_job.get("title", "Untitled"),
            company=company,
            location=raw_job.get("location", "Unknown"),
            salary=raw_job.get("salary"),
            description=description,
            url=url,
            source="seek",
            posted_date=posted_date,
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
