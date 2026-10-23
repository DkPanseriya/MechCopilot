"""Transmission calculators: shafts, keys & fits, gears."""
import math

import pytest

from engineering.core import CalcError, run_calculator
from engineering.registry import CATALOG
from engineering.transmission import iso286
from engineering.transmission.gears import lewis_y, min_pinion_teeth
from engineering.transmission.shafts import critical_speeds, influence


def out(res, name):
    return next(o for o in res["outputs"] if o["name"] == name)["value"]


def run(cid, inputs=None):
    return run_calculator(CATALOG[cid], inputs or {})


# --- ISO 286 ----------------------------------------------------------------

@pytest.mark.parametrize("size,cls,expected", [
    (50, "H7", (25, 0)), (50, "g6", (-9, -25)), (50, "k6", (18, 2)), (50, "p6", (42, 26)),
    (50, "s6", (59, 43)), (25, "H7", (21, 0)), (25, "f7", (-20, -41)), (25, "js7", (10, -10)),
    (50, "K7", (7, -18)), (50, "M7", (0, -25)), (50, "N7", (-8, -33)), (50, "P7", (-17, -42)),
    (50, "S7", (-34, -59)), (50, "G7", (34, 9)), (25, "F8", (53, 20)), (90, "r6", (73, 51)),
    (2, "K7", (0, -10)), (2, "N7", (-4, -14)), (5, "K7", (3, -9)), (50, "N9", (0, -62)),
    (35, "js6", (8, -8)), (100, "h9", (0, -87)),
])
def test_iso286_spot_values(size, cls, expected):
    letter, grade = iso286.parse_class(cls)
    devs = iso286.hole_deviations(size, letter, grade) if letter[0].isupper() \
        else iso286.shaft_deviations(size, letter, grade)
    assert devs == pytest.approx(expected)


def test_iso286_fit_types():
    assert iso286.fit(50, ("H", 7), ("g", 6))["type"] == "Clearance fit"
    assert iso286.fit(50, ("H", 7), ("k", 6))["type"] == "Transition fit"
    assert iso286.fit(50, ("H", 7), ("s", 6))["type"] == "Interference fit"


def test_iso286_size_bounds():
    with pytest.raises(CalcError):
        iso286.it_value(0, 7)
    with pytest.raises(CalcError):
        iso286.it_value(600, 7)


def test_iso_fits_calculator_h7g6():
    res = run("iso_fits", {"size": {"value": 50, "unit": "mm"}})
    assert out(res, "c_max") == pytest.approx(50)   # µm
    assert out(res, "c_min") == pytest.approx(9)
    assert next(o for o in res["outputs"] if o["name"] == "fit_type")["display"] == "Clearance fit"


# --- Shaft fatigue ---------------------------------------------------------

EX_7_1 = {"d": {"value": 28, "unit": "mm"}, "Ma": {"value": 142.4, "unit": "N*m"},
          "Mm": {"value": 0, "unit": "N*m"}, "Ta": {"value": 0, "unit": "N*m"},
          "Tm": {"value": 124.3, "unit": "N*m"}, "kf_mode": "direct", "Kf": 1.58, "Kfs": 1.39,
          "material": "custom", "material_Sy": {"value": 574, "unit": "MPa"},
          "material_Sut": {"value": 735, "unit": "MPa"}, "surface": "machined",
          "reliability": "0.99"}


def test_shigley_example_7_1():
    """Shigley 10th ed. Ex. 7-1: Goodman ≈1.62, Gerber ≈1.87, ASME ≈1.88, Soderberg ≈1.56, ny ≈4.58."""
    res = run("shaft_fatigue", EX_7_1)
    assert out(res, "Se") == pytest.approx(205, rel=0.02)
    assert out(res, "n_goodman") == pytest.approx(1.62, rel=0.03)
    assert out(res, "n_gerber") == pytest.approx(1.87, rel=0.03)
    assert out(res, "n_asme") == pytest.approx(1.88, rel=0.03)
    assert out(res, "n_soderberg") == pytest.approx(1.56, rel=0.03)
    assert out(res, "n_yield") == pytest.approx(4.58, rel=0.01)


def test_shaft_required_diameter_meets_target():
    res = run("shaft_fatigue", {**EX_7_1, "n_target": 2.0})
    d_req = out(res, "d_req")
    res2 = run("shaft_fatigue", {**EX_7_1, "d": {"value": d_req, "unit": "mm"}})
    assert out(res2, "n_goodman") == pytest.approx(2.0, rel=1e-3)


def test_shaft_feature_kf_and_no_load_error():
    res = run("shaft_fatigue", {"kf_mode": "ring_groove"})
    assert out(res, "Kf") == pytest.approx(5.0)
    assert out(res, "Kfs") == pytest.approx(3.0)
    with pytest.raises(CalcError):
        run("shaft_fatigue", {"Ma": 0, "Mm": 0, "Ta": 0, "Tm": 0})


# --- Critical speed --------------------------------------------------------

def test_uniform_shaft_closed_form():
    L, d, E, rho = 0.6, 0.03, 210e9, 7850
    r = critical_speeds(L, d, 0, E, rho, "simply_supported", [])
    I, A = math.pi * d ** 4 / 64, math.pi * d ** 2 / 4
    assert r["w_shaft"] == pytest.approx(math.pi ** 2 / L ** 2 * math.sqrt(E * I / (rho * A)))


def test_influence_coefficients():
    L, EI = 1.0, 1000.0
    # simply supported, central load: L^3/(48EI)
    assert influence(0.5, 0.5, L, EI, "simply_supported") == pytest.approx(L ** 3 / (48 * EI))
    # cantilever tip: L^3/(3EI)
    assert influence(1.0, 1.0, L, EI, "cantilever") == pytest.approx(L ** 3 / (3 * EI))
    # fixed-fixed central: L^3/(192EI)
    assert influence(0.5, 0.5, L, EI, "fixed_fixed") == pytest.approx(L ** 3 / (192 * EI))
    # Maxwell reciprocity
    assert influence(0.3, 0.7, L, EI, "simply_supported") == \
        pytest.approx(influence(0.7, 0.3, L, EI, "simply_supported"))


def test_single_mass_rayleigh_is_exact():
    L, d, E, rho = 0.6, 0.03, 210e9, 7850
    r = critical_speeds(L, d, 0, E, rho, "simply_supported", [(10.0, 0.3)])
    I = math.pi * d ** 4 / 64
    a11 = 0.3 ** 2 * 0.3 ** 2 / (3 * E * I * L)
    assert r["w_ray"] == pytest.approx(1 / math.sqrt(10 * a11), rel=1e-6)
    assert r["w_c"] < min(r["w_ray"], r["w_shaft"])  # Dunkerley lower bound


def test_critical_speed_mass_outside_span():
    with pytest.raises(CalcError):
        run("shaft_critical_speed", {"x1": {"value": 700, "unit": "mm"}})


def test_critical_speed_resonance_flagged():
    res = run("shaft_critical_speed", {"n_op": {"value": 3800, "unit": "rpm"}})
    assert res["checks"][0]["status"] == "fail"


# --- Parallel key ----------------------------------------------------------

def test_key_stresses():
    res = run("parallel_key")  # d 40 -> 12x8, t1 5, L 40 form A -> l_eff 28, T 250
    F = 2 * 250 / 0.04
    assert out(res, "tau") == pytest.approx(F / (12 * 28), rel=1e-6)          # MPa
    assert out(res, "p_hub") == pytest.approx(F / (3 * 28), rel=1e-6)
    assert out(res, "p_shaft") == pytest.approx(F / (5 * 28), rel=1e-6)
    assert next(o for o in res["outputs"] if o["name"] == "key")["display"] == "12 × 8"


def test_key_out_of_table():
    with pytest.raises(CalcError):
        run("parallel_key", {"d": {"value": 5, "unit": "mm"}})


# --- Interference fit ------------------------------------------------------

def test_lame_same_material_closed_form():
    """Same E, solid shaft: p = E δ (D² − d²) / (2 d D²)  (Shigley eq. 3-57)."""
    res = run("interference_fit", {"hub_material": "c45_n", "shaft_material": "c45_qt"})
    E, delta, d, D = 210e9, 30e-6, 0.04, 0.08
    p = E * delta * (D ** 2 - d ** 2) / (2 * d * D ** 2)
    assert out(res, "p_max") == pytest.approx(p / 1e6, rel=1e-6)
    T = math.pi * 0.15 * p * d ** 2 * 0.04 / 2
    assert out(res, "T_cap") == pytest.approx(T, rel=1e-6)


def test_interference_from_fit():
    res = run("interference_fit", {"mode": "fit", "fit": "H7/s6", "d": {"value": 50, "unit": "mm"},
                                   "D": {"value": 100, "unit": "mm"}})
    assert out(res, "dmax") == pytest.approx(59)
    assert out(res, "dmin") == pytest.approx(18)


def test_interference_bad_geometry():
    with pytest.raises(CalcError):
        run("interference_fit", {"D": {"value": 30, "unit": "mm"}})


# --- Spur gear -------------------------------------------------------------

def test_lewis_table():
    assert lewis_y(20) == pytest.approx(0.322)
    assert lewis_y(23) == pytest.approx((0.331 + 0.337) / 2)
    assert min_pinion_teeth(math.radians(20), 1.0) == pytest.approx(12.32, rel=0.01)
    assert min_pinion_teeth(math.radians(20), 1e6) == pytest.approx(17.1, rel=0.02)


def test_spur_gear_stresses():
    res = run("spur_gear")  # m2 z20/50 b25 3 kW 1450 rpm cut, steel 300 HB
    T1 = 3000 / (1450 * 2 * math.pi / 60)
    Wt = 2 * T1 / 0.04
    V = math.pi * 0.04 * 1450 / 60
    Kv = (6.1 + V) / 6.1
    sb = Kv * Wt / (0.025 * 0.002 * 0.322)
    assert out(res, "sb1") == pytest.approx(sb / 1e6, rel=1e-6)
    phi = math.radians(20)
    Cp = math.sqrt(1 / (math.pi * 2 * (1 - 0.09) / 207e9))
    sc = Cp * math.sqrt(Kv * Wt / (0.025 * math.cos(phi))
                        * (2 / (0.04 * math.sin(phi)) + 2 / (0.1 * math.sin(phi))))
    assert out(res, "sc") == pytest.approx(sc / 1e6, rel=1e-6)
    assert out(res, "a") == pytest.approx(70)
    assert 1.5 < out(res, "eps") < 1.8


def test_spur_gear_bad_teeth():
    with pytest.raises(CalcError):
        run("spur_gear", {"z1": 5})
