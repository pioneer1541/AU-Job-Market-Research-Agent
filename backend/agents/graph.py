"""
LangGraph Graph Definition for Job Market Research Agent
"""
from langgraph.graph import StateGraph, START, END
from .state import GraphState
from .nodes import (
    coordinator_node,
    job_fetcher_node,
    data_processor_node,
    market_analyzer_node,
    report_generator_node,
    supervisor_router,
)


def create_job_research_graph() -> StateGraph:
    """
    Creates the job market research graph.
    
    Architecture:
    START -> coordinator -> job_fetcher -> data_processor -> market_analyzer -> report_generator -> END
    
    With supervisor routing for flexibility.
    """
    # Create the graph
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("coordinator", coordinator_node)
    graph.add_node("fetch_jobs", job_fetcher_node)
    graph.add_node("process_data", data_processor_node)
    graph.add_node("analyze", market_analyzer_node)
    graph.add_node("generate_report", report_generator_node)
    
    # Define entry point
    graph.add_edge(START, "coordinator")
    
    # Add conditional edges from coordinator
    graph.add_conditional_edges(
        "coordinator",
        supervisor_router,
        {
            "fetch_jobs": "fetch_jobs",
            "process_data": "process_data",
            "analyze": "analyze",
            "generate_report": "generate_report",
            "END": END
        }
    )
    
    # Add conditional edges from each node
    for node in ["fetch_jobs", "process_data", "analyze", "generate_report"]:
        graph.add_conditional_edges(
            node,
            supervisor_router,
            {
                "fetch_jobs": "fetch_jobs",
                "process_data": "process_data",
                "analyze": "analyze",
                "generate_report": "generate_report",
                "END": END
            }
        )
    
    return graph


# Compile the graph
def get_compiled_graph():
    """Returns the compiled graph ready for execution."""
    graph = create_job_research_graph()
    return graph.compile()


# For visualization (optional, requires graphviz)
def visualize_graph():
    """Generates a PNG visualization of the graph."""
    try:
        from IPython.display import Image, display
        graph = get_compiled_graph()
        return Image(graph.get_graph().draw_mermaid_png())
    except ImportError:
        print("IPython not available. Install with: pip install ipython")
        return None


if __name__ == "__main__":
    # Test the graph
    app = get_compiled_graph()
    
    # Run a test
    result = app.invoke({
        "query": "software engineer melbourne",
        "job_listings": [],
        "analysis_results": [],
        "errors": []
    })
    
    print("Result:", result)
