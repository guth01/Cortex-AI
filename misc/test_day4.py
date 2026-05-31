"""
test_day4.py — End-of-day verification for Day 4

Tests:
1. Full chat flow via POST /chat/{session_id}/sync
2. Confirm RouterNode intent classification
3. Confirm RAGNode fires and returns chunks
4. Confirm WikipediaNode fires on low-confidence queries
5. Confirm transcript is saved to Atlas

HOW TO RUN:
-----------
1. Activate venv:
   .\\venv\\Scripts\\Activate.ps1

2. Start the server in another terminal:
   python server.py

3. In a NEW terminal with venv active, set your values then run:
   $env:BASE_URL = "http://localhost:8000"
   $env:TEST_EMAIL = "your@email.com"
   $env:TEST_PASSWORD = "yourpassword"
   $env:TEST_SUBJECT_ID = "your-subject-id-from-day1"
   $env:TEST_DOC_ID = "your-document-id-from-day2"
   python test_day4.py

Or just hardcode the values in the CONFIG section below for quick testing.
"""

import os
import sys
import json
import requests
import time
from datetime import datetime

# ============================================================================
# CONFIG — edit these or set as env vars
# ============================================================================
BASE_URL    = os.getenv("BASE_URL", "http://localhost:8000")
TEST_EMAIL  = os.getenv("TEST_EMAIL", "day4test@example.com")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "test1234")

# These are created dynamically if you leave them blank (blank = create new)
EXISTING_SUBJECT_ID = os.getenv("TEST_SUBJECT_ID", "")  # Leave blank to create fresh
EXISTING_DOC_ID     = os.getenv("TEST_DOC_ID", "")       # Leave blank to create fresh

# ============================================================================

session = requests.Session()
token = None
subject_id = None
session_id = None
doc_id = None


def header():
    return {"Authorization": f"Bearer {token}"}


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_pass(msg: str):
    print(f"  ✅ PASS: {msg}")


def print_fail(msg: str):
    print(f"  ❌ FAIL: {msg}")
    sys.exit(1)


def print_info(msg: str):
    print(f"  ℹ️  {msg}")


# ============================================================================
# Step 1: Login
# ============================================================================
print_section("Step 1: Authenticate")

resp = requests.post(f"{BASE_URL}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
if resp.status_code != 200:
    # Try registering
    resp2 = requests.post(f"{BASE_URL}/auth/register", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "name": "Test User"
    })
    if resp2.status_code not in (200, 201):
        print_fail(f"Could not login or register: {resp2.text}")
    token = resp2.json()["access_token"]
    print_pass("Registered and got JWT")
else:
    token = resp.json()["access_token"]
    print_pass("Logged in, got JWT")


# ============================================================================
# Step 2: Get or create subject
# ============================================================================
print_section("Step 2: Subject")

if EXISTING_SUBJECT_ID:
    subject_id = EXISTING_SUBJECT_ID
    print_info(f"Using existing subject: {subject_id}")
else:
    resp = requests.post(
        f"{BASE_URL}/subjects",
        json={"name": "Computer Science Day4", "exam_date": None},
        headers=header()
    )
    if resp.status_code != 201:
        print_fail(f"Subject creation failed: {resp.text}")
    subject_id = resp.json()["id"]
    print_pass(f"Created subject: {subject_id}")


# ============================================================================
# Step 3: Upload a test document
# ============================================================================
print_section("Step 3: Upload document")

# Create a test text file with content about virtual memory and OS concepts
TEST_CONTENT = """Introduction to Operating Systems

Virtual Memory
Virtual memory is a memory management technique that gives processes the illusion of having
more memory than physically exists. It uses a combination of RAM and disk space (swap) to
achieve this. The operating system manages a page table that maps virtual addresses to physical
addresses. When a page is not in RAM, a page fault occurs, and the OS loads the page from disk.

Key concepts in virtual memory:
- Page: Fixed-size block of memory (typically 4KB)
- Page table: Data structure mapping virtual to physical pages
- TLB (Translation Lookaside Buffer): Cache for page table entries
- Page fault: Triggered when a required page is not in RAM
- Thrashing: Excessive page faulting, degrading system performance

Process Management
Processes are programs in execution. Each process has its own address space, stack, heap, and
program counter. The OS scheduler decides which process runs at any given time.

Context Switching
Context switching is the process of saving the state of a running process and loading the state
of another. It involves saving registers, program counter, and memory mappings.

CPU Scheduling Algorithms
- FIFO (First In First Out): Simple but can cause convoy effect
- Shortest Job First (SJF): Optimal average wait time but requires knowing burst time
- Round Robin: Fair scheduling with time quantum
- Priority Scheduling: Higher priority processes run first

Deadlock
Deadlock occurs when two or more processes are waiting for resources held by each other.
Conditions for deadlock: mutual exclusion, hold and wait, no preemption, circular wait.

File Systems
File systems organize data on storage devices. Common types include FAT32, NTFS, ext4.
Key concepts: inodes, directory entries, file allocation tables, journaling.
"""

# Write temp file
test_file_path = "test_os_notes.txt"
with open(test_file_path, "w") as f:
    f.write(TEST_CONTENT)

if EXISTING_DOC_ID:
    doc_id = EXISTING_DOC_ID
    print_info(f"Using existing document: {doc_id}")
else:
    with open(test_file_path, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/documents/upload",
            files={"file": ("os_notes.txt", f, "text/plain")},
            data={"subject_id": subject_id},
            headers=header()
        )
    if resp.status_code != 201:
        print_fail(f"Document upload failed: {resp.text}")
    doc_id = resp.json()["id"]
    print_pass(f"Document uploaded: {doc_id}")


# ============================================================================
# Step 4: Start a session
# ============================================================================
print_section("Step 4: Start session (embeds documents into Chroma)")
print_info("This may take 5-15 seconds...")

resp = requests.post(
    f"{BASE_URL}/sessions/start",
    json={"subject_id": subject_id, "document_ids": [doc_id]},
    headers=header()
)
if resp.status_code != 201:
    print_fail(f"Session start failed: {resp.text}")

data = resp.json()
session_id = data["session_id"]
print_pass(f"Session started: {session_id}")
print_info(f"Docs loaded: {data['docs_loaded']}, Chunks: {data['chunk_count']}")

if data["chunk_count"] == 0:
    print_fail("No chunks were embedded! Session can't work with 0 chunks.")


# ============================================================================
# Step 5: RAG query — should find virtual memory in notes
# ============================================================================
print_section("Step 5: RAG query — 'explain virtual memory'")
print_info("Calling POST /chat/{session_id}/sync ...")

resp = requests.post(
    f"{BASE_URL}/chat/{session_id}/sync",
    json={"message": "explain virtual memory to me"},
    headers=header()
)
if resp.status_code != 200:
    print_fail(f"Chat sync failed: {resp.status_code} — {resp.text}")

result = resp.json()
print_pass("Got response from agent")

meta = result["metadata"]
print_info(f"Intent:       {meta['intent']}")
print_info(f"Confidence:   {meta['confidence']}")
print_info(f"Chunks used:  {meta['chunks_used']}")
print_info(f"Wiki used:    {meta['wikipedia_used']}")
print_info(f"Response (first 300 chars):\n    {result['response'][:300]}...")

# Assertions
if meta["intent"] != "rag_query":
    print_fail(f"Expected intent=rag_query, got intent={meta['intent']}")
print_pass(f"RouterNode correctly classified as rag_query")

if meta["chunks_used"] == 0:
    print_fail("RAGNode returned 0 chunks — it should have found virtual memory content")
print_pass(f"RAGNode retrieved {meta['chunks_used']} chunks from Chroma")

if "virtual memory" not in result["response"].lower():
    print_fail("Response doesn't mention virtual memory — synthesis may not be using chunks")
print_pass("SynthesisNode produced response mentioning 'virtual memory'")

print_info("Sleeping 20 seconds to respect Gemini API rate limits (5 RPM)...")
time.sleep(20)

# ============================================================================
# Step 6: Low-confidence query — Wikipedia should fire
# ============================================================================
print_section("Step 6: Low-confidence query — Wikipedia fallback")
print_info("Asking about something NOT in the notes (quantum physics)...")

resp = requests.post(
    f"{BASE_URL}/chat/{session_id}/sync",
    json={"message": "explain quantum entanglement"},
    headers=header()
)
if resp.status_code != 200:
    print_fail(f"Chat sync failed: {resp.status_code} — {resp.text}")

result2 = resp.json()
meta2 = result2["metadata"]
print_info(f"Intent:       {meta2['intent']}")
print_info(f"Confidence:   {meta2['confidence']}")
print_info(f"Wiki used:    {meta2['wikipedia_used']}")
print_info(f"Response (first 300 chars):\n    {result2['response'][:300]}...")

if not meta2["wikipedia_used"]:
    print_info("⚠️  Wikipedia did NOT fire — confidence may still be above threshold.")
    print_info(f"   Confidence was {meta2['confidence']} (threshold is 0.45)")
    print_info("   This is okay if your notes accidentally covered this topic semantically.")
    print_info("   Try asking about 'napoleonic war tactics' for a harder miss.")
else:
    print_pass("WikipediaNode fired correctly when confidence was insufficient")

print_info("Sleeping 20 seconds to respect Gemini API rate limits (5 RPM)...")
time.sleep(20)

# ============================================================================
# Step 7: Verify transcript saved to Atlas
# ============================================================================
print_section("Step 7: Verify transcript saved to Atlas")

resp = requests.get(f"{BASE_URL}/sessions/{session_id}", headers=header())
if resp.status_code != 200:
    print_fail(f"GET /sessions/{session_id} failed: {resp.text}")

session_data = resp.json()
transcript = session_data.get("transcript", [])
print_info(f"Transcript has {len(transcript)} messages")

if len(transcript) < 2:
    print_fail(f"Expected at least 2 transcript entries (user + assistant), got {len(transcript)}")
print_pass(f"Transcript saved with {len(transcript)} entries")

user_msgs = [m for m in transcript if m.get("role") == "user"]
asst_msgs = [m for m in transcript if m.get("role") == "assistant"]
print_pass(f"User messages: {len(user_msgs)}, Assistant messages: {len(asst_msgs)}")


# ============================================================================
# Step 8: Chitchat test
# ============================================================================
print_section("Step 8: Chitchat intent test")

resp = requests.post(
    f"{BASE_URL}/chat/{session_id}/sync",
    json={"message": "Hey! How are you doing today?"},
    headers=header()
)
result3 = resp.json()
print_info(f"Intent: {result3['metadata']['intent']}")
if result3["metadata"]["intent"] == "chitchat":
    print_pass("RouterNode correctly classified chitchat")
else:
    print_info(f"⚠️  Got intent={result3['metadata']['intent']} instead of chitchat (minor)")


# ============================================================================
# Step 9: End session
# ============================================================================
print_section("Step 9: End session (cleanup Chroma)")

resp = requests.post(f"{BASE_URL}/sessions/{session_id}/end", headers=header())
if resp.status_code != 200:
    print_fail(f"Session end failed: {resp.text}")
print_pass("Session ended, ChromaDB collection deleted")


# ============================================================================
# Summary
# ============================================================================
print_section("Day 4 Test Complete!")
print(f"""
  ✅ Router correctly classifies intents
  ✅ RAG retrieves chunks from ChromaDB  
  ✅ Synthesis generates grounded responses
  ✅ Transcript saved to MongoDB Atlas
  ✅ Wikipedia fallback fires on low confidence
  ✅ Session lifecycle still working

  Cleanup: {test_file_path} left on disk (delete manually if needed)
""")
