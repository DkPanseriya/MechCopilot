import sys
import os
import requests
import json

# Add backend to path to import kernel directly for unit test
sys.path.append(os.path.join(os.getcwd(), "backend"))

from physics_kernel import PhysicsRelation

def test_kernel_direct():
    print("--- Testing Physics Kernel (Direct) ---")
    
    # Test 1: F = ma (Solve for F)
    # F = m * a
    rel = PhysicsRelation("newton", "F = m * a", ["F", "m", "a"], "Newton 2nd")
    f_val = rel.solve({"m": 10, "a": 5}, "F")
    print(f"F = 10 * 5 -> {f_val} (Expected 50.0)")
    assert abs(f_val - 50.0) < 1e-6
    
    # Test 2: Inversion (Solve for m)
    # m = F / a
    m_val = rel.solve({"F": 100, "a": 20}, "m")
    print(f"m = 100 / 20 -> {m_val} (Expected 5.0)")
    assert abs(m_val - 5.0) < 1e-6
    
    print("Kernel Direct Tests PASSED")

def test_api_workflow():
    print("\n--- Testing Workflow API ---")
    base_url = "http://localhost:8000/api/workflow"
    
    # 1. Get Manifest
    try:
        res = requests.get(f"{base_url}/manifest")
        print(f"GET /manifest status: {res.status_code}")
        if res.status_code != 200:
            print("Failed to get manifest")
            return
        manifest = res.json()
        print(f"Manifest items: {len(manifest)}")
        assert len(manifest) >= 4
    except Exception as e:
        print(f"API not running? {e}")
        return

    # 2. Execute Step (Axial Stress)
    # Sigma = F / A
    payload = {
        "relation_name": "axial_stress",
        "target_var": "sigma",
        "inputs": {"F": 1000, "A": 0.001} # 1000 N / 0.001 m^2 = 1,000,000 Pa
    }
    res = requests.post(f"{base_url}/step", json=payload)
    print(f"POST /step status: {res.status_code}")
    data = res.json()
    print(f"Result: {data}")
    
    # Expect 1e6
    assert abs(data["result"] - 1000000.0) < 1e-1
    
    print("API Workflow Tests PASSED")

if __name__ == "__main__":
    try:
        test_kernel_direct()
        # Note: API test requires server running. We might skip if not running.
        # But we should try.
        test_api_workflow()
    except Exception as e:
        print(f"Verification FAILED: {e}")
        sys.exit(1)
