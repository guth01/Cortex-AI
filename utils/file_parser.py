"""
Document loader utility using LangChain.

Supports: PDF, DOCX, Markdown, and plain text files.
Uses LangChain document loaders under the hood.
"""

import os
from typing import List
from langchain_core.documents import Document


def load_documents(file_path: str, source_type: str) -> List[Document]:
    """
    Load a file using the appropriate LangChain document loader.

    Args:
        file_path: Absolute path to the file
        source_type: Type of file (pdf, docx, md, txt)

    Returns:
        List of LangChain Document objects (one per page for PDFs, one for others)

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If source_type is not supported or file has no text
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    source_type = source_type.lower()

    if source_type == "pdf":
        try:
            from langchain_community.document_loaders import PyMuPDFLoader
            loader = PyMuPDFLoader(file_path)
            docs = loader.load()
        except ImportError:
            print("⚠️ PyMuPDF not found. Falling back to PyPDFLoader. Run `pip install pymupdf` for better PDF text extraction.")
            from langchain_community.document_loaders import PyPDFLoader
            loader = PyPDFLoader(file_path)
            docs = loader.load()

    elif source_type == "docx":
        from langchain_community.document_loaders import Docx2txtLoader
        loader = Docx2txtLoader(file_path)
        docs = loader.load()

    elif source_type in ["md", "txt"]:
        from langchain_community.document_loaders import TextLoader
        try:
            loader = TextLoader(file_path, encoding="utf-8")
            docs = loader.load()
        except Exception:
            # Fallback for non-UTF-8 files
            loader = TextLoader(file_path, encoding="latin-1")
            docs = loader.load()

    else:
        raise ValueError(
            f"Unsupported source type: {source_type}. Supported: pdf, docx, md, txt"
        )

    if not docs or not any(doc.page_content.strip() for doc in docs):
        raise ValueError(f"No extractable text found in {file_path}")

    return docs


def parse_file(file_path: str, source_type: str) -> str:
    """
    Extract text content from a file as a single string.
    Legacy API — prefer load_documents() for LangChain pipeline.

    Args:
        file_path: Absolute path to the file
        source_type: Type of file (pdf, docx, md, txt)

    Returns:
        Extracted text content as a string
    """
    docs = load_documents(file_path, source_type)
    return "\n\n".join(doc.page_content for doc in docs)


def get_file_info(file_path: str) -> dict:
    """
    Get basic information about a file.

    Returns:
        Dictionary with file name, size, extension, size_mb
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    file_ext = os.path.splitext(file_name)[1].lower().replace('.', '')

    return {
        "name": file_name,
        "size": file_size,
        "extension": file_ext,
        "size_mb": round(file_size / (1024 * 1024), 2)
    }
