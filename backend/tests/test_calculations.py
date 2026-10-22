from fastapi.testclient import TestClient
from backend.main import app
from backend.calculations import calc_axial_stress

# client = TestClient(app)

def test_axial_stress_simple():
    """
    Test basic stress calculation:
    Force = 100 N
    Diameter = 10 mm -> Radius = 5mm = 0.005m
    Area = pi * (0.005)^2 = 7.854e-5 m^2
    Stress = 100 / 7.854e-5 = 1.273e6 Pa = 1.273 MPa
    """
    inputs = {
        "force": 100,
        "force_unit": "N",
        "diameter": 10,
        "diameter_unit": "mm"
    }
    result = calc_axial_stress(inputs)
    
    # We expect ~1.27 MPa
    assert result["unit"] == "MPa"
    # Check value roughly
    val = float(result["value"])
    assert 1.27 < val < 1.28
