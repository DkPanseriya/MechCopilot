import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from backend.calculations import perform_calculation

def test_torsional_stress():
    print("Testing Torsional Stress...")
    inputs = {
        "torque": 500,
        "torque_unit": "N*m",
        "diameter": 50,
        "diameter_unit": "mm"
    }
    result = perform_calculation("torsional_stress", inputs)
    
    if "error" in result:
        print(f"FAILED: {result['error']}")
        return False
        
    val = float(result["value"])
    unit = result["unit"]
    
    print(f"Result: {val} {unit}")
    
    if val > 20 and val < 21 and ("Pa" in unit or "MPa" in unit):
        print("PASSED")
        return True
    else:
        print("FAILED: Value out of range")
        return False

def test_thermal_expansion():
    print("\nTesting Thermal Expansion...")
    inputs = {
        "length": 1,
        "length_unit": "m",
        "delta_temperature": 50,
        "temperature_unit": "degC",
        "thermal_expansion_coefficient": 12e-6
    }
    result = perform_calculation("thermal_expansion", inputs)
    
    if "error" in result:
        print(f"FAILED: {result['error']}")
        return False
    
    val = float(result["value"])
    unit = result["unit"]
    
    print(f"Result: {val} {unit}")
    
    if val > 0.59 and val < 0.61 and unit == "mm":
        print("PASSED")
        return True
    else:
        print("FAILED: Value out of range")
        return False

if __name__ == "__main__":
    if test_torsional_stress() and test_thermal_expansion():
        print("\nAll Tests Passed")
        sys.exit(0)
    else:
        print("\nSome Tests Failed")
        sys.exit(1)
