import requests
import time
import json
import os

BASE_URL = "http://localhost:8000"

def print_step(title):
    print(f"\n{'='*50}\n▶ {title}\n{'='*50}")

def run_tests():
    session = requests.Session()
    
    # Generate unique test user
    timestamp = int(time.time())
    email = f"test_{timestamp}@example.com"
    password = "password123"
    
    print_step(f"1. Registering user: {email}")
    res = session.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "name": "Day 5 Tester"
    })
    
    if res.status_code != 201:
        print("Registration failed! Is the server running?")
        print(res.text)
        return
        
    token = res.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ User registered and got token.")

    print_step("2. Creating Subject, Document & Session")
    # Create Subject
    res = session.post(f"{BASE_URL}/subjects/", headers=headers, json={
        "name": "Test Subject OS",
        "exam_date": "2026-10-15T10:00:00Z"
    })
    subject_id = res.json().get("id")
    print(f"✅ Created Subject ID: {subject_id}")
    
    # Upload Dummy Document
    files = {'file': ('dummy.txt', b'Operating Systems use virtual memory to manage RAM.', 'text/plain')}
    res = session.post(f"{BASE_URL}/documents/upload", headers=headers, data={"subject_id": subject_id}, files=files)
    doc_id = res.json().get("id")
    print(f"✅ Uploaded Dummy Document ID: {doc_id}")
    
    # Create Session
    res = session.post(f"{BASE_URL}/sessions/start", headers=headers, json={
        "subject_id": subject_id,
        "document_ids": [doc_id]
    })
    
    if res.status_code != 201:
        print("❌ Failed to start session!")
        print(res.text)
        return
        
    session_id = res.json().get("session_id")
    print(f"✅ Started Session ID: {session_id}")

    print_step("3. Google Calendar OAuth (MANUAL STEP)")
    # Get the Google OAuth URL
    res = session.get(f"{BASE_URL}/auth/google", headers=headers, allow_redirects=False)
    
    if res.status_code in [301, 302, 303, 307, 308]:
        auth_url = res.headers.get("Location")
        print("\n⚠️  ACTION REQUIRED: ⚠️")
        print("To test Calendar creation, you must authorize this test user.")
        print("1. Open this URL in your browser:")
        print(f"\n{auth_url}\n")
        print("2. Log in with Google and click 'Allow'.")
        print("3. You will be redirected to localhost:3000 (even if it says connection refused, it's fine).")
        input("\nPress ENTER here once you have finished the Google login...")
    else:
        print("Failed to get Google OAuth URL.")
        print(res.text)
        return

    print_step("4. Test Study Planner (Generates proposed events)")
    res = session.post(f"{BASE_URL}/chat/{session_id}/sync", headers=headers, json={
        "message": "plan my OS revision, my exam is next month"
    })
    
    plan_data = res.json()
    print("Agent Response:\n", plan_data.get("response"))
    print("\nAwaiting Confirmation?", plan_data.get("metadata", {}).get("awaiting_confirmation"))
    
    if "proposed_events" in plan_data:
        print(f"Proposed Events: {len(plan_data['proposed_events'])}")
    else:
        print("❌ No proposed events found. Skipping Calendar confirmation test.")
        
    print_step("5. Test Confirming Plan (Creates Calendar Events)")
    # The confirm-plan route streams SSE events, but requests will just buffer it all
    # and print it out once it's done.
    if "proposed_events" in plan_data:
        print("Confirming plan (this might take a few seconds)...")
        res = session.post(f"{BASE_URL}/chat/{session_id}/confirm-plan", headers=headers, json={
            "action": "confirm"
        })
        
        # Parse the SSE output simply
        events = res.text.split("\n\n")
        for event in events:
            if "event: response" in event:
                data_line = event.split("data: ")[1]
                data = json.loads(data_line)
                print("\n✅ Events Created:", data.get("events_created"))
                print("Calendar Links:")
                for link in data.get("calendar_events", []):
                    print(" -", link.get("html_link"))
                break

    print_step("6. Test Flashcard Generation")
    res = session.post(f"{BASE_URL}/chat/{session_id}/sync", headers=headers, json={
        "message": "make me 3 flashcards on virtual memory"
    })
    if res.status_code != 200:
        print(f"❌ Server returned error {res.status_code}: {res.text}")
    else:
        data = res.json()
        print(f"Agent Response:\n{data.get('response')}")
    
    print_step("7. Test Revision Sheet Generation")
    print("Generating revision sheet (this will take ~45s due to rate limits)...")
    res = session.post(f"{BASE_URL}/chat/{session_id}/sync", headers=headers, json={
        "message": "generate an exam revision sheet for this subject"
    }, timeout=120)  # Revision sheet is slow — up to 2 mins
    if res.status_code != 200:
        print(f"❌ Server returned error {res.status_code}: {res.text[:300]}")
    else:
        data = res.json()
        print("\n✅ Revision Sheet generated. Preview:")
        print(str(data.get("response"))[:300] + "...\n")
    
    print_step("8. Test Hugging Face Translation")
    res = session.post(f"{BASE_URL}/chat/{session_id}/sync", headers=headers, json={
        "message": "translate this to French: The study agent is working perfectly!"
    })
    if res.status_code != 200:
        print(f"❌ Server returned error {res.status_code}: {res.text[:300]}")
    else:
        data = res.json()
        print("Agent Response:\n", data.get("response"))
    
    print_step("✅ ALL TESTS COMPLETE")

if __name__ == "__main__":
    run_tests()
