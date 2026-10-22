import sys
import os

sys.path.append(os.path.join(os.getcwd(), "backend"))
from physics_kernel import RELATIONS

def test_safety_check():
    print("--- Simulating Safety Check Workflow ---")
    
    # User: "Check 10mm Steel 1018 rod under 20kN"
    # Steel 1018 Yield = 370 MPa (from Trusted DB)
    
    # Step 1: Axial Stress
    # sigma = F / A
    print("\n[Step 1: Stress]")
    rel_area = RELATIONS["circle_area"]
    area = rel_area.solve({"d": "10 mm"}, "A")
    print(f"Area = {area} m^2")
    
    rel_stress = RELATIONS["axial_stress"]
    stress = rel_stress.solve({"F": "20 kN", "A": area}, "sigma")
    print(f"Stress = {stress/1e6} MPa")
    
    # Step 2: Factor of Safety
    # n = Limit / Load
    print("\n[Step 2: Safety]")
    rel_fos = RELATIONS["factor_of_safety"]
    limit = 370000000 # 370 MPa
    n = rel_fos.solve({"limit": limit, "load": stress}, "n")
    
    print(f"FoS = {n:.2f}")
    assert n > 1.0 # Should be safe
    assert abs(n - 1.45) < 0.1 # Approx (370 / 254)
    
    print("\nSafety Workflow PASSED")

if __name__ == "__main__":
    try:
        test_safety_check()
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)
