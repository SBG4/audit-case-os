"""
RAG Gateway - Main FastAPI Application

AI-powered investigation assistance via Retrieval-Augmented Generation.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.config import get_settings
from app.api.v1 import api_router
from app.db.session import init_db, close_db

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown events."""
    logger.info("Starting RAG Gateway", version="1.0.0", environment=settings.APP_ENV)

    # Startup: Initialize database
    try:
        await init_db()
        logger.info("Database initialized")

        # Warm up embedding model
        from rag.embedder import EmbeddingService
        embedder = EmbeddingService()
        await embedder.warm_up()
        logger.info("Embedding model loaded", model=settings.EMBEDDING_MODEL)

        yield

    finally:
        # Shutdown: Cleanup
        logger.info("Shutting down RAG Gateway")
        await close_db()
        logger.info("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="RAG Gateway",
        description="AI-powered investigation assistance via Retrieval-Augmented Generation",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(api_router)

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "service": "RAG Gateway",
            "version": "1.0.0",
            "status": "operational",
            "docs": "/docs"
        }

    # Health check endpoint
    @app.get("/health")
    async def health():
        """Health check endpoint for Docker and monitoring."""
        from app.db.session import engine
        from sqlalchemy import text

        health_status = {
            "status": "healthy",
            "version": "1.0.0",
            "services": {}
        }

        # Check database
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            health_status["services"]["database"] = "up"
        except Exception as e:
            health_status["services"]["database"] = "down"
            health_status["status"] = "unhealthy"
            logger.error("Database health check failed", error=str(e))

        # Check embedding model
        try:
            from rag.embedder import EmbeddingService
            embedder = EmbeddingService()
            health_status["services"]["embeddings"] = "up" if embedder.is_loaded() else "down"
        except Exception:
            health_status["services"]["embeddings"] = "down"

        # Check IRIS connectivity
        health_status["services"]["iris"] = "configured" if settings.is_iris_configured() else "not_configured"

        return JSONResponse(
            content=health_status,
            status_code=200 if health_status["status"] == "healthy" else 503
        )

    logger.info("FastAPI application created")
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
