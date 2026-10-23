"""Fastener domain: data against ISO tables, VDI 2230 relations, calculator behaviour."""
import math

import pytest

from engineering.core import CalcError, run_calculator
from engineering.fasteners import data
from engineering.fasteners.joint import plate_compliance
from engineering.registry import CATALOG


def run(calc_id, inputs=None):
    return run_calculator(CATALOG[calc_id], inputs or {})


def out(res, name):
    return next(o for o in res["outputs"] if o["name"] == name)


# --- data -------------------------------------------------------------------

@pytest.mark.parametrize("size,As", [("M6", 20.1), ("M8", 36.6), ("M10", 58.0), ("M12", 84.3),
                                     ("M16", 157.0), ("M20", 245.0), ("M24", 353.0), ("M30", 561.0)])
def test_stress_area_matches_iso_898(size, As):
    assert data.thread(size)["As"] == pytest.approx(As, rel=4e-3)


def test_fine_thread_geometry():
    th = data.thread("M10x1.25")
    assert th["P"] == 1.25 and not th["coarse"]
    assert th["As"] == pytest.approx(61.2, rel=4e-3)       # ISO: M10x1.25 As = 61.2 mm²


def test_property_class_values():
    assert data.strength("8.8", 12)["Sp"] == 580
    assert data.strength("8.8", 20)["Sp"] == 600            # > M16 row
    assert data.strength("10.9", 10)["Rp"] == 940
    assert data.strength("12.9", 10)["Rm"] == 1220
    with pytest.raises(ValueError):
        data.strength("9.8", 20)                            # 9.8 only up to M16


def test_every_size_has_complete_tables():
    for s in data.SIZES:
        assert s in data.HEX and s in data.NUT and s in data.WASHER and s in data.CLEARANCE
        assert s in data.TAP_DRILL
        c = data.CLEARANCE[s]
        assert data.thread(s)["d"] < c["fine"] < c["medium"] < c["coarse"]


def test_stock_length():
    assert data.stock_length(33.2) == 35
    assert data.stock_length(40) == 40
    assert data.stock_length(500) is None


# --- VDI 2230 relations -----------------------------------------------------

def test_tightening_torque_matches_vdi_table():
    # VDI 2230 table value for M10 8.8, μG = μK = 0.12, hex head: ≈ 48 N·m at FM,zul ≈ 29.6 kN
    res = run("bolt_preload_torque", {"thread": "M10", "cls": "8.8", "head": "hex", "friction": "oiled"})
    assert out(res, "MA")["value"] == pytest.approx(48.5, rel=0.04)
    assert out(res, "FMmax")["value"] == pytest.approx(29.6, rel=0.03)


def test_assembly_preload_hits_utilisation():
    res = run("bolt_preload_torque", {"thread": "M12", "cls": "10.9", "nu": 0.9})
    assert out(res, "sred")["value"] == pytest.approx(0.9 * 940, rel=1e-3)


def test_min_preload_uses_tightening_factor():
    res = run("bolt_preload_torque", {"method": "impact"})
    assert out(res, "FMmin")["si_value"] == pytest.approx(out(res, "FMmax")["si_value"] / 2.5, rel=1e-9)
    assert res["verdict"] == "warn"                          # scatter warning


def test_lower_friction_means_higher_preload_and_lower_torque():
    dry = run("bolt_preload_torque", {"friction": "dry"})
    mos2 = run("bolt_preload_torque", {"friction": "mos2"})
    assert out(mos2, "FMmax")["value"] > out(dry, "FMmax")["value"]
    assert out(mos2, "MA")["value"] < out(dry, "MA")["value"]


def test_plate_compliance_continuous_at_cone_limit():
    dW, dh, lK, E = 14.6, 11.0, 30.0, 205000
    full = plate_compliance(dW, dh, 1000.0, lK, E, "through")
    DA_gr = full["DA_gr"]
    a = plate_compliance(dW, dh, DA_gr + 1e-6, lK, E, "through")["dP"]
    b = plate_compliance(dW, dh, DA_gr - 1e-6, lK, E, "through")["dP"]
    assert a == pytest.approx(b, rel=1e-3)


# --- bolted joint -----------------------------------------------------------

def test_joint_force_balance():
    res = run("bolted_joint")
    v = {o["name"]: o["si_value"] for o in res["outputs"]}
    FA = 8000.0
    assert 0 < v["phi"] < 1
    assert v["FKR"] == pytest.approx(v["FM_min"] - (1 - v["phi"]) * FA - v["FZ"], rel=1e-9)
    assert v["FSA"] == pytest.approx(v["phi"] * FA, rel=1e-9)
    assert res["verdict"] == "ok"


def test_joint_separates_under_large_load():
    res = run("bolted_joint", {"FA_max": {"value": 40, "unit": "kN"}})
    assert any(c["label"] == "Joint separation" and c["status"] == "fail" for c in res["checks"])


def test_washer_reduces_surface_pressure():
    bare = run("bolted_joint", {"plate": "al6082", "head": "shcs"})
    wash = run("bolted_joint", {"plate": "al6082", "head": "shcs", "washer": True})
    assert out(wash, "p")["value"] < out(bare, "p")["value"]


def test_static_load_has_no_fatigue_output():
    res = run("bolted_joint", {"FA_min": {"value": 8, "unit": "kN"}})
    assert all(o["name"] != "SF_fatigue" for o in res["outputs"])


def test_joint_rejects_bad_geometry():
    with pytest.raises(CalcError):
        run("bolted_joint", {"l_shank": {"value": 40, "unit": "mm"}, "lK": {"value": 30, "unit": "mm"}})
    with pytest.raises(CalcError):
        run("bolted_joint", {"FA_min": {"value": 10, "unit": "kN"}, "FA_max": {"value": 5, "unit": "kN"}})


# --- shear joint (EN 1993-1-8) ---------------------------------------------

def test_ec3_shear_resistance_m16_88():
    res = run("bolt_shear_joint", {"thread": "M16", "cls": "8.8", "thread_in_plane": True, "planes": "1"})
    # Fv,Rd = 0.6 · 800 · 156.7 / 1.25 = 60.2 kN per bolt
    assert out(res, "Fv")["value"] == pytest.approx(60.2, rel=5e-3)


def test_ec3_bearing_formula():
    res = run("bolt_shear_joint", {"thread": "M16", "t": {"value": 10, "unit": "mm"},
                                   "e1": {"value": 54, "unit": "mm"}, "e2": {"value": 30, "unit": "mm"},
                                   "plate": "s355"})
    d0 = 18.0
    k1 = min(2.8 * 30 / d0 - 1.7, 2.5)
    ab = min(54 / (3 * d0), 800 / 490, 1.0)
    expected = k1 * ab * 490 * 16 * 10 / 1.25 / 1000
    assert out(res, "Fb")["value"] == pytest.approx(expected, rel=1e-3)


def test_slip_needs_preloadable_class():
    with pytest.raises(CalcError):
        run("bolt_shear_joint", {"cls": "4.6", "category": "slip_uls"})


def test_edge_distance_too_small_is_rejected():
    with pytest.raises(CalcError):
        run("bolt_shear_joint", {"e2": {"value": 10, "unit": "mm"}})


# --- thread engagement -----------------------------------------------------

def test_softer_material_needs_longer_engagement():
    steel = run("thread_engagement", {"material": "s355"})
    alu = run("thread_engagement", {"material": "al_cast"})
    assert out(alu, "L_req")["value"] > out(steel, "L_req")["value"]


def test_engagement_check_agrees_with_margin():
    res = run("thread_engagement", {"material": "al_cast", "thread": "M6", "cls": "12.9",
                                    "LE": {"value": 6, "unit": "mm"}})
    assert out(res, "margin")["value"] < 1 and res["verdict"] == "fail"


# --- bolt group -------------------------------------------------------------

def test_two_bolt_group_hand_calc():
    # bolts at x = ±50 mm, F = 10 kN at e = 100 mm: M = 1e6 N·mm, Σr² = 5000 mm²
    # torsional = M·50/5000 = 10 kN (vertical) ; critical = 5 + 10 = 15 kN
    res = run("bolt_group_eccentric", {"pattern": "grid", "rows": 1, "cols": 2,
                                       "px": {"value": 100, "unit": "mm"},
                                       "F": {"value": 10, "unit": "kN"}, "e": {"value": 100, "unit": "mm"}})
    assert out(res, "Rmax")["value"] == pytest.approx(15.0, rel=1e-6)


def test_circle_pattern_zero_eccentricity_shares_equally():
    res = run("bolt_group_eccentric", {"pattern": "circle", "n_circle": 8,
                                       "F": {"value": 16, "unit": "kN"}, "e": {"value": 0, "unit": "mm"}})
    rows = res["tables"][0]["rows"]
    assert all(float(r["R"]) == pytest.approx(2.0, rel=1e-3) for r in rows)


def test_group_needs_two_bolts():
    with pytest.raises(CalcError):
        run("bolt_group_eccentric", {"pattern": "grid", "rows": 1, "cols": 1})


# --- selector & lookup ------------------------------------------------------

def test_selector_size_grows_with_load():
    def size_of(kN_load):
        res = run("fastener_selector", {"FA": {"value": kN_load, "unit": "kN"}, "pref": "8.8"})
        rec = out(res, "recommended")["display"]
        return int(rec.split(" M")[1].split("×")[0])
    assert size_of(2) <= size_of(10) <= size_of(40)


def test_selector_result_is_adequate_and_orderable():
    res = run("fastener_selector")
    rec = out(res, "recommended")["display"]
    assert rec.startswith("ISO 4762 M") and "×" in rec and "ISO 4032" in rec
    hl = res["tables"][0]["highlight"]
    row = next(r for r in res["tables"][0]["rows"] if r["size"] == hl["size"] and r["cls"] == hl["cls"])
    assert row["_status"] == "ok"


def test_selector_aluminium_never_picks_high_classes():
    res = run("fastener_selector", {"joint_type": "tapped_al", "pref": "any",
                                    "FA": {"value": 6, "unit": "kN"}})
    assert all(r["cls"] == "8.8" for r in res["tables"][0]["rows"])


def test_selector_needs_a_load():
    with pytest.raises(CalcError):
        run("fastener_selector", {"FA": {"value": 0, "unit": "kN"}, "FQ": {"value": 0, "unit": "kN"}})


def test_lookup_countersunk_missing_size():
    with pytest.raises(CalcError):
        run("fastener_lookup", {"thread": "M24", "head": "countersunk"})


def test_lookup_reports_proof_load():
    res = run("fastener_lookup", {"thread": "M12", "cls": "8.8"})
    assert out(res, "proof")["value"] == pytest.approx(84.3 * 580 / 1000, rel=4e-3)
