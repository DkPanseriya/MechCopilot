import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from physics_kernel import PhysicsRelation, RELATIONS

def test_v2_expansion():
    print("--- Testing Fluid & Thermal Relations ---")
    
    # 1. Reynolds Number
    # Water: rho=1000, v=1, d=0.1, mu=0.001 (Pa.s)
    # Re = 1000 * 1 * 0.1 / 0.001 = 100 / 0.001 = 100,000
    print("\n[Reynolds Number]")
    rel = RELATIONS["reynolds_number"]
    val = rel.solve({"rho": 1000, "v": 1, "d": 0.1, "mu": 0.001}, "Re")
    print(f"Re = {val} (Expected 100000.0)")
    assert abs(val - 100000.0) < 1.0
    
    # 2. Heat Conduction
    # q = k*A*(Tin - Tout)/L
    # k=200, A=1, Tin=100, Tout=50, L=0.5
    # q = 200*1*50 / 0.5 = 10000 / 0.5 = 20000 Watts
    print("\n[Heat Conduction]")
    rel = RELATIONS["heat_conduction"]
    val = rel.solve({"k": 200, "A": 1, "Tin": 100, "Tout": 50, "L": 0.5}, "q")
    print(f"q = {val} (Expected 20000.0)")
    assert abs(val - 20000.0) < 1.0

    print("\nV2 Expansion Tests PASSED")

if __name__ == "__main__":
    try:
        test_v2_expansion()
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)
