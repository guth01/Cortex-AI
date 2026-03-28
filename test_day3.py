"""
Day 3 Test Suite — Session Lifecycle + ChromaDB + LangChain Pipeline

Tests:
1. ChromaDB collection CRUD
2. LangChain document loading
3. LangChain text splitting
4. Full pipeline: load → chunk → embed → store → query → delete
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.embedder import load_model
from utils.file_parser import load_documents, parse_file
from utils.chunker import split_documents, split_text, chunk_document
from db.chroma import (
    create_session_collection,
    get_session_collection,
    delete_session_collection,
    list_session_collections,
)


def test_chroma_crud():
    """Test ChromaDB collection create/get/delete."""
    print("\nTEST 1: ChromaDB Collection CRUD")

    test_id = "test_crud_123"

    # Create
    vs = create_session_collection(test_id)
    print(f"  ✓ Created collection: session_{test_id}")

    # Get
    vs2 = get_session_collection(test_id)
    print(f"  ✓ Retrieved collection: session_{test_id}")

    # List
    collections = list_session_collections()
    assert f"session_{test_id}" in collections, f"Expected session_{test_id} in {collections}"
    print(f"  ✓ Collection found in list ({len(collections)} total)")

    # Delete
    deleted = delete_session_collection(test_id)
    assert deleted, "Expected deletion to return True"
    collections = list_session_collections()
    assert f"session_{test_id}" not in collections
    print(f"  ✓ Collection deleted successfully")

    # Get after delete should raise
    try:
        get_session_collection(test_id)
        assert False, "Should have raised ValueError"
    except ValueError:
        print(f"  ✓ get_session_collection raises ValueError after delete")

    print("  ✅ ChromaDB CRUD test PASSED")


def test_langchain_loader():
    """Test LangChain document loading (replaces manual file_parser)."""
    print("\nTEST 2: LangChain Document Loading")

    test_file = "test_lc_document.txt"
    test_content = (
        "Artificial intelligence is a broad field of computer science.\n"
        "Machine learning is a subset of artificial intelligence.\n"
        "Deep learning uses neural networks with many layers.\n"
    ) * 10

    with open(test_file, "w", encoding="utf-8") as f:
        f.write(test_content)

    try:
        # New API: load_documents returns LangChain Document objects
        docs = load_documents(test_file, "txt")
        assert len(docs) > 0
        assert docs[0].page_content.strip()
        print(f"  ✓ load_documents: {len(docs)} Document(s), {len(docs[0].page_content)} chars")
        assert "source" in docs[0].metadata
        print(f"  ✓ Metadata has 'source': {docs[0].metadata['source']}")

        # Legacy API: parse_file returns raw string
        text = parse_file(test_file, "txt")
        assert len(text) > 0
        print(f"  ✓ parse_file (legacy): {len(text)} chars")

    finally:
        os.remove(test_file)

    print("  ✅ LangChain loader test PASSED")


def test_langchain_splitter():
    """Test LangChain text splitting (replaces manual chunker)."""
    print("\nTEST 3: LangChain Text Splitting")

    # Test with raw text
    text = (
        "The study of machine learning encompasses supervised learning, "
        "unsupervised learning, and reinforcement learning. "
    ) * 100

    chunks = split_text(text, metadata={"doc_id": "test123", "filename": "test.txt"})
    assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"
    print(f"  ✓ split_text: {len(chunks)} chunks from {len(text)} chars")
    assert chunks[0].metadata.get("doc_id") == "test123"
    print(f"  ✓ Metadata preserved: doc_id={chunks[0].metadata['doc_id']}")

    # Test legacy API
    legacy_chunks = chunk_document(
        text=text,
        doc_id="legacy_doc",
        filename="legacy.txt",
        subject_id="subj_1",
    )
    assert len(legacy_chunks) > 0
    assert legacy_chunks[0]["doc_id"] == "legacy_doc"
    assert legacy_chunks[0]["filename"] == "legacy.txt"
    print(f"  ✓ chunk_document (legacy): {len(legacy_chunks)} chunks with metadata")

    print("  ✅ Text splitter test PASSED")


def test_embedder():
    """Test LangChain HuggingFaceEmbeddings wrapper."""
    print("\nTEST 4: LangChain Embedder")

    from utils.embedder import embed, embed_batch, get_embedding_dimension

    # Single embedding
    vec = embed("Hello world")
    assert len(vec) == 384
    print(f"  ✓ Single embedding: {len(vec)} dimensions")

    # Batch embedding
    vecs = embed_batch(["Hello", "World", "Test"])
    assert len(vecs) == 3
    assert all(len(v) == 384 for v in vecs)
    print(f"  ✓ Batch embedding: {len(vecs)} vectors x {len(vecs[0])} dims")

    # Dimension check
    dim = get_embedding_dimension()
    assert dim == 384
    print(f"  ✓ Embedding dimension: {dim}")

    print("  ✅ Embedder test PASSED")


def test_full_pipeline():
    """Test full pipeline: load → chunk → embed → store in Chroma → query → delete."""
    print("\nTEST 5: Full Pipeline (Load → Chunk → Embed → Store → Query → Delete)")

    test_file = "test_pipeline.txt"
    test_session_id = "pipeline_test_456"

    # Create a document with distinct topics for search testing
    content = (
        "Machine learning is a method of data analysis that automates "
        "analytical model building. It is a branch of artificial intelligence "
        "based on the idea that systems can learn from data. "
    ) * 30 + "\n\n" + (
        "Photosynthesis is the process by which green plants convert "
        "sunlight into chemical energy. Chlorophyll absorbs light energy "
        "which is used to convert carbon dioxide and water into glucose. "
    ) * 30

    with open(test_file, "w", encoding="utf-8") as f:
        f.write(content)

    try:
        # 1. Load
        docs = load_documents(test_file, "txt")
        for doc in docs:
            doc.metadata.update({
                "doc_id": "test_doc_001",
                "filename": "test_pipeline.txt",
                "subject_id": "subj_test",
            })
        print(f"  ✓ Loaded {len(docs)} document(s)")

        # 2. Split
        chunks = split_documents(docs)
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
        print(f"  ✓ Split into {len(chunks)} chunks")

        # 3. Create Chroma collection + store
        vs = create_session_collection(test_session_id)
        vs.add_documents(chunks)
        print(f"  ✓ Stored {len(chunks)} chunks in ChromaDB")

        # 4. Query — should find ML-related chunks
        results = vs.similarity_search("machine learning algorithms", k=3)
        assert len(results) > 0
        assert "machine learning" in results[0].page_content.lower() or \
               "artificial intelligence" in results[0].page_content.lower()
        print(f"  ✓ Query 'machine learning': {len(results)} results")
        print(f"    Preview: {results[0].page_content[:80]}...")

        # 5. Query — should find biology-related chunks
        results2 = vs.similarity_search("photosynthesis plants", k=3)
        assert len(results2) > 0
        assert "photosynthesis" in results2[0].page_content.lower() or \
               "chlorophyll" in results2[0].page_content.lower()
        print(f"  ✓ Query 'photosynthesis': {len(results2)} results")
        print(f"    Preview: {results2[0].page_content[:80]}...")

        # 6. Verify metadata
        assert results[0].metadata.get("doc_id") == "test_doc_001"
        assert results[0].metadata.get("filename") == "test_pipeline.txt"
        print(f"  ✓ Metadata intact: doc_id={results[0].metadata['doc_id']}")

        # 7. Delete collection
        deleted = delete_session_collection(test_session_id)
        assert deleted
        collections = list_session_collections()
        assert f"session_{test_session_id}" not in collections
        print(f"  ✓ Collection deleted — no trace left")

    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

    print("  ✅ Full pipeline test PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("DAY 3 TEST SUITE")
    print("Sessions + ChromaDB + LangChain Pipeline")
    print("=" * 60)

    # Load embedder on startup (same as server does)
    print("\n🤖 Loading embedding model...")
    load_model()

    test_chroma_crud()
    test_langchain_loader()
    test_langchain_splitter()
    test_embedder()
    test_full_pipeline()

    print("\n" + "=" * 60)
    print("🎉 ALL DAY 3 TESTS PASSED!")
    print("=" * 60)
