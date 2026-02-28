"""
Tests for LangGraph graph structure
"""
import sys
from pathlib import Path

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
    
    def test_graph_invocation(self):
        """Test that graph can be invoked with initial state"""
        app = get_compiled_graph()
        
        initial_state: GraphState = {
            "query": "python developer sydney",
            "job_listings": [],
            "analysis_results": [],
            "errors": []
        }
        
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
