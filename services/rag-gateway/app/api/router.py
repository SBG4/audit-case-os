"""Main API router aggregator."""
from fastapi import APIRouter

# Import API route modules
# from app.api.v1 import sync, search, assist, report

api_router = APIRouter()

# Health check at API level
@api_router.get("/ping")
async def ping():
    """Simple ping endpoint for checking API availability."""
    return {"status": "ok", "message": "RAG Gateway API is running"}

# Include v1 routers when implemented
# api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
# api_router.include_router(search.router, prefix="/search", tags=["search"])
# api_router.include_router(assist.router, prefix="/assist", tags=["assist"])
# api_router.include_router(report.router, prefix="/report", tags=["report"])
