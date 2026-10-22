from backend.calculations import perform_calculation

def test_calc():
    print("Testing Physics Engine...")
    
    # 1. Stress: 1000 N on 10 mm diameter
    # Area = pi * 5^2 = 78.54 mm^2
    # Stress = 1000 / 78.54 = 12.73 MPa
    inputs_1 = {
        "force": 1000, "force_unit": "N",
        "diameter": 10, "diameter_unit": "mm"
    }
    res_1 = perform_calculation("axial_stress", inputs_1)
    print(f"Test 1 (Stress): {res_1}")
    assert "12.73" in res_1["value"]
    assert res_1["unit"] == "MPa"
    
    # 2. Deflection: 5 kN on 2m beam, dia=0.05m, Steel
    # F = 5000 N
    # L = 2 m
    # E = 200 GPa = 200e9 Pa
    # I = pi * 0.05^4 / 64 = 3.068e-7 m^4
    # Deflection = (5000 * 8) / (3 * 200e9 * 3.068e-7) 
    # = 40000 / 184080 = 0.217 m = 217 mm
    inputs_2 = {
        "force": 5, "force_unit": "kN",
        "length": 2, "length_unit": "m",
        "diameter": 5, "diameter_unit": "cm",
        "elasticity": 200, "elasticity_unit": "GPa"
    }
    res_2 = perform_calculation("beam_deflection", inputs_2)
    print(f"Test 2 (Deflection): {res_2}")
    # approx 217 mm
    assert res_2["unit"] == "mm"
    
    print("SUCCESS: Engine verified.")

if __name__ == "__main__":
    test_calc()
