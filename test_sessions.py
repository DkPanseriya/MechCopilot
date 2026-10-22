import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

def test_session_flow():
    print("1. Creating Session...")
    try:
        res = requests.post(f"{BASE_URL}/sessions/", json={
            "title": "Test Material Selection",
            "context_type": "material_selection"
        })
        if res.status_code != 200:
            print(f"Failed to create session: {res.text}")
            return
        
        session = res.json()
        session_id = session["id"]
        print(f"Session Created: ID={session_id}, Title={session['title']}")
        
        print("\n2. Sending Chat Message...")
        chat_res = requests.post(f"{BASE_URL}/sessions/{session_id}/chat", json={
            "message": "What is the yield strength of Steel 1018?",
            "tier": "efficient"
        })
        
        if chat_res.status_code != 200:
            print(f"Chat failed: {chat_res.text}")
            return
            
        message = chat_res.json()
        print(f"AI Response: {message['content'][:100]}...")
        
        print("\n3. Verifying History...")
        hist_res = requests.get(f"{BASE_URL}/sessions/{session_id}")
        if hist_res.status_code != 200:
            print(f"Failed to get history: {hist_res.text}")
            return
            
        history = hist_res.json()
        msg_count = len(history["messages"])
        print(f"History contains {msg_count} messages.")
        
        if msg_count >= 2:
            print("SUCCESS: Session flow verified.")
        else:
            print("FAILURE: History incomplete.")
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to backend. Is it running?")

if __name__ == "__main__":
    test_session_flow()
