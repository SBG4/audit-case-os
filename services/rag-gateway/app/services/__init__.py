"""
Business logic services.

Provides high-level services for:
- Sync operations (IRIS → RAG database)
- Search operations (semantic search)
- AI assistance (RAG + LLM)
"""

from .sync_service import SyncService

__all__ = ["SyncService"]
