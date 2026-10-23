"""Bearing domain: ISO 281 theory, database, calculators, importer."""
import csv
import math

import pytest

from engineering.core import CalcError, run_calculator
from engineering.registry import CATALOG
from engineering.bearings import data, theory
from engineering.bearings.importer import ImportError_, import_csv, validate_rows


def out(res, name):
    return next(o for o in res["outputs"] if o["name"] == name)


# --- theory ---------------------------------------------------------------

def test_basic_life_ball_cubic():
    # L10 = (C/P)^3 for ball bearings
    assert theory.basic_life(14800, 1480, 3) == pytest.approx(1000.0)
    assert theory.hours(1000.0, 1000) == pytest.approx(1000 * 1e6 / 60000)


def test_dgbb_xy_selection():
    b = data.get("6205")
    # Small axial share -> X = 1, Y = 0
    f = theory.dgbb_factors(Fr=1000, Fa=100, C0=b["C0"], f0=b["f0"])
    assert (f["X"], f["Y"]) == (1.0, 0.0)
    # Large axial share -> X = 0.56, Y from table (f0·Fa/C0 = 14·2000/7800 = 3.59 -> Y ≈ 1.14)
    f = theory.dgbb_factors(Fr=500, Fa=2000, C0=b["C0"], f0=b["f0"])
    assert f["X"] == 0.56
    assert 1.10 < f["Y"] < 1.16
    assert 0.37 < f["e"] < 0.40


def test_a1_table():
    assert theory.A1["90"] == 1.0
    assert theory.A1["95"] == 0.64
    assert theory.A1["99"] == 0.25


def test_rated_viscosity_formula():
    # n >= 1000: 4500 n^-0.5 dm^-0.5 ; n < 1000: 45000 n^-0.83 dm^-0.5
    assert theory.rated_viscosity(1500, 38.5) == pytest.approx(4500 / math.sqrt(1500 * 38.5))
    assert theory.rated_viscosity(500, 100) == pytest.approx(45000 * 500 ** -0.83 / 10)


def test_aiso_sanity_and_branch_continuity():
    hi = theory.a_iso(4.0, 1.0, 1000, 2000, "ball", False)
    lo = theory.a_iso(0.1, 0.5, 1000, 2000, "ball", False)
    assert hi > 5 and lo == pytest.approx(0.1, abs=0.02)
    assert theory.a_iso(4.0, 1.0, 50000, 1000, "ball", False) == 50.0  # capped
    for elem in ("ball", "roller"):
        for k in (0.4, 1.0):
            a = theory.a_iso(k - 1e-9, 0.5, 300, 2000, elem, False)
            b = theory.a_iso(k + 1e-9, 0.5, 300, 2000, elem, False)
            # ISO 281's published constants are rounded, so branches meet to ~0.03 %.
            assert a == pytest.approx(b, rel=1e-3), f"{elem} discontinuous at κ={k}"


def test_viscosity_from_iso_vg():
    assert theory.nu_at_temperature("68", 40) == pytest.approx(68, rel=1e-3)
    assert theory.nu_at_temperature("68", 100) == pytest.approx(8.7, rel=1e-3)
    assert 15 < theory.nu_at_temperature("68", 70) < 25


def test_type_load_rules():
    with pytest.raises(theory.LoadError):
        theory.equivalent_loads(data.get("NU 205"), 1000, 100)   # NU: no axial
    with pytest.raises(theory.LoadError):
        theory.equivalent_loads(data.get("51105"), 1000, 1000)   # thrust: no radial
    trb = data.get("30205")
    r = theory.equivalent_loads(trb, 1000, 1000)                 # Fa/Fr > e
    assert r["P"] == pytest.approx(0.4 * 1000 + trb["Y"] * 1000)


# --- database -------------------------------------------------------------

def test_database_coverage_and_links():
    counts = {t: len(data.by_type(t)) for t in data.TYPES}
    assert counts["dgbb"] >= 70 and all(v >= 20 for v in counts.values())
    b = data.get("6205")
    assert (b["d"], b["D"], b["B"]) == (25, 52, 15)
    links = data.skf_links(b, "2rsh")
    assert any("productid-6205" in l["url"] for l in links)
    assert any("q=6205-2RSH" in l["url"] for l in links)
    assert data.variant_designation(data.get("7205 BE")) == "7205 BECBP"
    assert data.limiting_speed(b, "2rsh") < b["n_lim"]


# --- calculators ----------------------------------------------------------

def test_bearing_life_matches_hand_calc():
    res = run_calculator(CATALOG["bearing_life"], {
        "btype": "dgbb", "des_dgbb": "6205", "Fr": {"value": 1.48, "unit": "kN"},
        "Fa": {"value": 0, "unit": "kN"}, "n": {"value": 1000, "unit": "rpm"},
    })
    # P = Fr = 1480 N -> L10 = (14800/1480)^3 = 1000 Mrev -> 16 667 h
    assert out(res, "L10")["value"] == pytest.approx(1000, rel=1e-6)
    assert out(res, "L10h")["value"] == pytest.approx(16666.7, rel=1e-4)
    assert res["links"] and res["tables"][0]["rows"]


def test_bearing_life_reliability_reduces_life():
    base = {"des_dgbb": "6205"}
    l90 = out(run_calculator(CATALOG["bearing_life"], {**base, "reliability": "90"}), "Lnmh")["value"]
    l99 = out(run_calculator(CATALOG["bearing_life"], {**base, "reliability": "99"}), "Lnmh")["value"]
    assert l99 == pytest.approx(0.25 * l90, rel=1e-6)


def test_bearing_life_custom_bearing():
    res = run_calculator(CATALOG["bearing_life"], {
        "btype": "custom", "c_C": {"value": 20, "unit": "kN"}, "c_C0": {"value": 10, "unit": "kN"},
        "Fr": {"value": 2, "unit": "kN"}, "Fa": {"value": 0, "unit": "kN"},
    })
    assert out(res, "L10")["value"] == pytest.approx(1000, rel=1e-6)


def test_bearing_life_rejects_axial_on_nu():
    with pytest.raises(CalcError):
        run_calculator(CATALOG["bearing_life"], {"btype": "crb", "des_crb": "NU 205"})


def test_selector_finds_compact_bearing():
    res = run_calculator(CATALOG["bearing_selector"], {})
    assert out(res, "best")["display"] == "6207"
    assert res["verdict"] == "ok"
    first = res["tables"][0]["rows"][0]
    assert first["_status"] == "ok" and first["_links"]


def test_selector_reports_impossible_request():
    res = run_calculator(CATALOG["bearing_selector"], {
        "Fr": {"value": 200, "unit": "kN"}, "bore_max": {"value": 25, "unit": "mm"}})
    assert out(res, "best")["display"] == "none found"
    assert res["verdict"] == "fail"


def test_required_c():
    res = run_calculator(CATALOG["bearing_required_c"], {})
    # L10 = 60*1500*20000/1e6 = 1800 Mrev ; C = 2 kN * 1800^(1/3) = 24.33 kN
    assert out(res, "C_req")["value"] == pytest.approx(2 * 1800 ** (1 / 3), rel=1e-6)
    assert data.get(next(r["_base"] for r in res["tables"][0]["rows"] if r.get("_base")))["type"] != "tbb"


# --- importer -------------------------------------------------------------

def test_importer_round_trip(tmp_path):
    src = tmp_path / "mine.csv"
    src.write_text("designation,type,d,D,B,C,C0,Pu,n_ref,n_lim\n"
                   "MY-6205,dgbb,25,52,15,15.0,8.0,0.34,28000,18000\n", encoding="utf-8")
    dest = tmp_path / "user" / "bearings.csv"
    assert import_csv(str(src), str(dest)) == 1
    rows = data.load_user_rows(str(dest))
    assert rows[0]["base"] == "MY-6205" and rows[0]["C"] == pytest.approx(15000)
    assert rows[0]["source"] == "user"


def test_importer_rejects_bad_rows():
    with pytest.raises(ImportError_):
        validate_rows([{"designation": "X", "type": "nope", "d": "1", "D": "2", "B": "1",
                        "C": "1", "C0": "1", "Pu": "1", "n_ref": "1", "n_lim": "1"}])
    with pytest.raises(ImportError_):
        validate_rows([{"designation": "X", "type": "trb", "d": "20", "D": "47", "B": "15",
                        "C": "30", "C0": "30", "Pu": "3", "n_ref": "9000", "n_lim": "11000"}])
