"""
Integration modules for external services.

Provides clients for:
- IRIS: Case management and evidence retrieval
- Nextcloud: Document storage (Phase 2)
- Paperless: OCR document processing (Phase 2)
"""

from .iris_client import IrisClient

__all__ = ["IrisClient"]
