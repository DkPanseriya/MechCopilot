import requests

BASE_URL = "http://localhost:8000/api"

def test_endpoints():
    print("Testing Session Endpoints...")
    
    # 1. Create
    print("1. Creating Session...")
    res = requests.post(f"{BASE_URL}/sessions/", json={"title": "Temp", "context_type": "general"})
    if res.status_code != 200:
        print(f"Create API failed: {res.text}")
        return
    session_id = res.json()["id"]
    print(f"Created Session {session_id}")

    # 2. Rename
    print("2. Renaming Session...")
    res = requests.put(f"{BASE_URL}/sessions/{session_id}", json={"title": "Renamed Session"})
    if res.status_code != 200:
        print(f"Rename API failed: {res.text}")
        return
    new_title = res.json()["title"]
    assert new_title == "Renamed Session"
    print("Rename Verified.")

    # 3. Delete
    print("3. Deleting Session...")
    res = requests.delete(f"{BASE_URL}/sessions/{session_id}")
    if res.status_code != 200:
        print(f"Delete API failed: {res.text}")
        return
    
    # Verify it's gone
    res = requests.get(f"{BASE_URL}/sessions/{session_id}")
    assert res.status_code == 404
    print("Delete Verified.")
    
    print("SUCCESS: All endpoints verified.")

if __name__ == "__main__":
    test_endpoints()
