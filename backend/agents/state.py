"""
Graph State Definitions for Job Market Research Agent
"""
from typing import TypedDict, Annotated, Optional
import operator


class JobListing(TypedDict):
    """Single job listing data structure"""
    id: str
    title: str
    company: str
    location: str
    salary: Optional[str]
    description: str
    url: str
    source: str
    posted_date: Optional[str]


class AnalysisResult(TypedDict):
    """Analysis result for a single job"""
    job_id: str
    hard_skills: list[str]
    soft_skills: list[str]
    years_of_experience: Optional[str]
    industry_keywords: list[str]
    responsibility_themes: list[str]
    qualifications: list[str]
    skills_required: list[str]
    experience_level: str
    salary_estimate: Optional[str]
    key_requirements: list[str]
    industry: Optional[str]


class GraphState(TypedDict):
    """Main state for the job market research graph"""
    # Input
    query: str  # User's search query (e.g., "software engineer melbourne")
    
    # Intermediate data
    job_listings: Annotated[list[JobListing], operator.add]  # Collected jobs
    analysis_results: Annotated[list[AnalysisResult], operator.add]  # Analysis per job
    
    # Aggregated results
    processed_data: dict  # Cleaned and normalized data
    market_insights: dict  # Statistical analysis
    report: str  # Final generated report
    
    # Error handling
    errors: Annotated[list[str], operator.add]
    
    # Control flow
    next_action: str  # For supervisor routing


class FetcherState(TypedDict):
    """State for job fetching subgraph"""
    query: str
    source: str  # seek, indeed, linkedin, etc.
    jobs: list[JobListing]
    page: int
    has_more: bool
    errors: list[str]
