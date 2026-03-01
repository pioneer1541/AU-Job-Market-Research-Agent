"""Tests for main application.
主应用测试
"""

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_root_endpoint():
    """测试根路径返回 API 信息"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


def test_health_check():
    """测试健康检查端点"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_api_search_endpoint_exists():
    """测试搜索端点存在且接受请求"""
    response = client.post(
        "/api/search",
        json={
            "search_term": "AI Engineer",
            "location": "Melbourne",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "search_id" in data
    assert "status" in data
