"""
ChromaDB manager for ephemeral study session vector stores.

Each session gets its own collection (session_{id}) persisted at ~/.skb/chroma/.
Collections are created on session start and deleted on session end.
"""

import chromadb
from chromadb.config import Settings
from pathlib import Path
from langchain_community.vectorstores import Chroma
from utils.embedder import get_embeddings


# Persist directory for ChromaDB
CHROMA_DIR = Path.home() / ".skb" / "chroma"

# Global client (initialized once)
_client: chromadb.ClientAPI = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or create the persistent ChromaDB client."""
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
        print(f"[CHROMA] Initialized persistent client at {CHROMA_DIR}")
    return _client


def create_session_collection(session_id: str) -> Chroma:
    """
    Create a new ChromaDB collection for a study session.

    Args:
        session_id: MongoDB session ID

    Returns:
        LangChain Chroma vectorstore wrapping the collection
    """
    client = get_chroma_client()
    collection_name = f"session_{session_id}"

    # Create the raw collection with cosine similarity
    client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    # Return LangChain Chroma wrapper for easy document operations
    return Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=get_embeddings(),
    )


def get_session_collection(session_id: str) -> Chroma:
    """
    Get an existing ChromaDB collection for a study session.

    Args:
        session_id: MongoDB session ID

    Returns:
        LangChain Chroma vectorstore

    Raises:
        ValueError: If collection doesn't exist
    """
    client = get_chroma_client()
    collection_name = f"session_{session_id}"

    # Check if collection exists
    existing = [c.name for c in client.list_collections()]
    if collection_name not in existing:
        raise ValueError(
            f"No ChromaDB collection found for session {session_id}. "
            "Session may have ended or never started."
        )

    return Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=get_embeddings(),
    )


def delete_session_collection(session_id: str) -> bool:
    """
    Delete a ChromaDB collection entirely. No trace left.

    Args:
        session_id: MongoDB session ID

    Returns:
        True if deleted, False if collection didn't exist
    """
    client = get_chroma_client()
    collection_name = f"session_{session_id}"

    try:
        client.delete_collection(name=collection_name)
        print(f"[CHROMA] Deleted collection: {collection_name}")
        return True
    except Exception:
        print(f"[CHROMA] Collection {collection_name} not found (already deleted)")
        return False


def list_session_collections() -> list:
    """List all session collection names (for debugging/cleanup)."""
    client = get_chroma_client()
    collections = client.list_collections()
    return [c.name for c in collections if c.name.startswith("session_")]
