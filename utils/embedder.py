"""
Embedder utility using Google Gemini text-embedding-004 via API.

Uses the Gemini API for embeddings — no local model download needed.
Model: text-embedding-004 (768 dimensions, optimized for retrieval).
Uses a dedicated API key (GEMINI_EMBEDDING_API_KEY) to avoid rate-limit
conflicts with the chat/LLM keys.
"""

import os
from typing import List, Union
from langchain_google_genai import GoogleGenerativeAIEmbeddings


# Global instance (initialized lazily on first use)
_embeddings: GoogleGenerativeAIEmbeddings = None
MODEL_NAME = "models/gemini-embedding-001"


def load_model() -> GoogleGenerativeAIEmbeddings:
    """
    Initialize the Gemini embedding model (API-based, no local download).

    Uses GEMINI_EMBEDDING_API_KEY from environment.
    This should be called once during server startup or lazily on first use.
    """
    global _embeddings

    if _embeddings is None:
        api_key = os.getenv("GEMINI_EMBEDDING_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_EMBEDDING_API_KEY not set in environment. "
                "Please add it to your .env file."
            )

        print(f"[EMBEDDER] Initializing Gemini API embeddings: {MODEL_NAME}")
        _embeddings = GoogleGenerativeAIEmbeddings(
            model=MODEL_NAME,
            google_api_key=api_key,
            task_type="retrieval_document",
        )
        # Warm up with a test embedding to verify the API key works
        _embeddings.embed_query("test")
        print("[EMBEDDER] ✓ Gemini embeddings ready!")

    return _embeddings


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """
    Get the global embeddings instance.

    Returns:
        Loaded GoogleGenerativeAIEmbeddings instance

    Raises:
        RuntimeError: If API key is missing or invalid
    """
    if _embeddings is None:
        load_model()
    return _embeddings


def embed(text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
    """
    Generate embeddings for text or list of texts.

    Args:
        text: Single text string or list of text strings

    Returns:
        Single embedding vector or list of embedding vectors
    """
    emb = get_embeddings()
    if isinstance(text, str):
        return emb.embed_query(text)
    else:
        return emb.embed_documents(text)


def embed_batch(
    texts: List[str],
    batch_size: int = 32,
    show_progress: bool = False
) -> List[List[float]]:
    """
    Generate embeddings for a batch of texts.

    Args:
        texts: List of text strings to embed
        batch_size: Ignored (kept for backward compatibility)
        show_progress: Ignored (kept for backward compatibility)

    Returns:
        List of embedding vectors
    """
    emb = get_embeddings()
    return emb.embed_documents(texts)


def get_embedding_dimension() -> int:
    """Get the dimensionality of the embedding vectors (768 for text-embedding-004)."""
    return 768
