"""
Tests for LangGraph graph structure
"""
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
from agents.graph import create_job_research_graph, get_compiled_graph
from agents.state import GraphState


class TestGraphStructure:
    """Test graph structure and compilation"""
    
    def test_graph_creation(self):
        """Test that graph can be created"""
        graph = create_job_research_graph()
        assert graph is not None
    
    def test_graph_compilation(self):
        """Test that graph can be compiled"""
        app = get_compiled_graph()
        assert app is not None
    
    def test_graph_invocation_without_token(self):
        """Test that graph handles missing API token gracefully"""
        app = get_compiled_graph()
        
        initial_state: GraphState = {
            "query": "python developer sydney",
            "job_listings": [],
            "analysis_results": [],
            "errors": []
        }
        
        # 在没有 API token 的情况下，应该返回错误而不是崩溃
        result = app.invoke(initial_state)
        
        assert "query" in result
        assert result["query"] == "python developer sydney"
        assert "errors" in result
        # 应该有错误信息说明 API token 未设置
        assert len(result["errors"]) > 0
    
    def test_graph_invocation_with_mocked_apify(self):
        """Test that graph can be invoked with mocked Apify client"""
        import httpx
        
        app = get_compiled_graph()
        
        # Mock httpx.AsyncClient
        mock_http_client = MagicMock(spec=httpx.AsyncClient)
        mock_http_client.post = AsyncMock()
        mock_http_client.post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"data": {"id": "run-123"}}
        )
        mock_http_client.post.return_value.raise_for_status = MagicMock()
        
        get_responses = [
            MagicMock(json=lambda: {"data": {"status": "RUNNING"}}),
            MagicMock(json=lambda: {"data": {"status": "SUCCEEDED", "defaultDatasetId": "ds-456"}}),
            MagicMock(json=lambda: [{"id": "job-1", "title": "Python Developer"}])
        ]
        for resp in get_responses:
            resp.raise_for_status = MagicMock()
        
        get_iter = iter(get_responses)
        mock_http_client.get = AsyncMock(side_effect=lambda *args, **kwargs: next(get_iter))
        mock_http_client.aclose = AsyncMock()
        
        initial_state: GraphState = {
            "query": "python developer sydney",
            "job_listings": [],
            "analysis_results": [],
            "errors": []
        }
        
        with patch.dict("os.environ", {"APIFY_API_TOKEN": "test-token"}):
            with patch("services.apify_client.httpx.AsyncClient", return_value=mock_http_client):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = app.invoke(initial_state)
        
        assert "query" in result
        assert "report" in result
        assert result["query"] == "python developer sydney"


class TestNodeExecution:
    """Test individual node execution"""
    
    def test_coordinator_node(self):
        """Test coordinator node routing"""
        from agents.nodes import coordinator_node
        
        state: GraphState = {
            "query": "test query",
            "job_listings": [],
            "analysis_results": [],
            "errors": []
        }
        
        result = coordinator_node(state)
        assert "next_action" in result
        assert result["next_action"] == "fetch_jobs"
    
    def test_report_generator_node(self):
        """Test report generator node"""
        from agents.nodes import report_generator_node
        
        state: GraphState = {
            "query": "test query",
            "job_listings": [],
            "analysis_results": [],
            "processed_data": {"total_jobs": 10, "unique_companies": 5},
            "market_insights": {},
            "errors": []
        }
        
        result = report_generator_node(state)
        assert "report" in result
        assert "Job Market Research Report" in result["report"]
