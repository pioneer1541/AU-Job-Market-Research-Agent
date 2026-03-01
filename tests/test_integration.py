"""Frontend-backend integration tests with mocked transport.

目标：
- 验证后端关键 API 端点返回结构正确
- 验证前端 APIClient 可正确调用后端接口

约束：
- 不调用真实外部 API
- 不依赖真实网络端口
"""

from pathlib import Path
import asyncio
import sys
from urllib.parse import urlparse

import pytest
import httpx

# Ensure project root is importable when running this file directly.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.main import app
from frontend.utils.api import APIClient, APIError
import frontend.utils.api as api_module


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


@pytest.fixture(scope="module")
def backend_client():
    """FastAPI in-process test client."""
    return LocalASGIClient(app)


def test_backend_health_endpoint(backend_client):
    """后端健康检查端点可用。"""
    response = backend_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


def test_backend_search_and_analyze_flow(backend_client):
    """后端搜索 + 分析流程可用（使用内置 mock 数据）。"""
    search_res = backend_client.post(
        "/api/jobs/search",
        json={"query": "AI", "location": "Melbourne", "max_results": 5},
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["query"] == "AI"
    assert isinstance(search_data["jobs"], list)
    assert search_data["total"] <= 5

    analyze_res = backend_client.get(
        "/api/analyze",
        params={"query": "AI", "location": "Melbourne", "max_results": 5},
    )
    assert analyze_res.status_code == 200
    analyze_data = analyze_res.json()
    assert "market_insights" in analyze_data
    assert "jobs" in analyze_data
    assert "report" in analyze_data


def test_frontend_api_client_calls_backend_via_mock_transport(monkeypatch, backend_client):
    """前端 APIClient 通过 mock httpx transport 调用后端。"""

    class MockHTTPXClient:
        def __init__(self, *args, **kwargs):
            self.timeout = kwargs.get("timeout")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, method, url, **kwargs):
            parsed = urlparse(url)
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            return backend_client.request(
                method=method,
                url=path,
                params=kwargs.get("params"),
                json=kwargs.get("json"),
                headers=kwargs.get("headers"),
            )

    monkeypatch.setattr(api_module.httpx, "Client", MockHTTPXClient)

    api_client = APIClient(base_url="http://mock-backend")
    health = api_client.health_check()
    assert health["status"] == "ok"

    search = api_client.search_jobs(query="AI", location="Melbourne", max_results=3)
    assert search["query"] == "AI"
    assert search["total"] <= 3

    analyze = api_client.analyze_market(query="AI", location="Melbourne", max_results=3)
    assert "market_insights" in analyze
    assert isinstance(analyze["jobs"], list)


def test_frontend_api_client_error_mapping(monkeypatch):
    """前端 APIClient 能把 HTTP 错误映射为 APIError。"""

    class MockHTTPXClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, method, url, **kwargs):
            class ErrorResponse:
                status_code = 500
                text = "boom"

                @staticmethod
                def json():
                    return {"message": "mock backend failure"}

                def raise_for_status(self):
                    request = api_module.httpx.Request(method, url)
                    raise api_module.httpx.HTTPStatusError(
                        "error",
                        request=request,
                        response=self,
                    )

            return ErrorResponse()

    monkeypatch.setattr(api_module.httpx, "Client", MockHTTPXClient)

    api_client = APIClient(base_url="http://mock-backend")
    with pytest.raises(APIError, match="API 请求失败"):
        api_client.health_check()
