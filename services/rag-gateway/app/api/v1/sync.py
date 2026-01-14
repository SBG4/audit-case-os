"""
Sync API endpoints for case synchronization.

Endpoints:
- POST /api/v1/sync/case/{case_id} - Trigger sync job
- GET /api/v1/sync/status/{job_id} - Get job status
- GET /api/v1/sync/jobs - List sync jobs
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.services.sync_service import SyncService
from app.integrations.iris_client import IrisClient, IrisNotFoundError, IrisAPIError
from rag.embedder import EmbeddingService
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/sync")


# Request/Response Models
class SyncRequest(BaseModel):
    """Request model for sync operation."""
    force_reindex: bool = Field(
        default=False,
        description="If True, re-process existing documents"
    )


class SyncResponse(BaseModel):
    """Response model for sync operation."""
    status: str = Field(description="Status: accepted, error")
    job_id: int = Field(description="Sync job ID for tracking")
    case_id: int = Field(description="IRIS case ID being synced")
    message: str = Field(description="Human-readable message")


class SyncJobStatus(BaseModel):
    """Sync job status model."""
    job_id: int
    case_id: int
    status: str = Field(description="pending, running, completed, failed, completed_with_errors")
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    documents_synced: int
    chunks_created: int
    error_message: Optional[str]


class SyncJobList(BaseModel):
    """List of sync jobs."""
    jobs: List[SyncJobStatus]
    total: int


# Dependency: Get IRIS client
async def get_iris_client() -> IrisClient:
    """Get configured IRIS client."""
    if not settings.is_iris_configured():
        raise HTTPException(
            status_code=500,
            detail="IRIS integration not configured. Set IRIS_API_URL and IRIS_API_KEY."
        )

    return IrisClient(
        base_url=settings.IRIS_API_URL,
        api_key=settings.IRIS_API_KEY,
        timeout=settings.IRIS_TIMEOUT,
    )


# Dependency: Get embedding service
async def get_embedding_service() -> EmbeddingService:
    """Get embedding service instance."""
    service = EmbeddingService()
    if not service.is_loaded():
        # Model should be loaded at startup, but check anyway
        await EmbeddingService.warm_up()
    return service


# Background task for sync
async def run_sync_task(
    case_id: int,
    force_reindex: bool,
    db_url: str,
):
    """
    Run sync task in background.

    This creates its own database session and IRIS client
    to avoid sharing connections across threads.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import text

    logger.info(f"Background sync task started for case {case_id}")

    # Create engine and session for this task
    task_engine = create_async_engine(db_url)
    TaskSessionLocal = async_sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)

    async with TaskSessionLocal() as session:
        async with IrisClient(settings.IRIS_API_URL, settings.IRIS_API_KEY) as iris_client:
            embedder = EmbeddingService()

            sync_service = SyncService(
                db_session=session,
                iris_client=iris_client,
                embedding_service=embedder,
            )

            try:
                await sync_service.sync_case(case_id, force_reindex)
                logger.info(f"Background sync completed for case {case_id}")
            except Exception as e:
                logger.error(f"Background sync failed for case {case_id}: {e}", exc_info=True)
            finally:
                await task_engine.dispose()


@router.post("/case/{case_id}", response_model=SyncResponse, status_code=202)
async def sync_case(
    case_id: int,
    request: SyncRequest = SyncRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    iris_client: IrisClient = Depends(get_iris_client),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    """
    Trigger sync job for an IRIS case.

    This endpoint accepts the request and launches a background task
    to perform the actual sync operation.

    Args:
        case_id: IRIS case ID to sync
        request: Sync request options
        background_tasks: FastAPI background tasks
        db: Database session
        iris_client: IRIS API client
        embedder: Embedding service

    Returns:
        SyncResponse with job_id for tracking

    Raises:
        404: Case not found in IRIS
        500: Sync initiation failed
    """
    try:
        # Verify case exists in IRIS
        case_data = await iris_client.get_case(case_id)

        logger.info(f"Sync requested for case {case_id}: {case_data.get('case_name')}")

        # Create sync service
        sync_service = SyncService(db, iris_client, embedder)

        # Create initial job record
        from app.db.models import SyncJob
        sync_job = SyncJob(
            case_id=case_id,
            status="pending",
            job_metadata={"force_reindex": request.force_reindex},
        )
        db.add(sync_job)
        await db.commit()
        await db.refresh(sync_job)

        # Launch background task
        background_tasks.add_task(
            run_sync_task,
            case_id,
            request.force_reindex,
            settings.DATABASE_URL,
        )

        return SyncResponse(
            status="accepted",
            job_id=sync_job.id,
            case_id=case_id,
            message=f"Sync job started for case {case_id} - {case_data.get('case_name')}"
        )

    except IrisNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Case {case_id} not found in IRIS"
        )
    except IrisAPIError as e:
        logger.error(f"IRIS API error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to communicate with IRIS: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to initiate sync for case {case_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate sync: {str(e)}"
        )


@router.get("/status/{job_id}", response_model=SyncJobStatus)
async def get_sync_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get status of a sync job.

    Args:
        job_id: Sync job ID
        db: Database session

    Returns:
        SyncJobStatus with current status

    Raises:
        404: Job not found
    """
    from sqlalchemy import select
    from app.db.models import SyncJob

    result = await db.execute(select(SyncJob).where(SyncJob.id == job_id))
    sync_job = result.scalar_one_or_none()

    if not sync_job:
        raise HTTPException(
            status_code=404,
            detail=f"Sync job {job_id} not found"
        )

    return SyncJobStatus(
        job_id=sync_job.id,
        case_id=sync_job.case_id,
        status=sync_job.status,
        started_at=sync_job.started_at,
        completed_at=sync_job.completed_at,
        documents_synced=sync_job.documents_synced,
        chunks_created=sync_job.chunks_created,
        error_message=sync_job.error_message,
    )


@router.get("/jobs", response_model=SyncJobList)
async def list_sync_jobs(
    case_id: Optional[int] = Query(None, description="Filter by case ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
):
    """
    List sync jobs with optional filters.

    Args:
        case_id: Optional case ID filter
        status: Optional status filter
        limit: Maximum number of results
        db: Database session

    Returns:
        SyncJobList with jobs and total count
    """
    from sqlalchemy import select, func
    from app.db.models import SyncJob

    # Build query
    query = select(SyncJob)

    if case_id is not None:
        query = query.where(SyncJob.case_id == case_id)

    if status is not None:
        query = query.where(SyncJob.status == status)

    query = query.order_by(SyncJob.started_at.desc()).limit(limit)

    # Execute query
    result = await db.execute(query)
    jobs = result.scalars().all()

    # Get total count
    count_query = select(func.count()).select_from(SyncJob)
    if case_id is not None:
        count_query = count_query.where(SyncJob.case_id == case_id)
    if status is not None:
        count_query = count_query.where(SyncJob.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return SyncJobList(
        jobs=[
            SyncJobStatus(
                job_id=job.id,
                case_id=job.case_id,
                status=job.status,
                started_at=job.started_at,
                completed_at=job.completed_at,
                documents_synced=job.documents_synced,
                chunks_created=job.chunks_created,
                error_message=job.error_message,
            )
            for job in jobs
        ],
        total=total,
    )
