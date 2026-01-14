"""Embedding generation service using Sentence Transformers."""
import asyncio
from typing import Optional
import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class EmbeddingService:
    """Handles text embedding generation using Sentence Transformers."""

    _model: Optional[any] = None
    _model_lock = asyncio.Lock()
    _loaded = False

    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        self.batch_size = settings.EMBEDDING_BATCH_SIZE
        self.dimension = settings.EMBEDDING_DIMENSION
        self.log = logger.bind(model=self.model_name)

    @classmethod
    async def warm_up(cls) -> None:
        """Pre-load the embedding model on startup."""
        async with cls._model_lock:
            if cls._model is None:
                logger.info("Loading embedding model", model=settings.EMBEDDING_MODEL)
                try:
                    # Import here to avoid issues if library not installed
                    from sentence_transformers import SentenceTransformer

                    # Load model in executor to avoid blocking
                    loop = asyncio.get_event_loop()
                    cls._model = await loop.run_in_executor(
                        None,
                        SentenceTransformer,
                        settings.EMBEDDING_MODEL
                    )

                    # Warm up with test embedding
                    await loop.run_in_executor(
                        None,
                        cls._model.encode,
                        ["warm up test"]
                    )

                    cls._loaded = True
                    logger.info(
                        "Embedding model loaded successfully",
                        dimension=cls._model.get_sentence_embedding_dimension()
                    )
                except Exception as e:
                    logger.error("Failed to load embedding model", error=str(e))
                    raise

    @property
    def model(self):
        """Get the loaded model instance."""
        if self._model is None:
            raise RuntimeError("Embedding model not loaded. Call warm_up() first.")
        return self._model

    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._loaded

    async def embed_single(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        if not text.strip():
            raise ValueError("Cannot embed empty text")

        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: self.model.encode(text, normalize_embeddings=True)
        )

        return embedding.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter out empty texts
        valid_texts = [t for t in texts if t.strip()]
        if not valid_texts:
            return []

        loop = asyncio.get_event_loop()

        # Process in batches to avoid memory issues
        all_embeddings = []
        for i in range(0, len(valid_texts), self.batch_size):
            batch = valid_texts[i:i + self.batch_size]

            embeddings = await loop.run_in_executor(
                None,
                lambda b=batch: self.model.encode(
                    b,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    batch_size=self.batch_size
                )
            )

            all_embeddings.extend(embeddings.tolist())
            self.log.debug(
                "Processed embedding batch",
                batch_num=i // self.batch_size + 1,
                batch_size=len(batch)
            )

        return all_embeddings

    def get_dimension(self) -> int:
        """Get the embedding dimension."""
        if self._loaded and self._model:
            return self._model.get_sentence_embedding_dimension()
        return self.dimension
