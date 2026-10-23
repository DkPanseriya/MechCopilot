"""Framework tests + registry-wide invariants every calculator must satisfy."""
import math

import pytest

from engineering.core import (UNIT_CHOICES, CANON, DISPLAY, CalcError, fmt,
                              from_canonical, run_calculator, to_canonical)
from engineering.registry import CATALOG


# --- units ----------------------------------------------------------------

def test_unit_tables_consistent():
    assert set(CANON) == set(UNIT_CHOICES) == set(DISPLAY)


@pytest.mark.parametrize("dim", [d for d in UNIT_CHOICES if d != "dimensionless"])
def test_every_unit_choice_converts(dim):
    for choice in UNIT_CHOICES[dim]:
        v = to_canonical(1.0, choice["value"], dim)
        assert math.isfinite(v)
        back = from_canonical(v, dim, choice["value"])
        assert back == pytest.approx(1.0, rel=1e-9)


def test_conversions():
    assert to_canonical(10, "mm", "length") == pytest.approx(0.010)
    assert to_canonical(2, "kN", "force") == pytest.approx(2000)
    assert to_canonical(250, "MPa", "stress") == pytest.approx(250e6)
    assert to_canonical(1500, "N*mm", "torque") == pytest.approx(1.5)
    assert to_canonical(60, "rpm", "speed") == pytest.approx(60)
    assert to_canonical(2 * math.pi, "rad/s", "speed") == pytest.approx(60)
    assert from_canonical(0.025, "length") == pytest.approx(25)


def test_fmt():
    assert fmt(0) == "0"
    assert fmt(1234.5678) == "1235"
    assert fmt(0.012345) == "0.01235"
    assert fmt(2.0) == "2"
    assert fmt(float("inf")) == "∞"


# --- reference calculator -------------------------------------------------

def test_round_bar_known_values():
    calc = CATALOG["round_bar_combined"]
    res = run_calculator(calc, {
        "D": {"value": 40, "unit": "mm"}, "d": {"value": 0, "unit": "mm"},
        "F": {"value": 0, "unit": "kN"}, "M": {"value": 0, "unit": "N*m"},
        "T": {"value": 250, "unit": "N*m"}, "material": "c45_n",
    })
    out = {o["name"]: o for o in res["outputs"]}
    # tau = 16 T / (pi d^3) = 19.894 MPa ; von Mises = sqrt(3) * tau
    assert out["t_t"]["value"] == pytest.approx(19.894, rel=1e-3)
    assert out["s_vm"]["value"] == pytest.approx(19.894 * math.sqrt(3), rel=1e-3)
    assert out["n"]["value"] == pytest.approx(340 / (19.894 * math.sqrt(3)), rel=1e-3)
    assert res["verdict"] == "ok"
    assert res["series"] and res["steps"] and res["diagram"]["id"] == "round_bar_combined"


def test_round_bar_required_diameter_meets_target():
    calc = CATALOG["round_bar_combined"]
    res = run_calculator(calc, {"M": {"value": 1500, "unit": "N*m"}, "n_target": 3})
    D_req = next(o for o in res["outputs"] if o["name"] == "D_req")["value"]
    check = run_calculator(calc, {"D": {"value": D_req, "unit": "mm"},
                                  "M": {"value": 1500, "unit": "N*m"}, "n_target": 3})
    n = next(o for o in check["outputs"] if o["name"] == "n")["value"]
    assert n == pytest.approx(3, rel=1e-3)


def test_invalid_geometry_raises():
    calc = CATALOG["round_bar_combined"]
    with pytest.raises(CalcError):
        run_calculator(calc, {"D": {"value": 20, "unit": "mm"}, "d": {"value": 25, "unit": "mm"}})


def test_bad_select_raises():
    with pytest.raises(CalcError):
        run_calculator(CATALOG["round_bar_combined"], {"material": "unobtainium"})


# --- registry-wide invariants (every calculator, current and future) ------

ALL_IDS = sorted(CATALOG)


@pytest.mark.parametrize("calc_id", ALL_IDS)
def test_definition_is_well_formed(calc_id):
    c = CATALOG[calc_id]
    assert c.title and c.category and c.summary
    assert c.outputs, "needs at least one output"
    assert any(o.primary for o in c.outputs), "mark at least one output primary"
    names = [p.name for p in c.params]
    assert len(names) == len(set(names)), "duplicate param names"
    for p in c.params:
        assert p.kind in ("number", "select", "bool", "text")
        if p.kind == "number":
            assert p.dim in CANON, f"{p.name}: unknown dim {p.dim}"
        if p.kind == "select":
            assert p.options and p.default in [o["value"] for o in p.options], \
                f"{p.name}: default not in options"
        for dep in (p.show_if or {}):
            assert dep in names, f"{p.name}: show_if refers to unknown param {dep}"
    for o in c.outputs:
        assert o.dim in CANON
    c.to_dict()
    c.llm_summary()


@pytest.mark.parametrize("calc_id", ALL_IDS)
def test_runs_on_defaults(calc_id):
    res = run_calculator(CATALOG[calc_id], {})
    assert res["outputs"], "defaults must produce outputs"
    for o in res["outputs"]:
        if o["value"] is not None:
            assert not math.isnan(o["value"]), f"{o['name']} is NaN on defaults"
    for s in res["series"]:
        assert len(s["x"]) == len(s["y"])
        # A scatter series may be a single operating point; lines need a segment.
        assert len(s["x"]) >= (1 if s["kind"] == "scatter" else 2), f"series {s['id']} too short"


@pytest.mark.parametrize("calc_id", ALL_IDS)
def test_presets_run(calc_id):
    for preset in CATALOG[calc_id].presets:
        run_calculator(CATALOG[calc_id], preset["values"])


@pytest.mark.parametrize("calc_id", ALL_IDS)
def test_result_is_strict_json(calc_id):
    """Starlette refuses inf/NaN; every result must serialise strictly."""
    import json
    json.dumps(run_calculator(CATALOG[calc_id], {}), allow_nan=False)


def test_zero_load_gives_infinite_safety_factor_not_a_crash():
    import json
    res = run_calculator(CATALOG["round_bar_combined"], {
        "F": {"value": 0, "unit": "kN"}, "M": {"value": 0, "unit": "N*m"}, "T": {"value": 0, "unit": "N*m"}})
    n = next(o for o in res["outputs"] if o["name"] == "n")
    assert n["display"] == "∞" and n["value"] is None
    json.dumps(res, allow_nan=False)
