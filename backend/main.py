"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("Starting Job Market Research Agent...")
    yield
    # Shutdown
    print("Shutting down Job Market Research Agent...")


app = FastAPI(
    title="Job Market Research Agent",
    description="AI-powered job market analysis API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}
