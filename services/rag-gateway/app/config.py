"""Configuration management using Pydantic Settings."""
from functools import lru_cache
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Application
    APP_NAME: str = "rag-gateway"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"])

    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/1"

    # DFIR-IRIS
    IRIS_API_URL: str = Field(..., description="DFIR-IRIS base URL")
    IRIS_API_KEY: str = Field(default="", description="DFIR-IRIS API key")
    IRIS_TIMEOUT: int = 30

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = ""
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "evidence"

    # Nextcloud (Phase 2)
    NEXTCLOUD_URL: str = "http://localhost:8081"
    NEXTCLOUD_USERNAME: str = "admin"
    NEXTCLOUD_PASSWORD: str = ""
    NEXTCLOUD_EVIDENCE_ROOT: str = "/Evidence"

    # Paperless-ngx (Phase 2)
    PAPERLESS_URL: str = "http://localhost:8083"
    PAPERLESS_TOKEN: str = ""
    PAPERLESS_TIMEOUT: int = 60

    # Ollama (Optional)
    OLLAMA_ENABLED: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_TIMEOUT: int = 120

    # Embeddings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 32

    # RAG Configuration
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    SEARCH_TOP_K: int = 20
    RERANK_TOP_K: int = 5
    MIN_SIMILARITY_SCORE: float = 0.5

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v_upper

    def is_iris_configured(self) -> bool:
        """Check if IRIS integration is properly configured."""
        return bool(self.IRIS_API_KEY and self.IRIS_API_URL)

    def is_nextcloud_configured(self) -> bool:
        """Check if Nextcloud integration is properly configured."""
        return bool(self.NEXTCLOUD_PASSWORD)

    def is_paperless_configured(self) -> bool:
        """Check if Paperless integration is properly configured."""
        return bool(self.PAPERLESS_TOKEN)

    def is_ollama_enabled(self) -> bool:
        """Check if Ollama is enabled and configured."""
        return self.OLLAMA_ENABLED


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
