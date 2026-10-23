"""Beam solver vs closed-form solutions, section formulas, profile tables, calculators."""
import math

import pytest

from engineering.core import CalcError, run_calculator
from engineering.registry import CATALOG
from engineering.beams.sections import (PROFILES, angle, channel, chs, i_section, rectangle,
                                        rhs, round_bar, tee)
from engineering.beams.solver import DistLoad, PointLoad, PointMoment, Support, solve_beam

L, EI, w, P = 5.0, 4.08e6, 5000.0, 10000.0
TOL = 0.005  # 0.5 %


def ss():
    return [Support(0, "pinned"), Support(L, "roller")]


# --- solver vs closed form ------------------------------------------------

def test_ss_udl():
    r = solve_beam(L, EI, ss(), dist_loads=[DistLoad(0, L, w, w)])
    assert r.M_max[0] == pytest.approx(w * L ** 2 / 8, rel=TOL)
    assert abs(r.v_max[0]) == pytest.approx(5 * w * L ** 4 / (384 * EI), rel=TOL)
    assert r.M_max[1] == pytest.approx(L / 2, abs=L / 100)
    assert [x["R"] for x in r.reactions] == pytest.approx([w * L / 2] * 2, rel=TOL)


def test_ss_central_point():
    r = solve_beam(L, EI, ss(), point_loads=[PointLoad(L / 2, P)])
    assert r.M_max[0] == pytest.approx(P * L / 4, rel=TOL)
    assert abs(r.v_max[0]) == pytest.approx(P * L ** 3 / (48 * EI), rel=TOL)
    assert abs(r.V_max[0]) == pytest.approx(P / 2, rel=TOL)


def test_cantilever_end_load():
    r = solve_beam(L, EI, [Support(0, "fixed")], point_loads=[PointLoad(L, P)])
    assert r.M_max[0] == pytest.approx(-P * L, rel=TOL)          # hogging at the root
    assert abs(r.v_max[0]) == pytest.approx(P * L ** 3 / (3 * EI), rel=TOL)
    assert r.reactions[0]["R"] == pytest.approx(P, rel=TOL)
    assert r.reactions[0]["M"] == pytest.approx(P * L, rel=TOL)


def test_fixed_fixed_udl():
    r = solve_beam(L, EI, [Support(0, "fixed"), Support(L, "fixed")], dist_loads=[DistLoad(0, L, w, w)])
    assert r.M_max[0] == pytest.approx(-w * L ** 2 / 12, rel=TOL)
    mid = min(range(len(r.x)), key=lambda i: abs(r.x[i] - L / 2))
    assert r.M[mid] == pytest.approx(w * L ** 2 / 24, rel=TOL)
    assert abs(r.v_max[0]) == pytest.approx(w * L ** 4 / (384 * EI), rel=TOL)


def test_propped_cantilever_udl():
    r = solve_beam(L, EI, [Support(0, "fixed"), Support(L, "roller")], dist_loads=[DistLoad(0, L, w, w)])
    assert r.M_max[0] == pytest.approx(-w * L ** 2 / 8, rel=TOL)
    assert r.reactions[1]["R"] == pytest.approx(3 * w * L / 8, rel=TOL)


def test_two_span_continuous_udl():
    r = solve_beam(L, EI, [Support(0, "pinned"), Support(L / 2, "roller"), Support(L, "roller")],
                   dist_loads=[DistLoad(0, L, w, w)])
    l = L / 2
    assert r.reactions[1]["R"] == pytest.approx(1.25 * w * l, rel=TOL)   # 10wl/8
    assert r.M_max[0] == pytest.approx(-w * l ** 2 / 8, rel=TOL)


def test_triangular_load():
    r = solve_beam(L, EI, ss(), dist_loads=[DistLoad(0, L, 0, w)])
    assert [x["R"] for x in r.reactions] == pytest.approx([w * L / 6, w * L / 3], rel=TOL)
    assert r.M_max[0] == pytest.approx(w * L ** 2 / (9 * math.sqrt(3)), rel=TOL)


def test_point_moment_reactions():
    M0 = 1000.0
    r = solve_beam(L, EI, ss(), moments=[PointMoment(L / 2, M0)])
    Rs = [x["R"] for x in r.reactions]
    # ΣM about A (ccw +): R_B·L + M0 = 0  ->  R_B = -M0/L, R_A = +M0/L
    assert Rs[0] == pytest.approx(M0 / L, rel=TOL) and Rs[1] == pytest.approx(-M0 / L, rel=TOL)
    # moment jumps by -M0 across the couple (sagging convention)
    i = min(range(len(r.x)), key=lambda k: abs(r.x[k] - (L / 2 + 1e-5)))
    j = min(range(len(r.x)), key=lambda k: abs(r.x[k] - (L / 2 - 1e-5)))
    assert r.M[i] - r.M[j] == pytest.approx(-M0, rel=1e-3)


def test_partial_udl_equilibrium():
    r = solve_beam(L, EI, ss(), dist_loads=[DistLoad(1.0, 3.0, w, w)])
    assert sum(x["R"] for x in r.reactions) == pytest.approx(2.0 * w, rel=1e-6)


def test_unstable_beam_raises():
    with pytest.raises(CalcError):
        solve_beam(L, EI, [Support(1.0, "pinned")], point_loads=[PointLoad(2.0, P)])
    with pytest.raises(CalcError):
        solve_beam(L, EI, ss(), point_loads=[PointLoad(L + 1, P)])


# --- sections --------------------------------------------------------------

def test_rectangle_and_round():
    r = rectangle(0.1, 0.2)
    assert r["Iy"] == pytest.approx(0.1 * 0.2 ** 3 / 12) and r["Wy"] == pytest.approx(0.1 * 0.2 ** 2 / 6)
    c = round_bar(0.05)
    assert c["Iy"] == pytest.approx(math.pi * 0.05 ** 4 / 64)


def test_chs_and_ipe_like_i_section():
    t = chs(0.0603, 0.004)
    assert t["A"] == pytest.approx(math.pi / 4 * (0.0603 ** 2 - 0.0523 ** 2))
    # IPE 200 dimensions with root radius reproduce the table value
    i = i_section(0.100, 0.200, 0.0056, 0.0085, 0.012)
    assert i["A"] * 1e4 == pytest.approx(28.48, rel=0.005)
    assert i["Iy"] * 1e8 == pytest.approx(1943, rel=0.005)


def test_shs_en10219_matches_table():
    s = rhs(0.100, 0.100, 0.005)          # EN 10219: A 18.4 cm2, I 271 cm4, W 54.2 cm3
    assert s["A"] * 1e4 == pytest.approx(18.4, rel=0.01)
    assert s["Iy"] * 1e8 == pytest.approx(271, rel=0.01)
    assert s["Wy"] * 1e6 == pytest.approx(54.2, rel=0.01)


def test_channel_tee_angle_centroids():
    ch = channel(0.075, 0.200, 0.0085, 0.0115)   # ≈ UPN 200 without fillets
    assert ch["Iy"] * 1e8 == pytest.approx(1910, rel=0.05)
    assert 0 < ch["zc"] < 0.075 / 2
    t = tee(0.1, 0.1, 0.01, 0.01)
    assert t["yc"] > 0.05                        # centroid moves toward the flange
    a = angle(0.05, 0.05, 0.005)                 # L50x50x5: A ≈ 4.75 cm2, e ≈ 14 mm
    assert a["A"] * 1e4 == pytest.approx(4.75, rel=0.01)
    assert a["zc"] == pytest.approx(a["yc"]) and a["zc"] * 1000 == pytest.approx(14.0, rel=0.03)


def test_bad_shapes_raise():
    with pytest.raises(CalcError):
        rhs(0.05, 0.05, 0.03)
    with pytest.raises(CalcError):
        i_section(0.1, 0.02, 0.005, 0.012)


def test_profile_tables():
    p = PROFILES["IPE 200"]
    assert p["Iy"] * 1e8 == pytest.approx(1943) and p["Wy"] * 1e6 == pytest.approx(194)
    assert PROFILES["HEB 300"]["Wy"] * 1e6 == pytest.approx(1678)
    families = {p["family"] for p in PROFILES.values()}
    assert families == {"IPE", "HEA", "HEB", "UPN", "SHS", "RHS", "CHS"}
    for name, p in PROFILES.items():
        assert p["Iy"] > 0 and p["Wy"] > 0 and p["mass"] > 0, name


# --- calculators -------------------------------------------------------------

def _out(res, name):
    return next(o for o in res["outputs"] if o["name"] == name)


def test_beam_analysis_matches_hand_calc():
    res = run_calculator(CATALOG["beam_analysis"], {
        "L": 4, "support": "simply_supported", "P1": 0, "w1": 10, "self_weight": False,
        "section_mode": "direct", "I_direct": 1000, "W_direct": 100, "A_direct": 20,
        "material": "s355j2"})
    # M = wL²/8 = 20 kN·m ; σ = 20e3 / 100e-6 = 200 MPa ; δ = 5wL⁴/384EI
    assert _out(res, "M_max")["value"] == pytest.approx(20, rel=TOL)
    assert _out(res, "sigma")["value"] == pytest.approx(200, rel=TOL)
    d = 5 * 10e3 * 4 ** 4 / (384 * 210e9 * 1000e-8) * 1000
    assert _out(res, "delta")["value"] == pytest.approx(d, rel=TOL)
    assert len(res["series"]) == 3 and res["tables"]


def test_beam_analysis_all_support_configs_run():
    for cfg in ("simply_supported", "cantilever", "fixed_fixed", "propped", "overhanging", "two_span"):
        res = run_calculator(CATALOG["beam_analysis"], {"support": cfg})
        assert _out(res, "M_max")["value"] > 0, cfg
        assert res["diagram"]["params"]["supports"]


def test_beam_analysis_bad_load_position():
    with pytest.raises(CalcError):
        run_calculator(CATALOG["beam_analysis"], {"x1": 9})


def test_section_properties_profile_and_shape():
    res = run_calculator(CATALOG["section_properties"], {"section_mode": "profile", "profile": "IPE 300"})
    assert _out(res, "Iy")["value"] == pytest.approx(8356)
    res = run_calculator(CATALOG["section_properties"], {"section_mode": "shape", "shape": "rectangle",
                                                         "b": 50, "h": 100})
    assert _out(res, "Wy")["value"] == pytest.approx(50 * 100 ** 2 / 6 / 1000, rel=1e-6)


def test_profile_selector_picks_lightest_passing():
    res = run_calculator(CATALOG["beam_profile_selector"],
                         {"mode": "direct", "W_req": 190, "I_req": 0, "families": "IPE"})
    assert _out(res, "recommended")["display"] == "IPE 200"
    res = run_calculator(CATALOG["beam_profile_selector"],
                         {"mode": "direct", "W_req": 1e7, "I_req": 0})
    assert res["verdict"] == "fail"
