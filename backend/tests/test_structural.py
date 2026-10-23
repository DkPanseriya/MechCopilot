"""Structural calculators: springs, welds, columns, pressure vessels, fatigue, Kt."""
import json
import math

import pytest

from engineering.core import CalcError, run_calculator
from engineering.registry import CATALOG
from engineering.structural.fatigue import (SURFACE, fatigue_fraction, kt_plate_hole, kt_round,
                                            mean_stress_factors, size_factor)
from engineering.structural.springs import wire_props

IDS = ["compression_spring", "torsion_spring", "fillet_weld", "column_buckling",
       "pressure_vessel", "fatigue_life", "stress_concentration"]


def out(res, name):
    return next(o for o in res["outputs"] if o["name"] == name)


def mm(v):
    return {"value": v, "unit": "mm"}


def custom(Sy=355, Sut=510, E=210):
    return {"material": "custom", "material_Sy": {"value": Sy, "unit": "MPa"},
            "material_Sut": {"value": Sut, "unit": "MPa"}, "material_E": {"value": E, "unit": "GPa"}}


@pytest.mark.parametrize("cid", IDS)
def test_registered_and_json_safe(cid):
    calc = CATALOG[cid]
    for vals in [{}] + [p["values"] for p in calc.presets]:
        json.dumps(run_calculator(calc, vals), allow_nan=False)


@pytest.mark.parametrize("cid", IDS)
def test_defaults_pass(cid):
    assert run_calculator(CATALOG[cid], {})["verdict"] in ("ok", "warn")


# --- springs --------------------------------------------------------------

def test_music_wire_strength_shigley_ex_10_1():
    # Shigley Ex. 10-1: No. 16 music wire d = 0.037 in -> Sut = 324 kpsi = 2235 MPa
    assert wire_props("a228", 0.037 * 0.0254)["Sut"] / 1e6 == pytest.approx(2235, rel=0.01)


def test_compression_spring_shigley_ex_10_1():
    # d = 0.037 in, OD = 7/16 in, squared ends, 12.5 total turns (Na = 10.5)
    res = run_calculator(CATALOG["compression_spring"], {
        "d": mm(0.9398), "D_basis": "outer", "D": mm(11.1125), "Na": 10.5, "ends": "squared",
        "L0": mm(52.3), "wire": "a228", "F": {"value": 20, "unit": "N"}})
    assert out(res, "k")["value"] == pytest.approx(4.13 * 4.44822 / 25.4, rel=0.01)  # 4.13 lbf/in
    assert out(res, "F_yield")["value"] == pytest.approx(6.46 * 4.44822, rel=0.02)    # 6.46 lbf
    assert out(res, "Ls")["value"] == pytest.approx(0.500 * 25.4, rel=0.01)           # 0.500 in


def test_compression_spring_rate_formula():
    res = run_calculator(CATALOG["compression_spring"], {
        "d": mm(3), "D": mm(24), "Na": 10, "wire": "a229", "L0": mm(80)})
    k = (0.003 ** 4 * 77.2e9) / (8 * 0.024 ** 3 * 10)  # N/m
    assert out(res, "k")["value"] == pytest.approx(k / 1000, rel=1e-6)


def test_compression_spring_cyclic_fatigue_reported():
    res = run_calculator(CATALOG["compression_spring"], {
        "cyclic": True, "F": {"value": 100, "unit": "N"}, "Fmin": {"value": 40, "unit": "N"}})
    assert "nf" in [o["name"] for o in res["outputs"]]
    assert any(c["label"].startswith("Fatigue") for c in res["checks"])


def test_compression_spring_errors():
    with pytest.raises(CalcError):
        run_calculator(CATALOG["compression_spring"], {"d": mm(5), "D": mm(4)})
    with pytest.raises(CalcError):  # free length below solid length
        run_calculator(CATALOG["compression_spring"], {"L0": mm(10)})


def test_torsion_spring_stress_formula():
    res = run_calculator(CATALOG["torsion_spring"], {
        "d": mm(2), "D": mm(20), "M": {"value": 500, "unit": "N*mm"}})
    C = 10
    Ki = (4 * C ** 2 - C - 1) / (4 * C * (C - 1))
    sigma = Ki * 32 * 0.5 / (math.pi * 0.002 ** 3)
    assert out(res, "sigma")["value"] == pytest.approx(sigma / 1e6, rel=1e-6)


# --- welds ----------------------------------------------------------------

def test_fillet_weld_shigley_ex_9_1():
    # 3/8 in fillet, 2 in long on both sides, 16.5 kip -> tau = 15.6 kpsi, n = 21/15.6 = 1.35
    res = run_calculator(CATALOG["fillet_weld"], {
        "pattern": "two_vertical", "b": mm(12.7), "d": mm(50.8), "h": mm(9.525),
        "case": "in_plane", "V": {"value": 16.5 * 4.44822, "unit": "kN"}, "e": mm(0), "code": "aws_e70"})
    assert out(res, "tau")["value"] == pytest.approx(15.56 * 6.894757, rel=0.01)
    assert out(res, "n")["value"] == pytest.approx(1.35, abs=0.01)


def test_fillet_weld_box_bending_closed_form():
    res = run_calculator(CATALOG["fillet_weld"], {
        "pattern": "box", "b": mm(100), "d": mm(100), "h": mm(10), "case": "out_of_plane",
        "V": {"value": 10, "unit": "kN"}, "e": mm(100)})
    A = 0.707 * 10 * 400
    I = 0.707 * 10 * (100 ** 2 / 6 * 400)
    tau = math.hypot(10000 / A, 1e6 * 50 / I)
    assert out(res, "tau")["value"] == pytest.approx(tau, rel=1e-4)


def test_fillet_weld_two_lines_torsion_closed_form():
    res = run_calculator(CATALOG["fillet_weld"], {
        "pattern": "two_vertical", "b": mm(50), "d": mm(100), "h": mm(10), "case": "in_plane",
        "V": {"value": 10, "unit": "kN"}, "e": mm(100)})
    A = 0.707 * 10 * 200
    J = 0.707 * 10 * 100 * (3 * 50 ** 2 + 100 ** 2) / 6
    tx, ty = 1e6 * 50 / J, 10000 / A + 1e6 * 25 / J
    assert out(res, "tau")["value"] == pytest.approx(math.hypot(tx, ty), rel=1e-4)


def test_fillet_weld_required_leg_meets_allowable():
    calc = CATALOG["fillet_weld"]
    res = run_calculator(calc, {"V": {"value": 40, "unit": "kN"}})
    h_req = out(res, "h_req")["value"]
    again = run_calculator(calc, {"V": {"value": 40, "unit": "kN"}, "h": mm(h_req)})
    assert out(again, "util")["value"] == pytest.approx(1.0, rel=1e-3)


def test_fillet_weld_error():
    with pytest.raises(CalcError):
        run_calculator(CATALOG["fillet_weld"], {"d": mm(0)})


# --- columns --------------------------------------------------------------

def test_column_euler():
    res = run_calculator(CATALOG["column_buckling"], {
        "section": "round", "d": mm(25), "L": mm(1000), "ends": "pinned_pinned",
        "P": {"value": 10, "unit": "kN"}, **custom()})
    I = math.pi * 25 ** 4 / 64
    Pcr = math.pi ** 2 * 210e3 * I / 1000 ** 2 / 1000  # kN
    assert out(res, "Pcr")["value"] == pytest.approx(Pcr, rel=1e-4)
    assert out(res, "regime")["display"].startswith("Euler")


def test_column_johnson():
    res = run_calculator(CATALOG["column_buckling"], {
        "section": "round", "d": mm(25), "L": mm(500), "ends": "pinned_pinned",
        "P": {"value": 10, "unit": "kN"}, **custom()})
    lam = 500 / (25 / 4)
    scr = 355 - (355 * lam / (2 * math.pi)) ** 2 / 210e3
    assert out(res, "scr")["value"] == pytest.approx(scr, rel=1e-4)
    assert out(res, "regime")["display"].startswith("Johnson")


def test_column_fixed_free_is_quarter_of_pinned():
    base = {"section": "round", "d": mm(20), "L": mm(2000), "P": {"value": 1, "unit": "kN"}, **custom()}
    p1 = out(run_calculator(CATALOG["column_buckling"], {**base, "ends": "pinned_pinned"}), "Pcr")["value"]
    p2 = out(run_calculator(CATALOG["column_buckling"], {**base, "ends": "fixed_free"}), "Pcr")["value"]
    assert p2 == pytest.approx(p1 / 4, rel=1e-6)


def test_column_bad_tube():
    with pytest.raises(CalcError):
        run_calculator(CATALOG["column_buckling"], {"section": "tube", "D": mm(20), "t": mm(10)})


# --- pressure vessels -----------------------------------------------------

def test_lame_thick_cylinder():
    res = run_calculator(CATALOG["pressure_vessel"], {
        "shape": "cylinder", "Di": mm(100), "t": mm(50), "p_i": {"value": 100, "unit": "MPa"},
        "p_o": {"value": 0, "unit": "MPa"}, "closed": True})
    assert out(res, "st_i")["value"] == pytest.approx(100 * (2500 + 10000) / 7500, rel=1e-6)
    assert out(res, "sr_i")["value"] == pytest.approx(-100, rel=1e-6)
    assert out(res, "sl_i")["value"] == pytest.approx(100 * 2500 / 7500, rel=1e-6)


def test_lame_thick_sphere():
    res = run_calculator(CATALOG["pressure_vessel"], {
        "shape": "sphere", "Di": mm(100), "t": mm(50), "p_i": {"value": 100, "unit": "MPa"}})
    ri, ro = 50.0, 100.0
    assert out(res, "st_i")["value"] == pytest.approx(100 * (ri ** 3 + ro ** 3 / 2) / (ro ** 3 - ri ** 3), rel=1e-6)


def test_thin_wall_hoop():
    res = run_calculator(CATALOG["pressure_vessel"], {
        "Di": mm(1000), "t": mm(5), "p_i": {"value": 1, "unit": "MPa"}})
    assert out(res, "st_thin")["value"] == pytest.approx(100, rel=1e-6)
    assert out(res, "st_i")["value"] == pytest.approx(100, rel=0.01)  # Lamé ≈ thin for t/r = 0.01


def test_vessel_required_thickness_meets_target():
    calc = CATALOG["pressure_vessel"]
    res = run_calculator(calc, {"n_target": 2.5})
    t_req = out(res, "t_req")["value"]
    again = run_calculator(calc, {"t": mm(t_req), "n_target": 2.5})
    assert out(again, "n")["value"] == pytest.approx(2.5, rel=1e-3)


def test_vessel_external_pressure_buckling_check():
    res = run_calculator(CATALOG["pressure_vessel"], {
        "Di": mm(500), "t": mm(3), "p_i": {"value": 0, "unit": "bar"}, "p_o": {"value": 5, "unit": "bar"}})
    assert any("buckling" in c["label"].lower() for c in res["checks"])


def test_vessel_no_pressure_error():
    with pytest.raises(CalcError):
        run_calculator(CATALOG["pressure_vessel"], {"p_i": {"value": 0, "unit": "bar"}})


# --- fatigue --------------------------------------------------------------

def test_marin_surface_shigley_ex_6_3():
    _, a, b = SURFACE["machined"]
    assert a * 520 ** b == pytest.approx(0.860, abs=0.002)


def test_marin_size_shigley_ex_6_4():
    assert size_factor(32)[0] == pytest.approx(0.856, abs=0.003)


def test_fatigue_fraction_shigley_ex_6_2():
    # 1050 HR, Sut = 90 kpsi -> f ≈ 0.86
    assert fatigue_fraction(90 * 6.894757) == pytest.approx(0.864, abs=0.005)


def test_mean_stress_criteria():
    n = mean_stress_factors(100, 100, 200, 600, 500)
    assert n["goodman"] == pytest.approx(1.5, rel=1e-6)
    assert n["soderberg"] == pytest.approx(1 / 0.7, rel=1e-6)
    assert n["asme"] == pytest.approx(1 / math.sqrt(0.29), rel=1e-6)
    assert n["gerber"] == pytest.approx(9 * (-1 + math.sqrt(1 + (2 / 3) ** 2)), rel=1e-6)
    assert n["langer"] == pytest.approx(2.5, rel=1e-6)


def test_fatigue_finite_life_consistent():
    res = run_calculator(CATALOG["fatigue_life"], CATALOG["fatigue_life"].presets[1]["values"])
    Se = out(res, "Se")["value"]
    f = out(res, "f")["value"]
    s_rev = out(res, "s_rev")["value"]
    Sut = 625.0
    a = (f * Sut) ** 2 / Se
    b = -math.log10(f * Sut / Se) / 3
    assert out(res, "N")["value"] == pytest.approx((s_rev / a) ** (1 / b), rel=1e-3)


def test_fatigue_infinite_life_display():
    res = run_calculator(CATALOG["fatigue_life"], {})
    assert out(res, "N")["display"] == "∞"


def test_fatigue_bad_kf():
    with pytest.raises(CalcError):
        run_calculator(CATALOG["fatigue_life"], {"Kf": 0.5})


# --- stress concentration -------------------------------------------------

def test_kt_shoulder_shigley_ex_6_6():
    # 38/32 mm, r = 3 mm, bending: chart Kt ≈ 1.65, Kf ≈ 1.55 for Sut = 690 MPa
    res = run_calculator(CATALOG["stress_concentration"], CATALOG["stress_concentration"].presets[0]["values"])
    assert out(res, "kt")["value"] == pytest.approx(1.65, abs=0.06)
    assert out(res, "kf")["value"] == pytest.approx(1.55, abs=0.05)
    assert out(res, "q")["value"] == pytest.approx(0.85, abs=0.03)


@pytest.mark.parametrize("load,D,r,expected", [
    ("bending", 1.5, 0.05, 2.1),   # Shigley Fig. A-15-9
    ("bending", 1.2, 0.10, 1.6),
    ("tension", 1.5, 0.05, 2.3),   # Fig. A-15-7
    ("torsion", 1.5, 0.10, 1.4),   # Fig. A-15-8
])
def test_kt_stepped_chart_values(load, D, r, expected):
    kt, _ = kt_round("stepped", load, D, 1.0, r)
    assert kt == pytest.approx(expected, abs=0.12)


def test_kt_shallow_groove_limits():
    # semicircular notch in a large bar: tension → ~3, torsion → ~2
    assert kt_round("groove", "tension", 100, 98, 1)[0] == pytest.approx(3.0, abs=0.1)
    assert kt_round("groove", "torsion", 100, 98, 1)[0] == pytest.approx(2.0, abs=0.1)


def test_kt_plate_hole():
    assert kt_plate_hole(0.5, 1.0) == pytest.approx(2.159, abs=0.002)
    assert kt_plate_hole(1e-6, 1.0) == pytest.approx(3.0, abs=1e-4)


def test_scf_error():
    with pytest.raises(CalcError):
        run_calculator(CATALOG["stress_concentration"], {"D": mm(20), "d": mm(30)})
