import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from physics_kernel import PhysicsRelation, RELATIONS
from routers.materials import get_materials, get_material

def test_materials_backend():
    print("--- Testing Material Library ---")
    
    # 1. Load Materials
    all_mats = get_materials()
    print(f"Loaded {len(all_mats)} materials.")
    assert len(all_mats) > 0
    
    # 2. Check specific material
    m = get_material("steel_1018_cd")
    print(f"Steel 1018 Yield: {m['yield_strength']} Pa")
    assert m['yield_strength'] == 370000000.0
    
    # 3. Factor of Safety
    print("\n[Factor of Safety]")
    rel = RELATIONS["factor_of_safety"]
    # Sy = 370 MPa, Stress = 200 MPa
    # n = 370 / 200 = 1.85
    val = rel.solve({"limit": 370, "load": 200}, "n")
    print(f"n = {val} (Expected 1.85)")
    assert abs(val - 1.85) < 1e-6
    
    print("\nMaterial Backend Tests PASSED")

if __name__ == "__main__":
    try:
        test_materials_backend()
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)
