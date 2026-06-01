"""
Focused test for Steps 7 & 8:
  - Revision Sheet Generation
  - Hugging Face Translation

Registers a fresh user, creates a minimal session with a dummy document,
then immediately tests only the two remaining features.
"""

import requests
import time

BASE_URL = "http://localhost:8000"

def print_step(title):
    print(f"\n{'='*50}\n▶ {title}\n{'='*50}")


def setup(session):
    """Register user, create subject + document + session. Returns (headers, session_id)."""
    timestamp = int(time.time())
    email = f"test_{timestamp}@example.com"

    print_step(f"Setup: Registering user {email}")
    res = session.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": "password123",
        "name": "Revision Tester"
    })
    if res.status_code != 201:
        print(f"❌ Registration failed: {res.text}")
        return None, None

    token = res.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Registered.")

    # Subject
    res = session.post(f"{BASE_URL}/subjects/", headers=headers, json={
        "name": "Operating Systems",
        "exam_date": "2026-10-15T10:00:00Z"
    })
    subject_id = res.json().get("id")
    print(f"✅ Subject: {subject_id}")

    # Upload dummy document
    content = b"""
    Virtual memory allows programs to use more RAM than physically available.
    Paging divides memory into fixed-size blocks called pages.
    Page faults occur when a page is not currently in physical memory.
    The OS uses a page table to map virtual addresses to physical addresses.
    Demand paging loads pages into memory only when they are needed.
    Thrashing occurs when excessive paging degrades system performance.
    """
    files = {"file": ("os_notes.txt", content, "text/plain")}
    res = session.post(f"{BASE_URL}/documents/upload", headers=headers,
                       data={"subject_id": subject_id}, files=files)
    doc_id = res.json().get("id")
    print(f"✅ Document uploaded: {doc_id}")

    # Session
    res = session.post(f"{BASE_URL}/sessions/start", headers=headers, json={
        "subject_id": subject_id,
        "document_ids": [doc_id]
    })
    if res.status_code != 201:
        print(f"❌ Session start failed: {res.text}")
        return None, None

    session_id = res.json().get("session_id")
    print(f"✅ Session started: {session_id}")
    return headers, session_id


def test_revision_sheet(session, headers, session_id):
    print_step("7. Revision Sheet Generation")
    print("⏳ This takes ~45s due to API rate limiting (intentional sleep between LLM calls)...")
    res = session.post(f"{BASE_URL}/chat/{session_id}/sync", headers=headers, json={
        "message": "generate an exam revision sheet for this subject"
    }, timeout=180)

    if res.status_code != 200:
        print(f"❌ Error {res.status_code}: {res.text[:500]}")
        return False

    data = res.json()
    response_text = str(data.get("response", ""))
    if response_text:
        print(f"\n✅ Revision Sheet generated! Preview:\n{response_text[:400]}...\n")
        return True
    else:
        print("❌ Empty response received.")
        return False


def test_translation(session, headers, session_id):
    print_step("8. Hugging Face Translation (NLLB-200)")
    res = session.post(f"{BASE_URL}/chat/{session_id}/sync", headers=headers, json={
        "message": "translate this to French: The study agent is working perfectly!"
    }, timeout=60)

    if res.status_code != 200:
        print(f"❌ Error {res.status_code}: {res.text[:500]}")
        return False

    data = res.json()
    response_text = data.get("response", "")
    if response_text:
        print(f"\n✅ Translation Response:\n{response_text}\n")
        return True
    else:
        print("❌ Empty response received.")
        return False


if __name__ == "__main__":
    http_session = requests.Session()

    headers, session_id = setup(http_session)
    if not headers:
        print("\n❌ Setup failed. Exiting.")
        exit(1)

    results = {}
    results["revision_sheet"] = test_revision_sheet(http_session, headers, session_id)
    results["translation"]    = test_translation(http_session, headers, session_id)

    print_step("TEST SUMMARY")
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  —  {test}")
