import sys
import os
import argparse
from pprint import pprint

# Import modules from the project
from utils.embedder import load_model
from utils.file_parser import load_documents
from utils.chunker import split_documents
from db.chroma import create_session_collection, delete_session_collection
from agent.tools import search_notes

def main():
    parser = argparse.ArgumentParser(description="Test RAG retrieval functionality airtight.")
    parser.add_argument("query", help="The search query to test against the document")
    parser.add_argument("--top_k", type=int, default=5, help="Number of chunks to retrieve")
    args = parser.parse_args()

    file_path = "software_engineering_note.pdf"
    query = args.query

    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        sys.exit(1)

    print("🚀 Initializing Embedder...")
    load_model()

    session_id = "test_rag_session_123"
    
    # 1. Clean up any previous test sessions just in case
    delete_session_collection(session_id)

    print(f"\n📄 Loading and parsing document: {file_path}")
    ext = os.path.splitext(file_path)[1].replace(".", "").lower()
    docs = load_documents(file_path, ext)
    print(f"   -> Extracted {len(docs)} page(s)/section(s) of text.")

    print("\n✂️ Chunking document...")
    chunks = split_documents(docs)
    print(f"   -> Split into {len(chunks)} chunks.")

    print("\n📦 Ingesting into ephemeral ChromaDB session...")
    vs = create_session_collection(session_id)
    vs.add_documents(chunks)
    print("   -> Ingestion complete.")

    print(f"\n🔍 Querying RAG System for: '{query}'")
    result = search_notes(query, session_id=session_id, top_k=args.top_k)

    print(f"\n==========================================")
    print(f"RAG Confidence Score: {result.get('confidence', 0):.4f}")
    print(f"Chunks Found: {len(result.get('chunks', []))}")
    print(f"==========================================")

    for i, chunk in enumerate(result.get("chunks", [])):
        print(f"\n--- Chunk {i+1} | Score: {chunk['score']:.4f} ---")
        print(chunk["content"].strip())
    
    print("\n🧹 Cleaning up test session...")
    delete_session_collection(session_id)
    print("✅ Done.")

if __name__ == "__main__":
    main()
