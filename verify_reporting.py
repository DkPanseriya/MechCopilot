import requests
import json
import sys

BASE_URL = "http://localhost:8001/api"

def test_reporting():
    print("--- Testing Automated Reporting ---")
    
    # 1. Create Session
    res = requests.post(f"{BASE_URL}/sessions/", json={"title": "Report Test", "context_type": "general"})
    session_id = res.json()["id"]
    print(f"Created Session: {session_id}")
    
    # 2. Add Message (Simulate Chat)
    requests.post(f"{BASE_URL}/sessions/{session_id}/chat", json={
        "message": "Calculate stress",
        "tier": "efficient"
    }, stream=True)
    # Note: We aren't waiting for the stream fully here, but the DB should populate the user msg immediately 
    # and eventually the assistant msg. For this test, we just check if report generates *something*.
    
    # 3. Generate Report
    res_rep = requests.get(f"{BASE_URL}/reports/{session_id}")
    if res_rep.status_code != 200:
        print(f"Report Failed: {res_rep.text}")
        sys.exit(1)
        
    data = res_rep.json()
    md = data["markdown"]
    
    print("\n[Report Preview]")
    print(md[:300] + "...")
    
    if "# Engineering Design Report" in md and "Report Test" in md:
        print("\nReport Content Verified: PASSED")
    else:
        print("\nReport Content Missing Header: FAILED")
        sys.exit(1)

if __name__ == "__main__":
    try:
        test_reporting()
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)
