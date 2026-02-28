"""
Tests for LLM Client and JD Analyzer

Uses mocking to avoid calling real LLM APIs.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json


# Test fixtures
@pytest.fixture
def sample_job():
    """Sample job listing for testing"""
    return {
        "id": "test-job-001",
        "title": "Senior Python Developer",
        "company": "Tech Corp",
        "location": "Melbourne, VIC",
        "salary": "$120,000 - $150,000 per year",
        "description": """
We are looking for a Senior Python Developer to join our team.

Requirements:
- 5+ years of Python experience
- Experience with FastAPI or Django
- PostgreSQL database skills
- AWS cloud experience
- Strong communication skills

Benefits:
- Competitive salary
- Remote work options
- Professional development budget
        """.strip(),
        "url": "https://example.com/job/001",
        "source": "seek",
        "posted_date": "2024-01-15"
    }


@pytest.fixture
def sample_llm_response():
    """Sample LLM response for JD analysis"""
    return json.dumps({
        "skills_required": ["Python", "FastAPI", "Django", "PostgreSQL", "AWS"],
        "experience_level": "Senior",
        "salary_estimate": "120000-150000 AUD/year",
        "key_requirements": [
            "5+ years Python experience",
            "FastAPI or Django experience",
            "PostgreSQL database skills",
            "AWS cloud experience"
        ],
        "industry": "科技"
    })


class TestLLMClient:
    """Tests for LLM Client"""
    
    @pytest.mark.asyncio
    async def test_llm_client_initialization(self):
        """Test LLM client initialization with environment variables"""
        with patch('backend.services.llm_client.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                llm_api_key="test-key",
                llm_base_url="https://api.test.com/v1",
                llm_model="test-model"
            )
            
            from backend.services.llm_client import LLMClient
            
            client = LLMClient()
            assert client.api_key == "test-key"
            assert client.base_url == "https://api.test.com/v1"
            assert client.model == "test-model"
    
    @pytest.mark.asyncio
    async def test_llm_client_missing_api_key(self):
        """Test LLM client raises error when API key is missing"""
        with patch('backend.services.llm_client.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                llm_api_key="",
                llm_base_url="https://api.test.com/v1",
                llm_model="test-model"
            )
            
            from backend.services.llm_client import LLMClient
            
            with pytest.raises(ValueError, match="API key"):
                LLMClient()
    
    @pytest.mark.asyncio
    async def test_llm_complete_success(self, sample_llm_response):
        """Test successful LLM completion request"""
        with patch('backend.services.llm_client.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                llm_api_key="test-key",
                llm_base_url="https://api.test.com/v1",
                llm_model="test-model"
            )
            
            from backend.services.llm_client import LLMClient
            
            # Mock AsyncOpenAI client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = sample_llm_response
            
            with patch('backend.services.llm_client.AsyncOpenAI') as mock_openai:
                mock_client = AsyncMock()
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_client.close = AsyncMock()
                mock_openai.return_value = mock_client
                
                async with LLMClient() as client:
                    result = await client.complete("Test prompt")
                    assert result == sample_llm_response
    
    @pytest.mark.asyncio
    async def test_llm_retry_on_rate_limit(self, sample_llm_response):
        """Test LLM client retries on rate limit error"""
        with patch('backend.services.llm_client.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                llm_api_key="test-key",
                llm_base_url="https://api.test.com/v1",
                llm_model="test-model"
            )
            
            from backend.services.llm_client import LLMClient
            from openai import RateLimitError
            
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = sample_llm_response
            
            with patch('backend.services.llm_client.AsyncOpenAI') as mock_openai:
                mock_client = AsyncMock()
                # First call fails, second succeeds
                mock_client.chat.completions.create = AsyncMock(
                    side_effect=[
                        RateLimitError("Rate limit", response=MagicMock(), body={}),
                        mock_response
                    ]
                )
                mock_client.close = AsyncMock()
                mock_openai.return_value = mock_client
                
                async with LLMClient(max_retries=3, retry_delay=0.1) as client:
                    result = await client.complete("Test prompt")
                    assert result == sample_llm_response
                    # Verify it was called twice (failed once, succeeded second)
                    assert mock_client.chat.completions.create.call_count == 2


class TestJDAnalyzer:
    """Tests for JD Analyzer"""
    
    def test_parse_llm_response_valid_json(self, sample_llm_response):
        """Test parsing valid JSON response"""
        from backend.services.jd_analyzer import parse_llm_response
        
        result = parse_llm_response(sample_llm_response)
        assert result["skills_required"] == ["Python", "FastAPI", "Django", "PostgreSQL", "AWS"]
        assert result["experience_level"] == "Senior"
    
    def test_parse_llm_response_json_in_code_block(self, sample_llm_response):
        """Test parsing JSON wrapped in code block"""
        from backend.services.jd_analyzer import parse_llm_response
        
        wrapped_response = f"```json\n{sample_llm_response}\n```"
        result = parse_llm_response(wrapped_response)
        assert result["skills_required"] == ["Python", "FastAPI", "Django", "PostgreSQL", "AWS"]
    
    def test_parse_llm_response_invalid_json(self):
        """Test parsing invalid JSON returns empty dict"""
        from backend.services.jd_analyzer import parse_llm_response
        
        result = parse_llm_response("This is not JSON")
        assert result == {}
    
    def test_validate_experience_level(self):
        """Test experience level validation and normalization"""
        from backend.services.jd_analyzer import validate_experience_level
        
        # Valid levels
        assert validate_experience_level("Senior") == "Senior"
        assert validate_experience_level("junior") == "Junior"
        assert validate_experience_level("MID") == "Mid"
        
        # Chinese translations
        assert validate_experience_level("高级") == "Senior"
        assert validate_experience_level("初级") == "Junior"
        assert validate_experience_level("中级") == "Mid"
        
        # Unknown defaults to Mid
        assert validate_experience_level("Expert") == "Mid"
    
    @pytest.mark.asyncio
    async def test_analyze_job_success(self, sample_job, sample_llm_response):
        """Test successful job analysis"""
        from backend.services.jd_analyzer import analyze_job
        from backend.services.llm_client import LLMClient
        
        with patch('backend.services.jd_analyzer.LLMClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(return_value=sample_llm_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client
            
            result = await analyze_job(sample_job)
            
            assert result["job_id"] == "test-job-001"
            assert "Python" in result["skills_required"]
            assert result["experience_level"] == "Senior"
            assert len(result["key_requirements"]) == 4
    
    @pytest.mark.asyncio
    async def test_analyze_job_with_client(self, sample_job, sample_llm_response):
        """Test job analysis with provided client"""
        from backend.services.jd_analyzer import analyze_job
        
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=sample_llm_response)
        
        result = await analyze_job(sample_job, client=mock_client)
        
        assert result["job_id"] == "test-job-001"
        assert "Python" in result["skills_required"]
        # Should not call __aenter__/__aexit__ when client is provided
    
    @pytest.mark.asyncio
    async def test_analyze_job_error_handling(self, sample_job):
        """Test job analysis returns default result on error"""
        from backend.services.jd_analyzer import analyze_job
        
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(side_effect=Exception("API Error"))
        
        result = await analyze_job(sample_job, client=mock_client)
        
        # Should return default result, not raise
        assert result["job_id"] == "test-job-001"
        assert result["skills_required"] == []
        assert result["experience_level"] == "Mid"
    
    @pytest.mark.asyncio
    async def test_analyze_jobs_batch(self, sample_llm_response):
        """Test batch job analysis"""
        from backend.services.jd_analyzer import analyze_jobs_batch
        
        jobs = [
            {
                "id": f"job-{i}",
                "title": f"Developer {i}",
                "company": f"Company {i}",
                "location": "Melbourne",
                "salary": None,
                "description": f"Job description {i}",
                "url": f"https://example.com/job/{i}",
                "source": "seek",
                "posted_date": "2024-01-15"
            }
            for i in range(10)
        ]
        
        with patch('backend.services.jd_analyzer.LLMClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(return_value=sample_llm_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client
            
            results = await analyze_jobs_batch(jobs, batch_size=3, delay_between_batches=0.01)
            
            assert len(results) == 10
            for result in results:
                assert "job_id" in result
                assert "skills_required" in result


class TestNodesIntegration:
    """Integration tests for graph nodes with JD analyzer"""
    
    @pytest.mark.asyncio
    async def test_market_analyzer_node(self):
        """Test market analyzer node with mock analysis"""
        from backend.agents.nodes import market_analyzer_node
        from backend.agents.state import GraphState
        
        # Create sample state
        state: GraphState = {
            "query": "python developer melbourne",
            "job_listings": [
                {
                    "id": "job-1",
                    "title": "Python Developer",
                    "company": "Tech Corp",
                    "location": "Melbourne",
                    "salary": "$100k",
                    "description": "Python, Django, AWS",
                    "url": "https://example.com/1",
                    "source": "seek",
                    "posted_date": "2024-01-15"
                }
            ],
            "analysis_results": [],
            "processed_data": {"total_jobs": 1},
            "market_insights": {},
            "report": "",
            "errors": [],
            "next_action": "analyze"
        }
        
        # Mock the analyze_jobs_batch function
        with patch('backend.agents.nodes.analyze_jobs_batch') as mock_analyze:
            mock_analyze.return_value = [
                {
                    "job_id": "job-1",
                    "skills_required": ["Python", "Django", "AWS"],
                    "experience_level": "Senior",
                    "salary_estimate": "$100k-$120k",
                    "key_requirements": ["5 years experience"],
                    "industry": "Tech"
                }
            ]
            
            result = await market_analyzer_node(state)
            
            assert "analysis_results" in result
            assert len(result["analysis_results"]) == 1
            assert "market_insights" in result
            assert "top_skills" in result["market_insights"]


class TestSalaryParsing:
    """Tests for salary parsing functionality"""
    
    def test_parse_salary_range_with_dollars(self):
        """Test parsing salary with dollar signs"""
        from backend.agents.nodes import parse_salary_range
        
        result = parse_salary_range("$120,000 - $150,000")
        assert result is not None
        assert result[0] == 120000.0
        assert result[1] == 150000.0
        assert result[2] == "AUD"
    
    def test_parse_salary_range_with_k_suffix(self):
        """Test parsing salary with k suffix"""
        from backend.agents.nodes import parse_salary_range
        
        result = parse_salary_range("$100k - $120k")
        assert result is not None
        assert result[0] == 100000.0
        assert result[1] == 120000.0
    
    def test_parse_salary_range_with_currency(self):
        """Test parsing salary with explicit currency"""
        from backend.agents.nodes import parse_salary_range
        
        result = parse_salary_range("120000-150000 AUD/year")
        assert result is not None
        assert result[0] == 120000.0
        assert result[1] == 150000.0
        assert result[2] == "AUD"
    
    def test_parse_salary_range_with_usd(self):
        """Test parsing salary with USD currency"""
        from backend.agents.nodes import parse_salary_range
        
        result = parse_salary_range("$80,000 USD")
        assert result is not None
        assert result[0] == 80000.0
        assert result[1] == 80000.0
        assert result[2] == "USD"
    
    def test_parse_salary_range_none(self):
        """Test parsing None returns None"""
        from backend.agents.nodes import parse_salary_range
        
        assert parse_salary_range(None) is None
        assert parse_salary_range("") is None
    
    def test_aggregate_insights_with_salaries(self):
        """Test salary aggregation in insights"""
        from backend.agents.nodes import _aggregate_insights
        
        analysis_results = [
            {
                "job_id": "job-1",
                "skills_required": ["Python"],
                "experience_level": "Senior",
                "salary_estimate": "$120,000 - $150,000",
                "key_requirements": [],
                "industry": "Tech"
            },
            {
                "job_id": "job-2",
                "skills_required": ["Java"],
                "experience_level": "Junior",
                "salary_estimate": "$60k - $80k",
                "key_requirements": [],
                "industry": "Tech"
            },
        ]
        jobs = [
            {"id": "job-1", "location": "Melbourne"},
            {"id": "job-2", "location": "Sydney"},
        ]
        
        result = _aggregate_insights(analysis_results, jobs)
        
        assert "salary_stats" in result
        assert result["salary_stats"] is not None
        assert result["salary_stats"]["count"] == 2
        assert "average" in result["salary_stats"]
        assert "by_experience" in result["salary_stats"]
    
    def test_report_includes_salary_section(self):
        """Test that report generator includes salary analysis"""
        from backend.agents.nodes import report_generator_node
        
        state = {
            "query": "python developer melbourne",
            "job_listings": [{"id": "job-1", "location": "Melbourne"}],
            "analysis_results": [],
            "processed_data": {"total_jobs": 1},
            "market_insights": {
                "top_skills": [],
                "experience_distribution": {},
                "top_locations": [],
                "salary_stats": {
                    "average": 135000.0,
                    "min": 120000.0,
                    "max": 150000.0,
                    "count": 3,
                    "currency": "AUD",
                    "by_experience": {
                        "Senior": {"average": 145000.0, "min": 140000.0, "max": 150000.0, "count": 2},
                        "Mid": {"average": 125000.0, "min": 120000.0, "max": 130000.0, "count": 1}
                    }
                }
            },
            "errors": [],
        }
        
        result = report_generator_node(state)
        report = result["report"]
        
        assert "## Salary Analysis" in report
        assert "Average Salary" in report
        assert "135k" in report  # 135000 formatted as 135k
        assert "Experience Level" in report
