import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from physics_kernel import PhysicsRelation, RELATIONS

def test_expanded_kernel():
    print("--- Testing Expanded Physics Kernel ---")
    
    # 1. Bending Stress: sigma = My/I
    # Let M = 1000, y = 0.05, I = 0.0001
    # sigma = 1000 * 0.05 / 0.0001 = 50 / 0.0001 = 500,000
    print("\n[Bending Stress]")
    rel = RELATIONS["bending_stress"]
    val = rel.solve({"M": 1000, "y": 0.05, "I": 0.0001}, "sigma")
    print(f"sigma = {val} (Expected 500000.0)")
    assert abs(val - 500000.0) < 1.0
    
    # 2. Thermal Expansion: dL = alpha * L * dT
    # alpha = 1.2e-5, L = 10, dT = 50
    # dL = 1.2e-5 * 10 * 50 = 1.2e-4 * 50 = 60e-4 = 0.006
    print("\n[Thermal Expansion]")
    rel = RELATIONS["thermal_expansion"]
    val = rel.solve({"alpha": 0.000012, "L": 10, "dT": 50}, "dL")
    print(f"dL = {val} (Expected 0.006)")
    # Float precision might be slightly off
    assert abs(val - 0.006) < 1e-6
    
    # 3. Hoop Stress: sigma = Pd / 2t
    # P = 1e6 (1 MPa), d = 1, t = 0.01
    # sigma = 1e6 * 1 / 0.02 = 50e6 = 50 MPa
    print("\n[Hoop Stress]")
    rel = RELATIONS["hoop_stress"]
    val = rel.solve({"P": 1000000, "d": 1, "t": 0.01}, "sigma")
    print(f"sigma = {val} (Expected 50,000,000)")
    assert abs(val - 50000000.0) < 1.0
    
    print("\nExpanded Kernel Tests PASSED")

if __name__ == "__main__":
    try:
        test_expanded_kernel()
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)
