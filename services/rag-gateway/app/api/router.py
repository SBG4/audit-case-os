"""Main API router aggregator."""
from fastapi import APIRouter

# Import v1 API router
from app.api.v1 import api_router as v1_router

api_router = APIRouter()

# Include v1 routes
api_router.include_router(v1_router)

# Health check at API level (legacy, kept for compatibility)
@api_router.get("/ping")
async def ping():
    """Simple ping endpoint for checking API availability."""
    return {"status": "ok", "message": "RAG Gateway API is running"}
