"""Pydantic schemas for API request/response models."""

from pydantic import BaseModel, Field


class SearchParams(BaseModel):
    """Parameters for job search."""

    search_term: str = Field(..., description="Job search keyword", min_length=1)
    location: str = Field(default="Melbourne", description="City or location")
    state: str | None = Field(default=None, description="State filter (e.g., VIC)")
    max_results: int = Field(default=200, description="Maximum listings to fetch", ge=10, le=550)
    salary_min: int | None = Field(default=None, description="Minimum salary filter")
    salary_max: int | None = Field(default=None, description="Maximum salary filter")
    work_types: list[str] = Field(default=["Full Time", "Contract"], description="Work types")
    work_arrangements: list[str] = Field(
        default=["On-site", "Hybrid", "Remote"], description="Work arrangements"
    )
    date_range: int = Field(default=30, description="Posting age in days", ge=1, le=365)


class SearchResponse(BaseModel):
    """Response for search creation."""

    search_id: str
    status: str
    message: str | None = None


class StatusResponse(BaseModel):
    """Response for pipeline status."""

    search_id: str
    stage: str  # pending, fetching, cleaning, analyzing, generating, completed, failed
    progress: int  # 0-100
    message: str | None = None
