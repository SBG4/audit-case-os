"""
API v1 routes.
"""

from fastapi import APIRouter
from .sync import router as sync_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(sync_router, tags=["sync"])

__all__ = ["api_router"]
