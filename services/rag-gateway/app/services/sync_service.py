"""
Sync service for orchestrating case synchronization from IRIS to RAG database.

Handles:
- Fetching case and evidence data from IRIS
- Downloading and extracting text from evidence files
- Chunking documents into semantic segments
- Generating embeddings
- Storing in database with deduplication
"""

import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, Chunk, SyncJob
from app.integrations.iris_client import IrisClient, IrisAPIError
from app.processing.extractors import extract_text, TextExtractionError
from app.processing.chunker import DocumentChunker
from rag.embedder import EmbeddingService
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SyncService:
    """
    Service for synchronizing IRIS cases to RAG database.

    Orchestrates the entire sync pipeline:
    IRIS → Download → Extract → Chunk → Embed → Store
    """

    def __init__(
        self,
        db_session: AsyncSession,
        iris_client: IrisClient,
        embedding_service: EmbeddingService,
    ):
        """
        Initialize sync service.

        Args:
            db_session: Database session
            iris_client: IRIS API client
            embedding_service: Embedding generation service
        """
        self.db = db_session
        self.iris = iris_client
        self.embedder = embedding_service
        self.chunker = DocumentChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

        logger.info("Initialized SyncService")

    async def sync_case(
        self,
        case_id: int,
        force_reindex: bool = False,
    ) -> SyncJob:
        """
        Synchronize a complete IRIS case to RAG database.

        Args:
            case_id: IRIS case ID to sync
            force_reindex: If True, re-process existing documents

        Returns:
            SyncJob record with status and statistics

        Raises:
            IrisAPIError: If IRIS API fails
        """
        logger.info(f"Starting sync for case {case_id} (force_reindex={force_reindex})")

        # Create sync job record
        sync_job = SyncJob(
            case_id=case_id,
            status="running",
            started_at=datetime.utcnow(),
            job_metadata={"force_reindex": force_reindex},
        )
        self.db.add(sync_job)
        await self.db.commit()
        await self.db.refresh(sync_job)

        try:
            # Fetch case metadata from IRIS
            case_data = await self.iris.get_case(case_id)
            logger.info(f"Fetched case: {case_data.get('case_name')}")

            # Fetch evidence list
            evidences = await self.iris.list_case_evidence(case_id)
            logger.info(f"Found {len(evidences)} evidence files")

            if not evidences:
                logger.warning(f"No evidence files found for case {case_id}")
                sync_job.status = "completed"
                sync_job.completed_at = datetime.utcnow()
                sync_job.documents_synced = 0
                sync_job.chunks_created = 0
                await self.db.commit()
                return sync_job

            # Process each evidence file
            documents_synced = 0
            chunks_created = 0
            errors = []

            for evidence in evidences:
                try:
                    evidence_id = evidence.get("id")
                    filename = evidence.get("filename", f"evidence_{evidence_id}")

                    logger.info(f"Processing evidence {evidence_id}: {filename}")

                    # Download file
                    file_content = await self.iris.download_evidence(evidence_id, case_id)
                    file_hash = hashlib.sha256(file_content).hexdigest()

                    # Check if already processed (unless force_reindex)
                    if not force_reindex:
                        existing = await self._find_document_by_hash(file_hash)
                        if existing:
                            logger.info(f"Skipping duplicate file: {filename} (hash: {file_hash[:16]}...)")
                            continue

                    # Extract text
                    try:
                        text = extract_text(filename, file_content)
                    except TextExtractionError as e:
                        logger.warning(f"Failed to extract text from {filename}: {e}")
                        errors.append(f"{filename}: {str(e)}")
                        continue

                    if not text.strip():
                        logger.warning(f"No text extracted from {filename}")
                        errors.append(f"{filename}: No text content")
                        continue

                    # Create document record
                    document = Document(
                        case_id=case_id,
                        document_name=filename,
                        document_type=evidence.get("file_type"),
                        file_size=len(file_content),
                        file_hash=file_hash,
                        storage_path=None,  # TODO: Upload to MinIO in Phase 2
                        doc_metadata={
                            "iris_evidence_id": evidence_id,
                            "file_description": evidence.get("file_description"),
                            "case_name": case_data.get("case_name"),
                        },
                    )
                    self.db.add(document)
                    await self.db.flush()  # Get document.id

                    # Chunk the text
                    chunks_data = self.chunker.chunk_text(
                        text,
                        metadata={
                            "document_name": filename,
                            "evidence_id": evidence_id,
                        },
                    )

                    logger.info(f"Created {len(chunks_data)} chunks from {filename}")

                    # Generate embeddings in batch
                    chunk_texts = [chunk["content"] for chunk in chunks_data]
                    embeddings = await self.embedder.embed_batch(chunk_texts)

                    # Create chunk records
                    for chunk_data, embedding in zip(chunks_data, embeddings):
                        chunk = Chunk(
                            document_id=document.id,
                            case_id=case_id,
                            chunk_index=chunk_data["chunk_index"],
                            content=chunk_data["content"],
                            embedding=embedding,
                            token_count=chunk_data["token_count"],
                            chunk_metadata=chunk_data["metadata"],
                        )
                        self.db.add(chunk)

                    documents_synced += 1
                    chunks_created += len(chunks_data)

                    # Commit after each document to avoid losing progress
                    await self.db.commit()

                    logger.info(
                        f"Synced document {documents_synced}/{len(evidences)}: "
                        f"{filename} ({len(chunks_data)} chunks)"
                    )

                except Exception as e:
                    logger.error(f"Error processing evidence {evidence_id}: {e}", exc_info=True)
                    errors.append(f"{evidence.get('filename', evidence_id)}: {str(e)}")
                    continue

            # Update sync job
            sync_job.status = "completed" if not errors else "completed_with_errors"
            sync_job.completed_at = datetime.utcnow()
            sync_job.documents_synced = documents_synced
            sync_job.chunks_created = chunks_created

            if errors:
                sync_job.error_message = "\n".join(errors)

            await self.db.commit()

            logger.info(
                f"Sync completed for case {case_id}: "
                f"{documents_synced} documents, {chunks_created} chunks"
            )

            return sync_job

        except Exception as e:
            logger.error(f"Sync failed for case {case_id}: {e}", exc_info=True)

            # Update job status to failed
            sync_job.status = "failed"
            sync_job.completed_at = datetime.utcnow()
            sync_job.error_message = str(e)
            await self.db.commit()

            raise

    async def _find_document_by_hash(self, file_hash: str) -> Optional[Document]:
        """
        Find existing document by file hash for deduplication.

        Args:
            file_hash: SHA-256 hash of file content

        Returns:
            Document if found, None otherwise
        """
        result = await self.db.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def get_sync_job(self, job_id: int) -> Optional[SyncJob]:
        """
        Get sync job by ID.

        Args:
            job_id: Sync job ID

        Returns:
            SyncJob if found, None otherwise
        """
        result = await self.db.execute(
            select(SyncJob).where(SyncJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_sync_jobs(
        self,
        case_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[SyncJob]:
        """
        List sync jobs with optional filters.

        Args:
            case_id: Filter by case ID
            status: Filter by status
            limit: Maximum number of results

        Returns:
            List of SyncJob records
        """
        query = select(SyncJob)

        if case_id is not None:
            query = query.where(SyncJob.case_id == case_id)

        if status is not None:
            query = query.where(SyncJob.status == status)

        query = query.order_by(SyncJob.started_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())
