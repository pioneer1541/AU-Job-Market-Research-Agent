"""API route definitions."""

from fastapi import APIRouter

from backend.api.schemas import SearchParams, SearchResponse, StatusResponse

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def create_search(params: SearchParams):
    """Trigger a new job search and analysis pipeline."""
    # TODO: Implement pipeline trigger
    return SearchResponse(
        search_id="placeholder",
        status="pending",
        message="Search pipeline not yet implemented",
    )


@router.get("/search/{search_id}/status", response_model=StatusResponse)
async def get_status(search_id: str):
    """Get the status of a running search pipeline."""
    # TODO: Implement status tracking
    return StatusResponse(
        search_id=search_id,
        stage="pending",
        progress=0,
        message="Status tracking not yet implemented",
    )
