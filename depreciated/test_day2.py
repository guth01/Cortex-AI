"""
Day 2 Test Script

Test file parsing, chunking, and embedding functionality.
Run this after starting the server to verify everything works.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.file_parser import parse_file, get_file_info
from utils.chunker import chunk_document, default_chunker
from utils.embedder import load_model, embed, get_embedding_dimension


def test_parser():
    """Test file parser with a sample text file."""
    print("=" * 60)
    print("TEST 1: File Parser")
    print("=" * 60)
    
    # Create a test text file
    test_file = Path("test_document.txt")
    test_content = """
    This is a test document for the Study Agent system.
    
    It contains multiple paragraphs to test the parsing functionality.
    The parser should extract this text correctly.
    
    Binary trees are hierarchical data structures.
    Each node can have at most two children: left and right.
    """
    
    test_file.write_text(test_content)
    
    try:
        # Test parsing
        parsed_text = parse_file(str(test_file), "txt")
        print(f"\n✓ Parsed text ({len(parsed_text)} chars):")
        print(parsed_text[:200] + "...")
        
        # Test file info
        info = get_file_info(str(test_file))
        print(f"\n✓ File info:")
        print(f"  Name: {info['name']}")
        print(f"  Size: {info['size']} bytes")
        print(f"  Extension: {info['extension']}")
        
    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()
    
    print("\n✅ File parser test PASSED\n")


def test_chunker():
    """Test text chunker with token counting."""
    print("=" * 60)
    print("TEST 2: Text Chunker")
    print("=" * 60)
    
    # Sample text
    text = """
    Binary search trees (BST) are fundamental data structures in computer science.
    A BST is a binary tree where each node has a comparable key and satisfies:
    - All keys in the left subtree are less than the node's key
    - All keys in the right subtree are greater than the node's key
    
    Operations on BSTs:
    1. Search: O(h) where h is height
    2. Insert: O(h)
    3. Delete: O(h)
    
    Balanced BSTs maintain h = O(log n) to ensure efficient operations.
    """ * 10  # Repeat to create more content
    
    print(f"\nOriginal text: {len(text)} characters")
    
    # Count tokens
    token_count = default_chunker.count_tokens(text)
    print(f"Token count: {token_count} tokens")
    
    # Chunk the text
    chunks = chunk_document(
        text=text,
        doc_id="test_doc_123",
        filename="bst_notes.pdf",
        subject_id="data_structures",
        chunk_size=100,  # Small chunks for testing
        overlap=20
    )
    
    print(f"\n✓ Created {len(chunks)} chunks")
    print(f"\nFirst chunk:")
    print(f"  Text: {chunks[0]['text'][:100]}...")
    print(f"  Tokens: {chunks[0]['token_count']}")
    print(f"  Index: {chunks[0]['chunk_index']}/{chunks[0]['total_chunks']}")
    print(f"  Metadata: doc_id={chunks[0]['doc_id']}, filename={chunks[0]['filename']}")
    
    print("\n✅ Chunker test PASSED\n")


def test_embedder():
    """Test embedding model."""
    print("=" * 60)
    print("TEST 3: Embedder")
    print("=" * 60)
    
    # Load model
    print("\nLoading embedding model...")
    load_model()
    
    # Get embedding dimension
    dim = get_embedding_dimension()
    print(f"✓ Model loaded. Embedding dimension: {dim}")
    
    # Test single string embedding
    text = "Binary trees are hierarchical data structures"
    embedding = embed(text)
    print(f"\n✓ Single embedding:")
    print(f"  Text: '{text}'")
    print(f"  Vector length: {len(embedding)}")
    print(f"  First 5 values: {embedding[:5]}")
    
    # Test batch embedding
    texts = [
        "What is a binary tree?",
        "Explain AVL tree rotations",
        "How does heap sort work?"
    ]
    embeddings = embed(texts)
    print(f"\n✓ Batch embedding:")
    print(f"  Texts: {len(texts)}")
    print(f"  Embeddings: {len(embeddings)}")
    print(f"  Each vector length: {len(embeddings[0])}")
    
    print("\n✅ Embedder test PASSED\n")


def test_full_pipeline():
    """Test the complete pipeline: parse → chunk → embed."""
    print("=" * 60)
    print("TEST 4: Full Pipeline")
    print("=" * 60)
    
    # Create test file
    test_file = Path("test_lecture.md")
    content = """# Data Structures Lecture 3: Binary Trees

## Introduction
A binary tree is a tree data structure where each node has at most two children.

## Properties
- Each node contains a value
- Left subtree of a node contains only nodes with values less than the node's value
- Right subtree contains only nodes with values greater than the node's value

## Time Complexity
- Search: O(log n) for balanced trees
- Insert: O(log n)
- Delete: O(log n)

## Applications
Binary trees are used in:
1. Expression parsing
2. Huffman coding
3. Binary search trees
4. Heap data structures
"""
    
    test_file.write_text(content)
    
    try:
        # Step 1: Parse
        print("\nStep 1: Parsing markdown file...")
        parsed_text = parse_file(str(test_file), "md")
        print(f"✓ Extracted {len(parsed_text)} characters")
        
        # Step 2: Chunk
        print("\nStep 2: Chunking text...")
        chunks = chunk_document(
            text=parsed_text,
            doc_id="lecture_3",
            filename="test_lecture.md",
            subject_id="data_structures",
            chunk_size=150,
            overlap=30
        )
        print(f"✓ Created {len(chunks)} chunks")
        
        # Step 3: Embed
        print("\nStep 3: Embedding chunks...")
        chunk_texts = [chunk["text"] for chunk in chunks]
        embeddings = embed(chunk_texts)
        print(f"✓ Generated {len(embeddings)} embeddings")
        
        # Verify
        print(f"\n✓ Pipeline successful:")
        print(f"  Input: {test_file.name}")
        print(f"  Chunks: {len(chunks)}")
        print(f"  Embeddings: {len(embeddings)} x {len(embeddings[0])}")
        
    finally:
        if test_file.exists():
            test_file.unlink()
    
    print("\n✅ Full pipeline test PASSED\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("DAY 2 TEST SUITE")
    print("=" * 60 + "\n")
    
    try:
        test_parser()
        test_chunker()
        test_embedder()
        test_full_pipeline()
        
        print("=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
