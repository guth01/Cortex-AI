"""
Text chunker utility using LangChain's RecursiveCharacterTextSplitter.

Uses tiktoken for accurate token-based chunk sizing.
"""

from typing import List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


# Default configuration
DEFAULT_CHUNK_SIZE = 400   # tokens
DEFAULT_OVERLAP = 100       # tokens
DEFAULT_ENCODING = "cl100k_base"


def get_text_splitter(
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_OVERLAP,
    encoding_name: str = DEFAULT_ENCODING,
) -> RecursiveCharacterTextSplitter:
    """
    Create a LangChain text splitter with tiktoken-based token counting.

    Args:
        chunk_size: Maximum tokens per chunk
        chunk_overlap: Overlap tokens between consecutive chunks
        encoding_name: Tiktoken encoding name

    Returns:
        Configured RecursiveCharacterTextSplitter
    """
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=encoding_name,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def split_documents(
    documents: List[Document],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_OVERLAP,
) -> List[Document]:
    """
    Split LangChain Documents into smaller chunks.

    Metadata from original documents is preserved in each chunk.

    Args:
        documents: List of LangChain Document objects
        chunk_size: Max tokens per chunk
        chunk_overlap: Overlap tokens between chunks

    Returns:
        List of chunked Document objects with preserved metadata
    """
    splitter = get_text_splitter(chunk_size, chunk_overlap)
    return splitter.split_documents(documents)


def split_text(
    text: str,
    metadata: dict = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_OVERLAP,
) -> List[Document]:
    """
    Split raw text into Document chunks.

    Args:
        text: Raw text string
        metadata: Optional metadata dict to attach to every chunk
        chunk_size: Max tokens per chunk
        chunk_overlap: Overlap tokens

    Returns:
        List of Document chunks
    """
    splitter = get_text_splitter(chunk_size, chunk_overlap)
    docs = splitter.create_documents(
        texts=[text],
        metadatas=[metadata] if metadata else None,
    )
    return docs


def chunk_document(
    text: str,
    doc_id: str,
    filename: str,
    subject_id: str = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> List[Dict[str, any]]:
    """
    Legacy API — Chunk a document with standard metadata.
    Returns list of dicts for backward compatibility with test_day2.py.
    """
    metadata = {"doc_id": doc_id, "filename": filename}
    if subject_id:
        metadata["subject_id"] = subject_id

    docs = split_text(text, metadata, chunk_size, overlap)

    chunks = []
    for i, doc in enumerate(docs):
        chunk = {
            "text": doc.page_content,
            "chunk_index": i,
            "total_chunks": len(docs),
            **doc.metadata,
        }
        chunks.append(chunk)

    return chunks
