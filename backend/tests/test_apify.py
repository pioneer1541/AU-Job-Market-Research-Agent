"""
Apify 客户端测试

使用 mock 数据进行测试，不会触发真实 API 调用。
"""
import sys
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from services.apify_client import (
    ApifyClient,
    ApifyError,
    ApifyRateLimitError,
    fetch_jobs_from_seek,
    JobListing,
)


# 加载真实的 fixture 数据
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_mock_job_data():
    """加载 mock 职位数据用于测试"""
    # 使用新的 fixture 文件名
    fixture_file = FIXTURES_DIR / "seek_scraper_response.json"
    if fixture_file.exists():
        with open(fixture_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


class TestApifyClient:
    """测试 ApifyClient 类"""
    
    def test_init_with_token(self):
        """测试使用显式 token 初始化"""
        client = ApifyClient(api_token="test-token")
        assert client.api_token == "test-token"
    
    def test_init_without_token_raises_error(self):
        """测试缺少 token 时抛出错误"""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ApifyError, match="APIFY_API_TOKEN 未设置"):
                ApifyClient()
    
    def test_init_with_env_token(self):
        """测试从环境变量读取 token"""
        with patch.dict("os.environ", {"APIFY_API_TOKEN": "env-token"}):
            client = ApifyClient()
            assert client.api_token == "env-token"
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """测试异步上下文管理器"""
        with patch.dict("os.environ", {"APIFY_API_TOKEN": "test-token"}):
            async with ApifyClient() as client:
                # 验证客户端已初始化
                assert client._client is not None
                # 验证可以获取 client 属性
                http_client = client.client
                assert http_client is not None
            
            # 退出后客户端应关闭
            assert client._client is None
    
    def test_parse_to_job_listing_websift_format(self):
        """测试解析 websift/seek-job-scraper 格式的数据"""
        # 使用真实 fixture 数据格式
        raw_job = {
            "id": "90603522",
            "jobLink": "https://www.seek.com.au/job/90603522",
            "title": "Senior AI Engineer",
            "salary": "$140,000 – $160,000 per year",  # en-dash
            "workTypes": "Full time",
            "workArrangements": "Hybrid",
            "joblocationInfo": {
                "displayLocation": "Melbourne VIC",
                "location": "Melbourne",
                "country": "Australia",
                "suburb": "Melbourne"
            },
            "advertiser": {
                "id": "12345",
                "name": "Tech Corp",
                "isVerified": True
            },
            "companyProfile": {
                "id": "67890",
                "name": "Tech Corp",
                "size": "100-500 employees"
            },
            "content": {
                "bulletPoints": [
                    "Great team culture",
                    "Competitive salary",
                    "Flexible working"
                ],
                "jobHook": "Join our AI team!",
                "sections": ["About the role", "Requirements"]
            },
            "listedAt": "2026-02-27T00:32:47.831Z"
        }
        
        result = ApifyClient.parse_to_job_listing(raw_job)
        
        assert result["id"] == "90603522"
        assert result["title"] == "Senior AI Engineer"
        assert result["company"] == "Tech Corp"
        assert result["location"] == "Melbourne VIC"
        # 薪资应该包含 en-dash 格式
        assert result["salary"] is not None
        assert "140,000" in result["salary"]
        assert result["source"] == "seek"
        assert result["url"] == "https://www.seek.com.au/job/90603522"
        assert "Great team culture" in result["description"]
        assert "Join our AI team" in result["description"]
    
    def test_parse_to_job_listing_minimal(self):
        """测试最小数据的解析"""
        raw_job = {
            "id": "999",
            "title": "Junior Developer",
        }
        
        result = ApifyClient.parse_to_job_listing(raw_job)
        
        assert result["id"] == "999"
        assert result["title"] == "Junior Developer"
        assert result["company"] == "Unknown"
        assert result["location"] == "Unknown"
        assert result["salary"] is None
        assert result["source"] == "seek"
        assert "https://www.seek.com.au/job/999" in result["url"]
    
    def test_parse_real_fixture_data(self):
        """测试解析真实 fixture 数据"""
        mock_data = load_mock_job_data()
        if not mock_data:
            pytest.skip("Mock fixture 数据不存在: seek_scraper_response.json")
        
        # 解析所有数据
        results = [ApifyClient.parse_to_job_listing(job) for job in mock_data]
        
        # 验证所有数据都能成功解析
        assert len(results) == len(mock_data)
        
        # 验证第一条数据的关键字段
        first_result = results[0]
        first_raw = mock_data[0]
        
        assert first_result["id"] == first_raw["id"]
        assert first_result["title"] == first_raw["title"]
        assert first_result["source"] == "seek"
        assert first_result["url"] == first_raw["jobLink"]
        
        # 验证公司名称提取
        expected_company = (
            first_raw.get("advertiser", {}).get("name") or
            first_raw.get("companyProfile", {}).get("name") or
            "Unknown"
        )
        assert first_result["company"] == expected_company
    
    def test_salary_cleaning(self):
        """测试薪资字段清洗"""
        from services.apify_client import clean_salary
        
        # 正常范围格式 (en-dash 和 hyphen)
        assert "140,000" in clean_salary("$140,000 – $160,000 per year")  # en-dash
        assert "100k" in clean_salary("$100k - $150k")  # hyphen
        assert "80" in clean_salary("$80 to $120")
        
        # AUD 格式
        aud_salary = clean_salary("AUD 180000 - 220000 per annum")
        assert aud_salary is not None
        assert "AUD" in aud_salary
        
        # Daily rate 格式
        daily_salary = clean_salary("$800 - $1k p.d.")
        assert daily_salary is not None
        
        # 单个数字
        assert clean_salary("$150,000") == "$150,000"
        # 注: clean_salary 只提取第一个匹配的数字部分
        assert "$100" in clean_salary("Around $100k")  # 提取到 $100
        
        # 包含换行符（应返回 None）
        assert clean_salary("$100k\nPlus super") is None
        
        # 过长（应返回 None）
        assert clean_salary("$100k - $150k plus superannuation and bonuses and more info") is None
        
        # 无薪资信息
        assert clean_salary("Competitive salary") is None
        assert clean_salary(None) is None
        
        # N/A 值
        assert clean_salary("N/A") is None
        assert clean_salary("n/a") is None
    
    @pytest.mark.asyncio
    async def test_run_seek_scraper_success(self):
        """测试成功的 Seek Scraper 调用"""
        import httpx
        
        # 使用 mock 数据
        mock_data = load_mock_job_data() or [{"id": "job-1", "title": "Test Job"}]
        
        with patch.dict("os.environ", {"APIFY_API_TOKEN": "test-token"}):
            mock_http_client = MagicMock(spec=httpx.AsyncClient)
            
            # Mock POST (启动 actor)
            mock_http_client.post = AsyncMock()
            mock_http_client.post.return_value = MagicMock(
                status_code=201,
                json=lambda: {"data": {"id": "run-123"}}
            )
            mock_http_client.post.return_value.raise_for_status = MagicMock()
            
            # Mock GET 响应序列
            get_responses = [
                # 轮询状态 - 运行中
                MagicMock(json=lambda: {"data": {"status": "RUNNING"}}),
                # 轮询状态 - 完成
                MagicMock(json=lambda: {
                    "data": {
                        "status": "SUCCEEDED",
                        "defaultDatasetId": "dataset-456"
                    }
                }),
                # 获取数据集
                MagicMock(json=lambda: mock_data)
            ]
            for resp in get_responses:
                resp.raise_for_status = MagicMock()
            
            get_iter = iter(get_responses)
            mock_http_client.get = AsyncMock(side_effect=lambda *args, **kwargs: next(get_iter))
            mock_http_client.aclose = AsyncMock()
            
            with patch("services.apify_client.httpx.AsyncClient", return_value=mock_http_client):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    async with ApifyClient() as client:
                        results = await client.run_seek_scraper(
                            search_query="AI Engineer",
                            location="Melbourne",
                            max_items=10
                        )
                    
                    assert len(results) == len(mock_data)
    
    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        """测试速率限制错误"""
        import httpx
        
        with patch.dict("os.environ", {"APIFY_API_TOKEN": "test-token"}):
            mock_http_client = MagicMock(spec=httpx.AsyncClient)
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.text = "Rate limit exceeded"
            
            mock_request = MagicMock()
            mock_http_client.post = AsyncMock()
            mock_http_client.post.return_value.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "Rate limit", request=mock_request, response=mock_response
                )
            )
            mock_http_client.aclose = AsyncMock()
            
            with patch("services.apify_client.httpx.AsyncClient", return_value=mock_http_client):
                async with ApifyClient() as client:
                    with pytest.raises(ApifyRateLimitError):
                        await client.run_seek_scraper("test")
    
    @pytest.mark.asyncio
    async def test_actor_failure(self):
        """测试 Actor 运行失败"""
        with patch.dict("os.environ", {"APIFY_API_TOKEN": "test-token"}):
            import httpx
            mock_http_client = MagicMock(spec=httpx.AsyncClient)
            
            # 启动成功
            mock_http_client.post = AsyncMock()
            mock_http_client.post.return_value = MagicMock(
                status_code=201,
                json=lambda: {"data": {"id": "run-123"}}
            )
            mock_http_client.post.return_value.raise_for_status = MagicMock()
            
            # 运行失败
            mock_http_client.get = AsyncMock()
            mock_http_client.get.return_value = MagicMock(
                json=lambda: {
                    "data": {
                        "status": "FAILED",
                        "statusMessage": "Scraper error"
                    }
                }
            )
            mock_http_client.get.return_value.raise_for_status = MagicMock()
            mock_http_client.aclose = AsyncMock()
            
            with patch("services.apify_client.httpx.AsyncClient", return_value=mock_http_client):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    async with ApifyClient() as client:
                        with pytest.raises(ApifyError, match="Actor 运行失败"):
                            await client.run_seek_scraper("test")


class TestFetchJobsFromSeek:
    """测试便捷函数"""
    
    @pytest.mark.asyncio
    async def test_fetch_jobs_from_seek(self):
        """测试便捷函数调用"""
        mock_data = load_mock_job_data() or [{"id": "1", "title": "Job 1"}]
        
        with patch.dict("os.environ", {"APIFY_API_TOKEN": "test-token"}):
            from services.apify_client import ApifyClient
            
            async def mock_run_seek_scraper(*args, **kwargs):
                return mock_data
            
            with patch.object(ApifyClient, 'run_seek_scraper', mock_run_seek_scraper):
                jobs = await fetch_jobs_from_seek("AI Engineer", "Melbourne", 10)
                
                assert len(jobs) == len(mock_data)
                
                # 验证所有职位都有必要字段
                for job in jobs:
                    assert isinstance(job, dict)
                    assert "id" in job
                    assert "title" in job
                    assert "company" in job
                    assert "source" in job
                    assert job["source"] == "seek"


class TestMockDataValidation:
    """Mock 数据验证测试"""
    
    def test_fixture_file_exists(self):
        """测试 fixture 文件是否存在"""
        fixture_file = FIXTURES_DIR / "seek_scraper_response.json"
        assert fixture_file.exists(), f"Fixture 文件不存在: {fixture_file}"
    
    def test_fixture_data_structure(self):
        """测试 fixture 数据结构"""
        mock_data = load_mock_job_data()
        if not mock_data:
            pytest.skip("Mock fixture 数据不存在")
        
        # 验证数据是列表
        assert isinstance(mock_data, list)
        assert len(mock_data) > 0
        
        # 验证关键字段存在
        for i, job in enumerate(mock_data):
            assert "id" in job, f"第 {i+1} 条数据缺少 id"
            assert "title" in job, f"第 {i+1} 条数据缺少 title"
            assert "jobLink" in job, f"第 {i+1} 条数据缺少 jobLink"
    
    def test_fixture_data_quality(self):
        """测试 fixture 数据质量"""
        mock_data = load_mock_job_data()
        if not mock_data:
            pytest.skip("Mock fixture 数据不存在")
        
        # 统计数据质量
        total = len(mock_data)
        with_salary = sum(1 for job in mock_data 
                         if job.get("salary") and job["salary"] != "N/A")
        with_location = sum(1 for job in mock_data 
                           if job.get("joblocationInfo"))
        with_advertiser = sum(1 for job in mock_data 
                             if job.get("advertiser", {}).get("name"))
        
        print(f"\n数据统计:")
        print(f"  总职位数: {total}")
        print(f"  有薪资信息: {with_salary} ({with_salary/total*100:.1f}%)")
        print(f"  有位置信息: {with_location} ({with_location/total*100:.1f}%)")
        print(f"  有招聘方信息: {with_advertiser} ({with_advertiser/total*100:.1f}%)")
        
        # 验证基本数据质量
        assert with_location > 0, "所有职位都没有位置信息"
