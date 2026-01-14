"""
Document chunking with token-based segmentation.

Implements fixed-size chunking with overlap to preserve context across boundaries.
Uses tiktoken for accurate token counting compatible with GPT models.
"""

import logging
from typing import List, Dict, Any, Optional
import tiktoken

logger = logging.getLogger(__name__)


class DocumentChunker:
    """
    Split documents into fixed-size chunks with overlap.

    Chunks are created based on token count rather than character count
    for consistency with embedding models and LLMs.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 128,
        encoding_name: str = "cl100k_base",
    ):
        """
        Initialize document chunker.

        Args:
            chunk_size: Target size of each chunk in tokens (default: 512)
            chunk_overlap: Number of overlapping tokens between chunks (default: 128)
            encoding_name: Tiktoken encoding to use (default: cl100k_base for GPT-4)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
        except Exception as e:
            logger.warning(f"Failed to load encoding {encoding_name}, falling back to cl100k_base: {e}")
            self.encoding = tiktoken.get_encoding("cl100k_base")

        logger.info(
            f"Initialized chunker: chunk_size={chunk_size}, "
            f"overlap={chunk_overlap}, encoding={encoding_name}"
        )

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in text.

        Args:
            text: Text to count

        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Split text into chunks with overlap.

        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk

        Returns:
            List of chunk dictionaries with keys:
            - content: Chunk text
            - token_count: Number of tokens in chunk
            - chunk_index: Sequential index (0-based)
            - metadata: Merged metadata
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to chunker")
            return []

        # Encode the entire text
        tokens = self.encoding.encode(text)
        total_tokens = len(tokens)

        logger.debug(f"Chunking text with {total_tokens} tokens")

        chunks = []
        chunk_index = 0
        start_idx = 0

        while start_idx < total_tokens:
            # Calculate end index for this chunk
            end_idx = min(start_idx + self.chunk_size, total_tokens)

            # Extract chunk tokens
            chunk_tokens = tokens[start_idx:end_idx]

            # Decode back to text
            chunk_text = self.encoding.decode(chunk_tokens)

            # Create chunk metadata
            chunk_metadata = {
                "chunk_index": chunk_index,
                "start_token": start_idx,
                "end_token": end_idx,
                "total_document_tokens": total_tokens,
            }

            # Merge with provided metadata
            if metadata:
                chunk_metadata.update(metadata)

            chunks.append({
                "content": chunk_text,
                "token_count": len(chunk_tokens),
                "chunk_index": chunk_index,
                "metadata": chunk_metadata,
            })

            # Move to next chunk with overlap
            start_idx = end_idx - self.chunk_overlap
            chunk_index += 1

            # Avoid infinite loop if overlap >= chunk_size
            if start_idx >= end_idx:
                break

        logger.info(f"Created {len(chunks)} chunks from {total_tokens} tokens")
        return chunks

    def chunk_with_sentence_boundaries(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Split text into chunks while trying to preserve sentence boundaries.

        This is a more sophisticated approach that attempts to split at sentence
        boundaries when possible, while still respecting token limits.

        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk

        Returns:
            List of chunk dictionaries
        """
        # For now, use simple chunking
        # TODO: Implement sentence boundary detection for better semantic coherence
        # This would require a sentence tokenizer (e.g., nltk.sent_tokenize)
        return self.chunk_text(text, metadata)


# Global instance for convenience
default_chunker = DocumentChunker()


def chunk_document(text: str, **kwargs) -> List[Dict[str, Any]]:
    """
    Convenience function to chunk a document using default settings.

    Args:
        text: Text to chunk
        **kwargs: Additional arguments passed to chunk_text

    Returns:
        List of chunk dictionaries
    """
    return default_chunker.chunk_text(text, **kwargs)
