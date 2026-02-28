"""Tests for main application."""

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_api_search_endpoint_exists():
    """Test that search endpoint exists and accepts requests."""
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
