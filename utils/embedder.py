"""
Embedder utility using LangChain's HuggingFaceEmbeddings.

Wraps sentence-transformers/all-MiniLM-L6-v2 for 384-dimensional embeddings.
Loaded once on startup and reused throughout the application.
"""

from typing import List, Union
from langchain_huggingface import HuggingFaceEmbeddings


# Global instance (loaded once on startup)
_embeddings: HuggingFaceEmbeddings = None
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_model() -> HuggingFaceEmbeddings:
    """
    Load the embedding model into memory.

    This should be called once during server startup.
    First run will download ~90MB model file.
    """
    global _embeddings

    if _embeddings is None:
        print(f"[EMBEDDER] Loading model: {MODEL_NAME}")
        _embeddings = HuggingFaceEmbeddings(
            model_name=MODEL_NAME,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True},
        )
        # Warm up with a test embedding
        _embeddings.embed_query("test")
        print("[EMBEDDER] Model loaded successfully!")

    return _embeddings


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Get the global embeddings instance.

    Returns:
        Loaded HuggingFaceEmbeddings instance

    Raises:
        RuntimeError: If model hasn't been loaded yet
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
    """Get the dimensionality of the embedding vectors (384 for all-MiniLM-L6-v2)."""
    return 384
