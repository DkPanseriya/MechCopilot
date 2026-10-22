import sys
import os
import requests

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from physics_kernel import PhysicsRelation, RELATIONS

def test_units_kernel():
    print("--- Testing Unit Awareness in Kernel ---")
    
    rel = RELATIONS["axial_stress"] # sigma = F/A
    
    # Case 1: Mixed Units
    # F = 1 kN, A = 1000 mm^2
    # 1 kN = 1000 N
    # 1000 mm^2 = 1000 * 1e-6 m^2 = 1e-3 m^2
    # Sigma = 1000 / 0.001 = 1,000,000 Pa (1 MPa)
    
    inputs = {
        "F": {"value": 1, "unit": "kN"}, 
        "A": {"value": 1000, "unit": "mm**2"}
    }
    
    print("\n[Input]", inputs)
    val = rel.solve(inputs, "sigma")
    print(f"Result (Pa): {val}")
    
    assert abs(val - 1000000.0) < 1.0
    print("Test 1 PASSED")
    
    # Case 2: String parsing (Pint)
    # F = "1000 N", A = "0.001 m^2"
    inputs_str = {
        "F": "1000 N",
        "A": "0.001 m**2"
    }
    print("\n[Input String]", inputs_str)
    val2 = rel.solve(inputs_str, "sigma")
    print(f"Result (Pa): {val2}")
    
    assert abs(val2 - 1000000.0) < 1.0
    print("Test 2 PASSED")

if __name__ == "__main__":
    try:
        test_units_kernel()
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)
