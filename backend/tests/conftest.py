"""Pytest configuration and fixtures."""

import asyncio
import inspect

import pytest


def pytest_configure(config):
    """Register local async marker fallback when pytest-asyncio is unavailable."""
    config.addinivalue_line(
        "markers",
        "asyncio: run test coroutine using local asyncio fallback",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """Run coroutine test functions without requiring pytest-asyncio plugin."""
    if inspect.iscoroutinefunction(pyfuncitem.obj):
        kwargs = {
            name: pyfuncitem.funcargs[name]
            for name in pyfuncitem._fixtureinfo.argnames
            if name in pyfuncitem.funcargs
        }
        asyncio.run(pyfuncitem.obj(**kwargs))
        return True
    return None


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
