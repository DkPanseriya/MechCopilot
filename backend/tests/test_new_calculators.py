import pytest
from backend.calculations import perform_calculation

def test_torsional_stress():
    inputs = {
        "torque": 500,
        "torque_unit": "N*m",
        "diameter": 50,
        "diameter_unit": "mm"
    }
    result = perform_calculation("torsional_stress", inputs)
    assert "error" not in result
    
    # Check value: Tau = 16 * 500 / (pi * 0.05^3) = 8000 / (pi * 0.000125) = 8000 / 0.0003927 = ~20,371,832 Pa = 20.37 MPa
    val = float(result["value"])
    unit = result["unit"]
    
    # 20.37 MPa
    assert val > 20 and val < 21
    assert "Pa" in unit or "MPa" in unit

def test_thermal_expansion():
    inputs = {
        "length": 1,
        "length_unit": "m",
        "delta_temperature": 50,
        "temperature_unit": "degC",
        "thermal_expansion_coefficient": 12e-6 # Steel approx
    }
    result = perform_calculation("thermal_expansion", inputs)
    assert "error" not in result
    
    # Delta L = 12e-6 * 1 * 50 = 600e-6 m = 0.6 mm
    val = float(result["value"])
    unit = result["unit"]
    
    assert val > 0.59 and val < 0.61
    assert unit == "mm"
