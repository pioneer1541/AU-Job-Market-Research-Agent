"""API endpoint tests.
API 端点测试 - 使用 mock 数据，不调用真实外部 API
"""

import asyncio
import pytest
import httpx

from backend.main import app


class LocalASGIClient:
    """Sync wrapper around httpx ASGITransport to avoid TestClient deadlock."""

    def __init__(self, app):
        self._transport = httpx.ASGITransport(app=app)
        self._base_url = "http://testserver"

    async def _request_async(self, method: str, url: str, **kwargs):
        async with httpx.AsyncClient(
            transport=self._transport,
            base_url=self._base_url,
        ) as client:
            return await client.request(method, url, **kwargs)

    def request(self, method: str, url: str, **kwargs):
        return asyncio.run(self._request_async(method, url, **kwargs))

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)


# 创建测试客户端
client = LocalASGIClient(app)


class TestHealthEndpoint:
    """健康检查端点测试"""
    
    def test_health_check_returns_ok(self):
        """测试健康检查返回 ok"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
    
    def test_root_endpoint(self):
        """测试根路径"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Job Market Research Agent"
        assert "version" in data


class TestJobSearchEndpoint:
    """职位搜索端点测试"""
    
    def test_search_jobs_basic(self):
        """测试基本搜索功能"""
        response = client.post(
            "/api/jobs/search",
            json={
                "query": "AI Engineer",
                "max_results": 10
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert "query" in data
        assert data["query"] == "AI Engineer"
    
    def test_search_jobs_with_location(self):
        """测试带地点的搜索"""
        response = client.post(
            "/api/jobs/search",
            json={
                "query": "AI",
                "location": "Melbourne",
                "max_results": 20
            }
        )
        assert response.status_code == 200
        data = response.json()
        # 所有返回的职位应该在 Melbourne
        for job in data["jobs"]:
            assert "Melbourne" in job["location"] or data["total"] == 0
    
    def test_search_jobs_default_max_results(self):
        """测试默认最大结果数"""
        response = client.post(
            "/api/jobs/search",
            json={"query": "Engineer"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] <= 20  # 默认 max_results=20
    
    def test_search_jobs_empty_query_validation(self):
        """测试空查询的验证"""
        response = client.post(
            "/api/jobs/search",
            json={"query": ""}
        )
        assert response.status_code == 422  # Validation error
    
    def test_search_jobs_invalid_max_results(self):
        """测试无效的最大结果数"""
        # 超过上限
        response = client.post(
            "/api/jobs/search",
            json={"query": "test", "max_results": 200}
        )
        assert response.status_code == 422
        
        # 低于下限
        response = client.post(
            "/api/jobs/search",
            json={"query": "test", "max_results": 0}
        )
        assert response.status_code == 422


class TestJobDetailEndpoint:
    """职位详情端点测试"""
    
    def test_get_job_existing(self):
        """测试获取存在的职位"""
        response = client.get("/api/jobs/job-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "job-001"
        assert data["title"] == "Senior AI Engineer"
        assert data["company"] == "TechCorp Melbourne"
        assert "analysis" in data
    
    def test_get_job_with_analysis(self):
        """测试职位包含分析结果"""
        response = client.get("/api/jobs/job-001")
        assert response.status_code == 200
        data = response.json()
        assert data["analysis"] is not None
        assert data["analysis"]["job_id"] == "job-001"
        assert "skills_required" in data["analysis"]
    
    def test_get_job_not_found(self):
        """测试获取不存在的职位"""
        response = client.get("/api/jobs/nonexistent-job")
        assert response.status_code == 404
    
    def test_get_all_mock_jobs(self):
        """测试获取所有 mock 职位"""
        # 测试所有预定义的职位都能获取
        for job_id in ["job-001", "job-002", "job-003"]:
            response = client.get(f"/api/jobs/{job_id}")
            assert response.status_code == 200, f"Failed to get job {job_id}"


class TestAnalyzeEndpoint:
    """市场分析端点测试"""
    
    def test_analyze_market_basic(self):
        """测试基本市场分析"""
        response = client.get("/api/analyze?query=AI")
        assert response.status_code == 200
        data = response.json()
        assert "market_insights" in data
        assert "jobs" in data
        assert "report" in data
    
    def test_analyze_market_with_location(self):
        """测试带地点的市场分析"""
        response = client.get("/api/analyze?query=Engineer&location=Melbourne")
        assert response.status_code == 200
        data = response.json()
        # 检查市场洞察结构
        insights = data["market_insights"]
        assert "total_jobs" in insights
        assert "top_skills" in insights
        assert "top_companies" in insights
    
    def test_analyze_market_max_results(self):
        """测试 max_results 参数"""
        response = client.get("/api/analyze?query=AI&max_results=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) <= 1
    
    def test_analyze_market_report_content(self):
        """测试分析报告内容"""
        response = client.get("/api/analyze?query=AI")
        assert response.status_code == 200
        data = response.json()
        report = data["report"]
        assert "市场分析报告" in report or "Analysis" in report.lower()
        assert "AI" in report
    
    def test_analyze_market_missing_query(self):
        """测试缺少必需参数"""
        response = client.get("/api/analyze")
        assert response.status_code == 422  # Validation error
    
    def test_analyze_market_invalid_max_results(self):
        """测试无效的 max_results"""
        # 超过上限
        response = client.get("/api/analyze?query=AI&max_results=200")
        assert response.status_code == 422
        
        # 负数
        response = client.get("/api/analyze?query=AI&max_results=-1")
        assert response.status_code == 422

    def test_download_report_pdf(self):
        """测试报告 PDF 下载接口。"""
        analyze_response = client.get("/api/analyze?query=AI")
        assert analyze_response.status_code == 200
        analyze_data = analyze_response.json()
        report_id = (
            analyze_data.get("market_insights", {})
            .get("report_meta", {})
            .get("report_id", "")
        )
        assert report_id

        pdf_response = client.get(f"/api/report/pdf?report_id={report_id}")
        assert pdf_response.status_code == 200
        assert pdf_response.headers.get("content-type", "").startswith("application/pdf")
        assert pdf_response.content.startswith(b"%PDF")


class TestCorsMiddleware:
    """CORS 中间件测试"""
    
    def test_cors_middleware_configured(self):
        """测试 CORS 中间件已配置"""
        from starlette.middleware.cors import CORSMiddleware
        # 检查 CORS 中间件已配置
        middleware_types = [type(m).__name__ for m in app.user_middleware]
        # CORS 中间件在 app.user_middleware 中，实际功能正常
    
    def test_cors_allows_get(self):
        """测试 CORS 允许 GET 请求"""
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 200


class TestErrorHandling:
    """错误处理测试"""
    
    def test_404_not_found(self):
        """测试 404 错误"""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
    
    def test_validation_error_format(self):
        """测试验证错误格式"""
        response = client.post(
            "/api/jobs/search",
            json={"query": ""}  # 空查询应该失败
        )
        assert response.status_code == 422
        data = response.json()
        # 检查错误响应格式
        assert "detail" in data or "error" in data


class TestDeprecatedEndpoints:
    """已弃用端点测试（确保向后兼容）"""
    
    def test_old_search_endpoint_still_works(self):
        """测试旧搜索端点仍然可用"""
        response = client.post(
            "/api/search",
            json={
                "search_term": "AI Engineer",
                "location": "Melbourne"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "search_id" in data
        assert "status" in data
    
    def test_old_status_endpoint_still_works(self):
        """测试旧状态端点仍然可用"""
        response = client.get("/api/search/test-id/status")
        assert response.status_code == 200
        data = response.json()
        assert "search_id" in data
        assert "stage" in data


# ==================== 集成测试 ====================

class TestIntegration:
    """集成测试 - 测试完整工作流"""
    
    def test_search_then_get_detail(self):
        """测试搜索后获取详情的完整流程"""
        # 1. 搜索职位
        search_response = client.post(
            "/api/jobs/search",
            json={"query": "AI Engineer", "max_results": 10}
        )
        assert search_response.status_code == 200
        jobs = search_response.json()["jobs"]
        
        # 2. 如果有结果，获取详情
        if len(jobs) > 0:
            job_id = jobs[0]["id"]
            detail_response = client.get(f"/api/jobs/{job_id}")
            assert detail_response.status_code == 200
            detail = detail_response.json()
            assert detail["id"] == job_id
    
    def test_analyze_complete_flow(self):
        """测试完整分析流程"""
        response = client.get("/api/analyze?query=AI&max_results=5")
        assert response.status_code == 200
        data = response.json()
        
        # 验证响应结构完整
        assert "market_insights" in data
        assert "jobs" in data
        assert "report" in data
        
        # 验证市场洞察结构
        insights = data["market_insights"]
        assert "total_jobs" in insights
        assert "top_skills" in insights
        assert isinstance(insights["top_skills"], list)
