"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def mock_apify_response():
    """Mock response from Apify Seek Scraper."""
    return [
        {
            "id": "12345678",
            "title": "Senior AI Engineer",
            "salary": "$150k - $180k + super",
            "numApplicants": "45",
            "workTypes": "Full time",
            "workArrangements": "Hybrid",
            "content": {
                "bulletPoints": ["Python", "LangChain", "AWS", "Docker"],
                "sections": [
                    {"title": "About the role", "content": "..."},
                    {"title": "Requirements", "content": "5+ years Python experience..."},
                ],
            },
            "advertiser": {"name": "Tech Recruitment Co"},
            "companyProfile": {"name": "Tech Corp"},
            "listedAt": "2026-02-28T00:00:00Z",
        }
    ]


@pytest.fixture
def mock_llm_response():
    """Mock LLM extraction response."""
    return {
        "tech_stack": ["Python", "LangChain", "AWS", "Docker"],
        "salary_min": 150000,
        "salary_max": 180000,
        "salary_type": "annual",
        "includes_super": True,
        "experience_years_min": 5,
        "experience_years_max": None,
        "work_type": "full-time",
        "work_arrangement": "hybrid",
    }
