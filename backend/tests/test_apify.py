"""
Apify 客户端测试
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


def load_real_job_data():
    """加载真实的职位数据用于测试"""
    fixture_file = FIXTURES_DIR / "seek_response.json"
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
    
    def test_parse_to_job_listing(self):
        """测试原始数据解析为 JobListing"""
        raw_job = {
            "id": "12345678",
            "title": "Senior Python Developer",
            "salary": "$150k - $180k + super",
            "location": "Melbourne VIC",
            "advertiser": {"name": "Tech Recruitment"},
            "companyProfile": {"name": "Tech Corp"},
            "listedAt": "2026-03-01T00:00:00Z",
            "url": "https://www.seek.com.au/job/12345678",
            "content": {
                "bulletPoints": ["Python", "FastAPI", "PostgreSQL"],
                "sections": [
                    {"title": "About the role", "content": "Great opportunity..."},
                ]
            }
        }
        
        result = ApifyClient.parse_to_job_listing(raw_job)
        
        assert result["id"] == "12345678"
        assert result["title"] == "Senior Python Developer"
        assert result["company"] == "Tech Corp"  # companyProfile 优先
        assert result["location"] == "Melbourne VIC"
        assert result["salary"] == "$150k - $180k"  # 清洗后只保留核心薪资格式
        assert result["source"] == "seek"
        assert result["posted_date"] == "2026-03-01T00:00:00Z"
        assert "Python" in result["description"]
        assert "About the role" in result["description"]
    
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
    
    def test_parse_real_job_data(self):
        """测试解析真实的 Seek 职位数据"""
        real_data = load_real_job_data()
        if not real_data:
            pytest.skip("真实 fixture 数据不存在，请运行 test_apify_real.py 生成")
        
        # 解析第一条数据
        first_job = real_data[0]
        result = ApifyClient.parse_to_job_listing(first_job)
        
        # 验证关键字段
        assert result["id"] == first_job["id"]
        assert result["title"] == first_job["title"]
        assert result["source"] == "seek"
        assert result["url"].startswith("https://www.seek.com.au")
    
    def test_parse_all_real_job_data(self):
        """测试解析所有真实数据"""
        real_data = load_real_job_data()
        if not real_data:
            pytest.skip("真实 fixture 数据不存在，请运行 test_apify_real.py 生成")
        
        results = [ApifyClient.parse_to_job_listing(job) for job in real_data]
        
        # 验证所有数据都能成功解析
        assert len(results) == len(real_data)
        for result in results:
            assert result["id"]
            assert result["title"]
            assert result["source"] == "seek"
    
    @pytest.mark.asyncio
    async def test_run_seek_scraper_success(self):
        """测试成功的 Seek Scraper 调用"""
        import httpx
        
        # 使用真实数据作为 mock 响应
        real_data = load_real_job_data()
        mock_response_data = real_data or [{"id": "job-1", "title": "Test Job"}]
        
        with patch.dict("os.environ", {"APIFY_API_TOKEN": "test-token"}):
            # Mock httpx.AsyncClient
            mock_http_client = MagicMock(spec=httpx.AsyncClient)
            mock_http_client.post = AsyncMock()
            mock_http_client.post.return_value = MagicMock(
                status_code=201,
                json=lambda: {"data": {"id": "run-123"}}
            )
            mock_http_client.post.return_value.raise_for_status = MagicMock()
            
            # 创建 get 响应序列
            get_responses = [
                # 第一次轮询 - 运行中
                MagicMock(json=lambda: {"data": {"status": "RUNNING"}}),
                # 第二次轮询 - 完成
                MagicMock(json=lambda: {
                    "data": {
                        "status": "SUCCEEDED",
                        "defaultDatasetId": "dataset-456"
                    }
                }),
                # 获取数据集 - 使用真实数据
                MagicMock(json=lambda: mock_response_data)
            ]
            for resp in get_responses:
                resp.raise_for_status = MagicMock()
            
            # 使用迭代器来确保 side_effect 消耗正确
            get_iter = iter(get_responses)
            mock_http_client.get = AsyncMock(side_effect=lambda *args, **kwargs: next(get_iter))
            mock_http_client.aclose = AsyncMock()
            
            with patch("services.apify_client.httpx.AsyncClient", return_value=mock_http_client):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    async with ApifyClient() as client:
                        results = await client.run_seek_scraper(
                            search_query="AI Engineer",
                            location="Melbourne",
                            max_items=5
                        )
                    
                    assert len(results) == len(mock_response_data)
                    if real_data:
                        # 验证真实数据的格式
                        assert results[0]["id"] == real_data[0]["id"]
    
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
        with patch.dict("os.environ", {"APIFY_API_TOKEN": "test-token"}):
            with patch("services.apify_client.ApifyClient") as MockClient:
                mock_instance = AsyncMock()
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_instance.run_seek_scraper = AsyncMock(return_value=[
                    {"id": "1", "title": "Job 1"},
                    {"id": "2", "title": "Job 2"},
                ])
                MockClient.return_value = mock_instance
                
                jobs = await fetch_jobs_from_seek("python", "Melbourne", 10)
                
                assert len(jobs) == 2
                mock_instance.run_seek_scraper.assert_called_once_with(
                    "python", "Melbourne", 10
                )
    
    @pytest.mark.asyncio
    async def test_fetch_jobs_from_seek_with_real_data(self):
        """测试使用真实数据的便捷函数"""
        real_data = load_real_job_data()
        if not real_data:
            pytest.skip("真实 fixture 数据不存在，请运行 test_apify_real.py 生成")
        
        with patch.dict("os.environ", {"APIFY_API_TOKEN": "test-token"}):
            # 不 mock 整个类，而是 mock 实例方法
            from services.apify_client import ApifyClient
            
            async def mock_run_seek_scraper(*args, **kwargs):
                return real_data
            
            with patch.object(ApifyClient, 'run_seek_scraper', mock_run_seek_scraper):
                jobs = await fetch_jobs_from_seek("AI Engineer", "Melbourne", 5)
                
                assert len(jobs) == len(real_data)
                # 验证所有职位都有必要字段
                for job in jobs:
                    assert isinstance(job, dict), f"job 应该是 dict 类型: {type(job)}"
                    assert "id" in job, f"job 缺少 id 字段: {job.keys()}"
                    assert "title" in job
                    assert "company" in job
                    assert "source" in job
                    assert job["source"] == "seek"


class TestRealDataValidation:
    """真实数据验证测试"""
    
    def test_fixture_file_exists(self):
        """测试 fixture 文件是否存在"""
        fixture_file = FIXTURES_DIR / "seek_response.json"
        # 这个测试不会失败，只是标记是否存在
        if fixture_file.exists():
            assert True, "Fixture 文件存在"
        else:
            pytest.skip("Fixture 文件不存在，请运行 test_apify_real.py 生成")
    
    def test_fixture_data_structure(self):
        """测试 fixture 数据结构"""
        real_data = load_real_job_data()
        if not real_data:
            pytest.skip("真实 fixture 数据不存在")
        
        # 验证数据是列表
        assert isinstance(real_data, list)
        assert len(real_data) > 0
        
        # 验证每条数据都有必要字段
        required_fields = ["id", "title", "company", "location", "url", "source"]
        for i, job in enumerate(real_data):
            for field in required_fields:
                assert field in job, f"第 {i+1} 条数据缺少字段: {field}"
    
    def test_fixture_data_quality(self):
        """测试 fixture 数据质量"""
        real_data = load_real_job_data()
        if not real_data:
            pytest.skip("真实 fixture 数据不存在")
        
        # 统计数据质量
        total = len(real_data)
        with_salary = sum(1 for job in real_data if job.get("salary"))
        with_description = sum(1 for job in real_data if job.get("description"))
        
        # 输出统计信息
        print(f"\n数据统计:")
        print(f"  总职位数: {total}")
        print(f"  有薪资信息: {with_salary} ({with_salary/total*100:.1f}%)")
        print(f"  有描述信息: {with_description} ({with_description/total*100:.1f}%)")
        
        # 至少应该有描述
        assert with_description > 0, "所有职位都没有描述信息"
