"""Tests for the unit-aware physics kernel (relation library)."""
import math
import pytest
from backend.physics_kernel import RELATIONS, get_manifest


def _solve(name, knowns, target, target_unit=None):
    return RELATIONS[name].solve(knowns, target, target_unit)


def test_axial_stress_forward_mpa():
    # F=100 N, d=10 mm -> A=7.854e-5 m^2 -> sigma ~1.273 MPa
    A = math.pi * (0.010 ** 2) / 4
    r = _solve("axial_stress",
               {"F": "100 N", "A": {"value": A, "unit": "m**2"}},
               "sigma", "MPa")
    assert r["unit"] in ("MPa", "megapascal")
    assert 1.27 < r["value"] < 1.28


def test_axial_stress_inverse_solves_area():
    # Given sigma and F, solve for A (checks solve-for-any-variable).
    r = _solve("axial_stress", {"sigma": "1.2732 MPa", "F": "100 N"}, "A", "mm**2")
    # A = F/sigma = 100 / 1.2732e6 = 7.854e-5 m^2 = 78.54 mm^2
    assert 78 < r["value"] < 79


def test_torsional_stress_solid():
    # T=500 N*m, d=50 mm -> tau ~20.37 MPa
    r = _solve("torsional_stress_solid", {"T": "500 N*m", "d": "50 mm"}, "tau", "MPa")
    assert 20.3 < r["value"] < 20.5


def test_bending_stress_units_propagate():
    # M=1000 N*m, y=25 mm, I from solid circle d=50 mm
    I = math.pi * (0.050 ** 4) / 64
    r = _solve("bending_stress",
               {"M": "1000 N*m", "y": "25 mm", "I": {"value": I, "unit": "m**4"}},
               "sigma", "MPa")
    assert r["value"] > 0
    assert r["unit"] in ("MPa", "megapascal")


def test_angle_of_twist_is_radian():
    r = _solve("angle_of_twist",
               {"T": "200 N*m", "L": "1 m", "G": "79 GPa",
                "J": {"value": math.pi * (0.040 ** 4) / 32, "unit": "m**4"}},
               "theta")
    assert r["si_unit"] == "radian"
    assert r["value"] > 0


def test_factor_of_safety_dimensionless():
    r = _solve("factor_of_safety", {"S": "250 MPa", "sigma": "125 MPa"}, "n")
    assert r["unit"] == ""
    assert abs(r["value"] - 2.0) < 1e-6


def test_von_mises():
    r = _solve("von_mises_2d",
               {"sx": "100 MPa", "sy": "0 MPa", "txy": "50 MPa"}, "sv", "MPa")
    # sqrt(100^2 + 3*50^2) = sqrt(10000+7500)=132.3 MPa
    assert 132 < r["value"] < 133


def test_shaft_equivalent_stress():
    r = _solve("shaft_equivalent_stress",
               {"sb": "80 MPa", "tt": "40 MPa"}, "se", "MPa")
    # sqrt(80^2 + 3*40^2) = sqrt(6400+4800)=105.8
    assert 105 < r["value"] < 107


def test_euler_buckling_newton():
    r = _solve("euler_buckling",
               {"E": "200 GPa", "I": {"value": math.pi * (0.020 ** 4) / 64, "unit": "m**4"},
                "Le": "1 m"}, "Pcr", "kN")
    assert r["value"] > 0
    assert r["unit"] in ("kN", "kilonewton")


def test_shear_modulus_steel():
    r = _solve("shear_modulus", {"E": "200 GPa", "nu": 0.3}, "G", "GPa")
    # G = 200 / (2*1.3) = 76.9 GPa
    assert 76 < r["value"] < 78


def test_manifest_shape():
    m = get_manifest()
    assert len(m) >= 30
    sample = m[0]
    for key in ("name", "category", "description", "variables", "units", "equation"):
        assert key in sample
