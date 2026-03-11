"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logging import logger
from app.api.routes import router as api_router
from app.api.dashboard import router as dashboard_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Starting Social Media Agent...")
    logger.info(f"Environment: {settings.app_env}")
    yield
    logger.info("Shutting down Social Media Agent...")


app = FastAPI(
    title=settings.app_name,
    description="Hybrid Social Media Posting Agent with AI-powered content generation",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files and templates
app.mount("/static", StaticFiles(directory="templates/static"), name="static")

# API routes
app.include_router(api_router, prefix="/api")

# Dashboard routes
app.include_router(dashboard_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.app_name}
