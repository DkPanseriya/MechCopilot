"""Beam calculators: general beam analysis, section properties, profile selector."""
import math
from typing import Any, Dict, List, Optional

from ..core import (Calculator, CalcError, Output, Param, check, fmt, from_canonical,
                    series, step, table)
from ..materials import material_params, resolve_material
from .sections import (FAMILIES, PROFILES, SHAPES, get_profile, profile_options, shape_props)
from .solver import DistLoad, PointLoad, PointMoment, Support, solve_beam

G = 9.80665

REFERENCES = [
    "Roark's Formulas for Stress and Strain, 8th ed., Ch. 8 (beams)",
    "Gere & Goodno, Mechanics of Materials, 9th ed., Ch. 4–10",
    "EN 1993-1-1:2005 (section classification, LTB §6.3.2 — not checked here)",
    "EN 10365:2017 / EN 10219-2:2006 (profile dimensions and properties)",
]


# --------------------------------------------------------------------------
# Shared section inputs
# --------------------------------------------------------------------------

_SHAPE_OPTS = [{"value": k, "label": v} for k, v in SHAPES.items()]


def _dim_param(name, label, default, shapes, *, unit="mm", advanced=False, help=None):
    return Param(name, label, dim="length", default=default, unit=unit, min=0, group="Section",
                 show_if={"section_mode": ["shape"], "shape": shapes}, advanced=advanced, help=help)


def section_params(modes=("profile", "shape", "direct"), default_mode="profile",
                   default_shape="rhs", with_axis=True) -> List[Param]:
    labels = {"profile": "Standard profile", "shape": "Custom shape", "direct": "Enter I and W directly"}
    ps = [
        Param("section_mode", "Section input", kind="select", default=default_mode, group="Section",
              options=[{"value": m, "label": labels[m]} for m in modes]),
    ]
    if "profile" in modes:
        ps.append(Param("profile", "Profile", kind="select", default="IPE 200", group="Section",
                        options=profile_options(), show_if={"section_mode": ["profile"]}))
    if "shape" in modes:
        ps += [
            Param("shape", "Shape", kind="select", default=default_shape, options=_SHAPE_OPTS,
                  group="Section", show_if={"section_mode": ["shape"]}),
            _dim_param("b", "Width b", 100, ["rectangle", "rhs", "i_section", "channel", "tee", "angle"]),
            _dim_param("h", "Height h", 200, ["rectangle", "rhs", "i_section", "channel", "tee", "angle"]),
            _dim_param("t", "Wall / leg thickness t", 5, ["rhs", "chs", "angle"]),
            _dim_param("D", "Outer diameter D", 60, ["round", "chs"]),
            _dim_param("tw", "Web thickness tw", 5.6, ["i_section", "channel", "tee"]),
            _dim_param("tf", "Flange thickness tf", 8.5, ["i_section", "channel", "tee"]),
            _dim_param("r_root", "Root radius r", 0, ["i_section"], advanced=True,
                       help="Web–flange fillet radius of rolled I-sections (0 for welded)."),
        ]
    if "direct" in modes:
        show = {"section_mode": ["direct"]}
        ps += [
            Param("I_direct", "Second moment of area I", dim="inertia", default=1943, unit="cm**4",
                  min=0, group="Section", show_if=show),
            Param("W_direct", "Elastic section modulus W", dim="section_modulus", default=194,
                  unit="cm**3", min=0, group="Section", show_if=show),
            Param("A_direct", "Area A (for self-weight)", dim="area", default=28.5, unit="cm**2",
                  min=0, group="Section", show_if=show),
        ]
    if with_axis:
        ps.append(Param("axis", "Bending axis", kind="select", default="strong", group="Section",
                        options=[{"value": "strong", "label": "Strong axis (y–y)"},
                                 {"value": "weak", "label": "Weak axis (z–z)"}],
                        show_if={"section_mode": [m for m in ("profile", "shape") if m in modes]}))
    return ps


def resolve_section(x: Dict[str, Any]) -> Dict[str, Any]:
    """Section properties (SI) + label + drawing params from section inputs."""
    mode = x.get("section_mode", "profile")
    if mode == "profile":
        p = dict(get_profile(x["profile"]))
        label = p["name"]
    elif mode == "shape":
        p = shape_props(x["shape"], x["b"], x["h"], x["t"], x["D"], x["tw"], x["tf"],
                        x.get("r_root", 0.0) or 0.0)
        label = SHAPES[x["shape"]]
    else:
        I, W, A = x["I_direct"], x["W_direct"], x["A_direct"]
        if I <= 0 or W <= 0:
            raise CalcError("I and W must be positive.")
        p = {"A": A, "Iy": I, "Iz": I, "Wy": W, "Wz": W, "Avy": None, "Avz": None,
             "mass": A * 7850, "draw": None, "J": None}
        label = f"I = {fmt(from_canonical(I, 'inertia', 'cm**4'), 4)} cm⁴"
    weak = x.get("axis") == "weak" and mode != "direct"
    p["I"] = p["Iz"] if weak else p["Iy"]
    p["W"] = p["Wz"] if weak else p["Wy"]
    p["Av"] = p.get("Avz") if weak else p.get("Avy")
    p["label"] = label + (" (weak axis)" if weak else "")
    p["mode"] = mode
    p["weak"] = weak
    return p


def _open_section(p: Dict[str, Any]) -> bool:
    d = p.get("draw") or {}
    return d.get("shape") in ("i", "channel", "tee", "angle") or p.get("mode") == "direct"


# --------------------------------------------------------------------------
# 1. General beam analysis
# --------------------------------------------------------------------------

SUPPORTS = [
    {"value": "simply_supported", "label": "Simply supported (pin – roller)"},
    {"value": "cantilever", "label": "Cantilever (fixed – free)"},
    {"value": "fixed_fixed", "label": "Fixed – fixed"},
    {"value": "propped", "label": "Propped cantilever (fixed – roller)"},
    {"value": "overhanging", "label": "Overhanging (supports at a and b)"},
    {"value": "two_span", "label": "Two-span continuous"},
]

DEFL_LIMITS = [{"value": v, "label": f"L/{v}"} for v in ("180", "250", "300", "360", "500")] + \
              [{"value": "custom", "label": "Custom absolute limit"}]


def _supports(x: Dict[str, Any], L: float) -> List[Support]:
    cfg = x["support"]
    if cfg == "simply_supported":
        return [Support(0.0, "pinned"), Support(L, "roller")]
    if cfg == "cantilever":
        return [Support(0.0, "fixed")]
    if cfg == "fixed_fixed":
        return [Support(0.0, "fixed"), Support(L, "fixed")]
    if cfg == "propped":
        return [Support(0.0, "fixed"), Support(L, "roller")]
    if cfg == "overhanging":
        a, b = x["a_sup"], x["b_sup"]
        if not (0 <= a < b <= L):
            raise CalcError("Overhanging beam: need 0 ≤ a < b ≤ L for the support positions.")
        return [Support(a, "pinned"), Support(b, "roller")]
    if cfg == "two_span":
        m = x["x_mid"]
        if not (0 < m < L):
            raise CalcError("Two-span beam: the interior support must lie strictly inside the span.")
        return [Support(0.0, "pinned"), Support(m, "roller"), Support(L, "roller")]
    raise CalcError(f"Unknown support configuration '{cfg}'.")


def _ref_span(x: Dict[str, Any], L: float, supports: List[Support]) -> float:
    if x["support"] == "overhanging":
        return supports[1].x - supports[0].x
    if x["support"] == "two_span":
        return max(x["x_mid"], L - x["x_mid"])
    return L


def _kn(v):  # N -> "12.3 kN"
    return f"{fmt(v / 1000, 3)} kN"


def _compute_beam(x: Dict[str, Any]) -> Dict[str, Any]:
    L = x["L"]
    if L <= 0:
        raise CalcError("Span must be positive.")
    mat = resolve_material(x)
    sec = resolve_section(x)
    E, S = mat["E"], (mat["Sut"] if mat["brittle"] else mat["Sy"])
    EI = E * sec["I"]
    n_t = x["n_target"]
    if n_t <= 0:
        raise CalcError("Target safety factor must be positive.")

    supports = _supports(x, L)
    point_loads = [PointLoad(x[f"x{i}"], x[f"P{i}"]) for i in (1, 2, 3) if x[f"P{i}"] != 0]
    dist: List[DistLoad] = []
    if x["w1"] != 0 or (x["w1_shape"] == "linear" and x["w1_end"] != 0):
        a, b = (0.0, L) if x["w1_extent"] == "full" else (x["a1"], x["b1"])
        wb = x["w1_end"] if x["w1_shape"] == "linear" else x["w1"]
        dist.append(DistLoad(a, b, x["w1"], wb))
    if x["w2"] != 0:
        dist.append(DistLoad(x["a2"], x["b2"], x["w2"], x["w2"]))
    moments = [PointMoment(x["xm"], x["M1"])] if x["M1"] != 0 else []
    w_self = sec["A"] * mat["rho"] * G
    if x["self_weight"]:
        dist.append(DistLoad(0.0, L, w_self, w_self))
    if not point_loads and not dist and not moments:
        raise CalcError("No loads applied — enter a point load, distributed load or moment.")

    r = solve_beam(L, EI, supports, point_loads, moments, dist)
    M_val, M_x = r.M_max
    V_val, V_x = r.V_max
    v_val, v_x = r.v_max
    Mabs, Vabs, d = abs(M_val), abs(V_val), abs(v_val)

    sigma = Mabs / sec["W"]
    tau = Vabs / sec["Av"] if sec.get("Av") else None
    n = S / sigma if sigma > 0 else None
    L_ref = _ref_span(x, L, supports)
    if x["defl_limit"] == "custom":
        d_allow = x["defl_custom"]
        lim_label = f"{fmt(from_canonical(d_allow, 'length'), 3)} mm"
    else:
        d_allow = L_ref / float(x["defl_limit"])
        lim_label = f"L/{x['defl_limit']}"
    L_over_d = L_ref / d if d > 0 else None

    checks = []
    if n is not None:
        checks.append(check("Bending stress", n >= n_t,
                            f"σ = {fmt(from_canonical(sigma, 'stress'), 3)} MPa, safety factor "
                            f"{fmt(n, 3)} vs target {fmt(n_t, 3)}", value=n, limit=n_t))
    if tau is not None:
        n_tau = S / (math.sqrt(3) * tau) if tau > 0 else None
        if n_tau is not None:
            checks.append(check("Shear stress", n_tau >= n_t,
                                f"τ ≈ {fmt(from_canonical(tau, 'stress'), 3)} MPa (V / shear area), "
                                f"safety factor {fmt(n_tau, 3)} against Sy/√3", value=n_tau, limit=n_t))
    checks.append(check("Deflection", d <= d_allow,
                        f"δmax = {fmt(from_canonical(d, 'length'), 3)} mm vs limit {lim_label} = "
                        f"{fmt(from_canonical(d_allow, 'length'), 3)} mm",
                        value=d, limit=d_allow))

    notes = []
    if _open_section(sec):
        notes.append("Lateral–torsional buckling is not checked. Open sections bent about the strong "
                     "axis need the compression flange restrained, or an LTB check to EN 1993-1-1 §6.3.2.")
    if sec.get("draw") and sec["draw"].get("shape") == "angle":
        notes.append("Angles bend unsymmetrically; properties about leg-parallel axes are an approximation.")
    if sec["weak"]:
        notes.append("Bending about the weak axis — check that this matches how the member is oriented.")
    if x["self_weight"]:
        notes.append(f"Self-weight included: {fmt(w_self / 1000, 3)} kN/m.")
    else:
        notes.append(f"Self-weight not included ({fmt(w_self / 1000, 3)} kN/m).")
    if x["support"] in ("overhanging", "two_span"):
        notes.append(f"Deflection limit referenced to the longest span between supports ({fmt(L_ref, 3)} m).")

    values: Dict[str, Any] = {
        "M_max": Mabs, "V_max": Vabs, "delta": d, "x_delta": v_x, "sigma": sigma,
        "n": n, "L_delta": L_over_d, "w_self": w_self,
    }
    if tau is not None:
        values["tau"] = tau
    for i, rx in enumerate(r.reactions):
        values[f"R{i + 1}"] = rx["R"]
    fixed = [rx for rx in r.reactions if rx["M"] is not None]
    for i, rx in enumerate(fixed):
        values[f"MR{i + 1}"] = abs(rx["M"])

    # --- plots -------------------------------------------------------------
    xs = r.x.tolist()
    M_allow = S * sec["W"] / n_t
    plots = [
        series("shear", "Shear force V", xs, r.V.tolist(), x_label="x", y_label="V",
               x_dim="length", y_dim="force", x_unit="m", y_unit="kN", kind="area",
               group="Shear force", markers=[{"x": V_x, "label": f"|V|max {_kn(Vabs)}"}]),
        series("moment", "Bending moment M", xs, r.M.tolist(), x_label="x", y_label="M",
               x_dim="length", y_dim="torque", x_unit="m", y_unit="kN*m", kind="area",
               group="Bending moment",
               markers=[{"x": M_x, "label": f"|M|max {fmt(Mabs / 1000, 3)} kN·m"}],
               ref_lines=[{"y": math.copysign(M_allow, M_val) if M_val else M_allow,
                           "label": f"allowable S·W/{fmt(n_t, 3)}"}]),
        series("deflection", "Deflection", xs, r.v.tolist(), x_label="x", y_label="δ",
               x_dim="length", y_dim="length", x_unit="m", y_unit="mm", group="Deflection",
               markers=[{"x": v_x, "label": f"δmax {fmt(from_canonical(d, 'length'), 3)} mm"}],
               ref_lines=[{"y": -d_allow if v_val <= 0 else d_allow, "label": f"limit {lim_label}"}]),
    ]

    rows = []
    for i, rx in enumerate(r.reactions):
        rows.append({"support": i + 1, "x": fmt(rx["x"], 4), "type": rx["kind"],
                     "R": fmt(rx["R"] / 1000, 4),
                     "M": fmt(rx["M"] / 1000, 4) if rx["M"] is not None else "–"})

    # --- diagram -----------------------------------------------------------
    vmax = max(abs(float(v)) for v in r.v) or 1.0
    step_n = max(1, len(xs) // 60)
    shape = [[xs[i] / L, float(r.v[i]) / vmax] for i in range(0, len(xs), step_n)]
    shape.append([1.0, float(r.v[-1]) / vmax])
    wmax = max([abs(dl.wa) for dl in dist] + [abs(dl.wb) for dl in dist] + [1e-12])
    diagram = {
        "L": f"{fmt(L, 4)} m",
        "supports": [{"f": s.x / L, "type": s.kind} for s in supports],
        "points": [{"f": p.x / L, "label": _kn(p.P), "up": p.P < 0} for p in point_loads],
        "dists": [{"a": dl.a / L, "b": dl.b / L, "wa": dl.wa / wmax, "wb": dl.wb / wmax,
                   "label": (f"{fmt(dl.wa / 1000, 3)} kN/m" if dl.wa == dl.wb else
                             f"{fmt(dl.wa / 1000, 3)}→{fmt(dl.wb / 1000, 3)} kN/m"),
                   "self": x["self_weight"] and dl.a == 0 and dl.b == L and dl.wa == w_self}
                  for dl in dist],
        "moments": [{"f": m.x / L, "label": f"{fmt(abs(m.M) / 1000, 3)} kN·m", "ccw": m.M > 0}
                    for m in moments],
        "reactions": [{"f": rx["x"] / L, "label": _kn(rx["R"]),
                       "mlabel": f"{fmt(abs(rx['M']) / 1000, 3)} kN·m" if rx["M"] is not None else None}
                      for rx in r.reactions],
        "maxM": {"f": M_x / L, "label": f"|M|max {fmt(Mabs / 1000, 3)} kN·m"},
        "maxD": {"f": v_x / L, "label": f"δmax {fmt(from_canonical(d, 'length'), 3)} mm"},
        "shape": shape,
        "section": f"{sec['label']} · {mat['name']}",
        "ok": all(c["status"] == "ok" for c in checks),
    }

    steps = [
        step("Second moment of area", r"I", sec["I"], "inertia", "cm**4"),
        step("Elastic section modulus", r"W", sec["W"], "section_modulus", "cm**3"),
        step("Bending stiffness", r"EI = E \cdot I", EI / 1e3, "dimensionless", sig=4),
    ]
    steps[-1]["label"] = "Bending stiffness EI (kN·m²)"
    steps += [
        step("Max moment (FE solution, " + ("sagging" if M_val >= 0 else "hogging") + ")",
             r"|M|_{max}", Mabs, "torque", "kN*m"),
        step("Bending stress", r"\sigma = |M|_{max} / W", sigma, "stress"),
    ]
    if n is not None:
        steps.append(step("Safety factor", r"n = S_y / \sigma", n, sig=3))
    steps.append(step("Allowable deflection", r"\delta_{allow} = L / " + (x["defl_limit"] if x["defl_limit"] != "custom" else r"\text{custom}"),
                      d_allow, "length"))
    steps.append(step("Max deflection", r"|\delta|_{max}", d, "length"))

    return {
        "values": values, "checks": checks, "steps": steps, "series": plots,
        "tables": [table("Support reactions (upward +, moments counter-clockwise +)",
                         [{"key": "support", "label": "#"}, {"key": "x", "label": "x", "unit": "m"},
                          {"key": "type", "label": "Type"}, {"key": "R", "label": "Reaction", "unit": "kN"},
                          {"key": "M", "label": "Moment", "unit": "kN·m"}], rows)],
        "diagram": diagram, "notes": notes,
    }


_loads_group = "Loads"
def _load_point(x: Dict[str, Any]):
    """Default position for a point load or moment: the free tip of a cantilever, else mid-span."""
    if x["support"] == "cantilever":
        return x["L"], "tip of the cantilever"
    return x["L"] / 2, "mid-span"


BEAM_ANALYSIS = Calculator(
    id="beam_analysis",
    derived_defaults={
        "x1": _load_point,
        "xm": _load_point,
        "x_mid": lambda x: (x["L"] / 2, "mid-span"),
        "b1": lambda x: (x["L"], "end of the beam"),
    },
    governing=["L", "support", "P1", "w1", "profile", "shape", "b", "h", "t", "D", "tw", "tf", "I_direct", "W_direct"],
    title="Beam analysis: shear, moment & deflection",
    category="Beams",
    summary="Any common support case with point loads, distributed loads and moments — "
            "SFD, BMD, deflection curve, stress and deflection checks.",
    description=(
        "Solves the beam with a finite-element Euler–Bernoulli model (exact at nodes for these "
        "load types), including statically indeterminate cases such as fixed–fixed, propped "
        "cantilevers and continuous beams. Shear and moment are recovered by statics from the "
        "solved reactions. Loads are downward positive; moments counter-clockwise positive."
    ),
    params=[
        Param("L", "Beam length L", dim="length", default=5, unit="m", min=0, group="Span & supports"),
        Param("support", "Supports", kind="select", default="simply_supported", options=SUPPORTS,
              group="Span & supports"),
        Param("a_sup", "Left support position a", dim="length", default=0.5, unit="m", min=0,
              group="Span & supports", show_if={"support": ["overhanging"]}),
        Param("b_sup", "Right support position b", dim="length", default=4.0, unit="m", min=0,
              group="Span & supports", show_if={"support": ["overhanging"]}),
        Param("x_mid", "Interior support position", dim="length", default=2.5, unit="m", min=0,
              group="Span & supports", show_if={"support": ["two_span"]}),

        Param("P1", "Point load P1 (down +)", dim="force", default=10, unit="kN", group=_loads_group),
        Param("x1", "P1 position x1", dim="length", default=2.5, unit="m", group=_loads_group),
        Param("w1", "Distributed load w1 (down +)", dim="line_load", default=5, unit="kN/m",
              group=_loads_group),
        Param("w1_extent", "w1 extent", kind="select", default="full", group=_loads_group,
              options=[{"value": "full", "label": "Full length"},
                       {"value": "partial", "label": "Partial (from a1 to b1)"}]),
        Param("a1", "w1 start a1", dim="length", default=0, unit="m", group=_loads_group,
              show_if={"w1_extent": ["partial"]}),
        Param("b1", "w1 end b1", dim="length", default=2.5, unit="m", group=_loads_group,
              show_if={"w1_extent": ["partial"]}),
        Param("w1_shape", "w1 distribution", kind="select", default="uniform", group=_loads_group,
              options=[{"value": "uniform", "label": "Uniform"},
                       {"value": "linear", "label": "Linearly varying"}], advanced=True),
        Param("w1_end", "w1 intensity at end", dim="line_load", default=0, unit="kN/m",
              group=_loads_group, show_if={"w1_shape": ["linear"]}, advanced=True),
        Param("P2", "Point load P2", dim="force", default=0, unit="kN", group=_loads_group, advanced=True),
        Param("x2", "P2 position x2", dim="length", default=1.0, unit="m", group=_loads_group, advanced=True),
        Param("P3", "Point load P3", dim="force", default=0, unit="kN", group=_loads_group, advanced=True),
        Param("x3", "P3 position x3", dim="length", default=4.0, unit="m", group=_loads_group, advanced=True),
        Param("w2", "Distributed load w2 (partial)", dim="line_load", default=0, unit="kN/m",
              group=_loads_group, advanced=True),
        Param("a2", "w2 start a2", dim="length", default=0, unit="m", group=_loads_group, advanced=True),
        Param("b2", "w2 end b2", dim="length", default=2.5, unit="m", group=_loads_group, advanced=True),
        Param("M1", "Point moment M (ccw +)", dim="torque", default=0, unit="kN*m",
              group=_loads_group, advanced=True),
        Param("xm", "Moment position", dim="length", default=2.5, unit="m", group=_loads_group,
              advanced=True),
        Param("self_weight", "Include self-weight", kind="bool", default=True, group=_loads_group),

        *section_params(),
        *material_params(default="s355j2"),

        Param("n_target", "Target safety factor (stress)", default=1.5, min=1, group="Design"),
        Param("defl_limit", "Deflection limit", kind="select", default="250", options=DEFL_LIMITS,
              group="Design", help="L/250 typical for floors, L/360 with brittle finishes, L/180 for cantilevers/roofs."),
        Param("defl_custom", "Max allowed deflection", dim="length", default=10, unit="mm", min=0,
              group="Design", show_if={"defl_limit": ["custom"]}),
    ],
    outputs=[
        Output("M_max", "Max bending moment |M|", "torque", unit="kN*m", primary=True),
        Output("delta", "Max deflection", "length", unit="mm", primary=True, sig=3),
        Output("sigma", "Max bending stress σ", "stress", primary=True),
        Output("n", "Safety factor (bending)", primary=True, sig=3),
        Output("V_max", "Max shear force |V|", "force", unit="kN"),
        Output("tau", "Approx. max shear stress τ", "stress"),
        Output("x_delta", "Position of max deflection", "length", unit="m", sig=3),
        Output("L_delta", "Span / deflection ratio", sig=3),
        Output("R1", "Reaction at support 1 (up +)", "force", unit="kN"),
        Output("R2", "Reaction at support 2 (up +)", "force", unit="kN"),
        Output("R3", "Reaction at support 3 (up +)", "force", unit="kN"),
        Output("MR1", "Fixed-end moment, first fixed support", "torque", unit="kN*m"),
        Output("MR2", "Fixed-end moment, second fixed support", "torque", unit="kN*m"),
        Output("w_self", "Self-weight", "line_load", unit="kN/m", sig=3),
    ],
    compute=_compute_beam,
    diagram="beam_analysis",
    formulas=[r"EI\,\frac{d^4 v}{dx^4} = -w(x)", r"M(x) = EI\,\frac{d^2 v}{dx^2}",
              r"\sigma = \frac{M}{W}", r"\delta_{SS,UDL} = \frac{5 w L^4}{384 E I}"],
    references=REFERENCES,
    keywords=["beam", "bending moment", "shear force", "deflection", "SFD", "BMD", "cantilever",
              "simply supported", "fixed beam", "continuous beam", "overhang", "UDL", "point load",
              "I-beam", "IPE", "HEA", "joist", "girder", "lintel"],
    presets=[
        {"label": "Floor beam 6 m, 5 kN/m", "values": {
            "L": 6, "support": "simply_supported", "P1": 0, "w1": 5, "profile": "IPE 240"}},
        {"label": "Cantilever bracket, 2 kN tip", "values": {
            "L": 1.2, "support": "cantilever", "P1": 2, "x1": 1.2, "w1": 0,
            "profile": "RHS 100x50x4", "defl_limit": "180"}},
        {"label": "Two-span continuous, 8 kN/m", "values": {
            "L": 10, "support": "two_span", "x_mid": 5, "P1": 0, "w1": 8, "profile": "IPE 240"}},
    ],
)


# --------------------------------------------------------------------------
# 2. Section properties
# --------------------------------------------------------------------------

_SHAPE_LATEX = {
    "rectangle": (r"A = b h", r"I_y = \frac{b h^3}{12}"),
    "rhs": (r"A = A_{outer} - A_{inner}\ \text{(rounded corners, EN 10219)}",
            r"I_y = I_{outer} - I_{inner}"),
    "round": (r"A = \frac{\pi D^2}{4}", r"I = \frac{\pi D^4}{64}"),
    "chs": (r"A = \frac{\pi}{4}(D^2 - d^2)", r"I = \frac{\pi}{64}(D^4 - d^4)"),
    "i_section": (r"A = 2 b t_f + (h - 2t_f) t_w + (4-\pi) r^2",
                  r"I_y = \frac{b h^3 - (b - t_w)(h - 2t_f)^3}{12} + I_{fillets}"),
    "channel": (r"A = 2 b t_f + (h - 2t_f) t_w", r"I_y = \frac{b h^3 - (b - t_w)(h - 2t_f)^3}{12}"),
    "tee": (r"A = b t_f + (h - t_f) t_w", r"I_y = \sum (I_i + A_i d_i^2)"),
    "angle": (r"A = t (b + h - t)", r"I_y = \sum (I_i + A_i d_i^2)"),
}


def _draw_params(sec: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    d = dict(sec.get("draw") or {})
    d.update({
        "label": sec.get("label", ""),
        "yc": round(sec["yc"] * 1000, 2) if sec.get("yc") is not None else None,
        "zc": round(sec["zc"] * 1000, 2) if sec.get("zc") is not None else None,
    })
    if extra:
        d.update(extra)
    return d


def _compute_section(x: Dict[str, Any]) -> Dict[str, Any]:
    x = dict(x)
    x["axis"] = "strong"
    sec = resolve_section(x)
    rho = x["rho"]
    mass = sec["A"] * rho if sec["mode"] == "shape" else sec["mass"] * rho / 7850.0
    values = {"A": sec["A"], "Iy": sec["Iy"], "Iz": sec["Iz"], "Wy": sec["Wy"], "Wz": sec["Wz"],
              "iy": sec["iy"], "iz": sec["iz"], "J": sec["J"], "mass": mass,
              "yc": sec["yc"], "zc": sec["zc"]}
    if sec["mode"] == "shape":
        la, li = _SHAPE_LATEX[x["shape"]]
        steps = [step("Area", la, sec["A"], "area", "cm**2"),
                 step("Second moment, strong axis", li, sec["Iy"], "inertia", "cm**4"),
                 step("Elastic modulus", r"W_y = I_y / c_{max}", sec["Wy"], "section_modulus", "cm**3"),
                 step("Radius of gyration", r"i_y = \sqrt{I_y / A}", sec["iy"], "length")]
    else:
        steps = [step("Area (table)", r"A", sec["A"], "area", "cm**2"),
                 step("Second moment (table)", r"I_y", sec["Iy"], "inertia", "cm**4"),
                 step("Elastic modulus (table)", r"W_{el,y}", sec["Wy"], "section_modulus", "cm**3")]
    tags = {
        "A": f"A = {fmt(sec['A'] * 1e4, 4)} cm²",
        "Iy": f"Iy = {fmt(sec['Iy'] * 1e8, 4)} cm⁴",
        "Wy": f"Wy = {fmt(sec['Wy'] * 1e6, 4)} cm³",
    }
    notes = []
    if sec["mode"] == "profile":
        notes.append("Standard profile values from EN 10365 tables (I/H/U) or computed with "
                     "EN 10219 corner radii (hollow sections). Mass scaled by the chosen density.")
    if sec.get("draw", {}).get("shape") == "angle":
        notes.append("Angle properties are about centroidal axes parallel to the legs; the principal "
                     "axes are rotated and give a smaller minimum I.")
    return {"values": values, "steps": steps, "diagram": _draw_params(sec, tags), "notes": notes}


SECTION_PROPERTIES = Calculator(
    id="section_properties",
    governing=["profile", "shape", "b", "h", "t", "D", "tw", "tf"],
    title="Section properties",
    category="Beams",
    summary="Area, second moments, section moduli, radii of gyration and mass for common "
            "shapes and standard IPE/HEA/HEB/UPN/SHS/RHS/CHS profiles.",
    description=(
        "Computes cross-section properties about the centroidal strong (y–y) and weak (z–z) axes. "
        "Rolled I-sections include the root fillets; cold-formed hollow sections use EN 10219 "
        "corner radii. Standard profiles use published EN 10365 values."
    ),
    params=[
        *section_params(modes=("shape", "profile"), default_mode="shape", default_shape="i_section",
                        with_axis=False),
        Param("rho", "Material density", dim="density", default=7850, unit="kg/m**3", min=0,
              group="Material", advanced=True),
    ],
    outputs=[
        Output("A", "Area A", "area", unit="cm**2", primary=True),
        Output("Iy", "Second moment Iy (strong)", "inertia", unit="cm**4", primary=True),
        Output("Wy", "Elastic modulus Wy", "section_modulus", unit="cm**3", primary=True),
        Output("Iz", "Second moment Iz (weak)", "inertia", unit="cm**4"),
        Output("Wz", "Elastic modulus Wz", "section_modulus", unit="cm**3"),
        Output("iy", "Radius of gyration iy", "length", unit="mm"),
        Output("iz", "Radius of gyration iz", "length", unit="mm"),
        Output("J", "Torsion constant J (approx.)", "inertia", unit="cm**4"),
        Output("mass", "Mass per metre (kg/m)", sig=4),
        Output("yc", "Centroid height from bottom", "length", unit="mm"),
        Output("zc", "Centroid from left / back", "length", unit="mm"),
    ],
    compute=_compute_section,
    diagram="section_properties",
    formulas=[r"I_y = \int_A z^2\,dA", r"W = \frac{I}{c_{max}}", r"i = \sqrt{I/A}",
              r"I = I_c + A d^2"],
    references=REFERENCES,
    keywords=["section properties", "moment of inertia", "second moment of area", "section modulus",
              "radius of gyration", "IPE", "HEA", "HEB", "UPN", "RHS", "SHS", "CHS", "tube", "channel",
              "angle", "tee", "cross-section"],
    presets=[
        {"label": "IPE 300 (table)", "values": {"section_mode": "profile", "profile": "IPE 300"}},
        {"label": "SHS 100×100×5", "values": {"section_mode": "shape", "shape": "rhs", "b": 100,
                                              "h": 100, "t": 5}},
        {"label": "Tube Ø60×4", "values": {"section_mode": "shape", "shape": "chs", "D": 60, "t": 4}},
    ],
)


# --------------------------------------------------------------------------
# 3. Profile selector
# --------------------------------------------------------------------------

CASES = {
    "ss_udl": ("Simply supported, uniform load", "udl", r"M = \frac{wL^2}{8}",
               r"I_{req} = \frac{5 w L^4}{384\,E\,\delta_{allow}}"),
    "ss_point": ("Simply supported, central point load", "point", r"M = \frac{PL}{4}",
                 r"I_{req} = \frac{P L^3}{48\,E\,\delta_{allow}}"),
    "cant_point": ("Cantilever, tip point load", "point", r"M = P L",
                   r"I_{req} = \frac{P L^3}{3\,E\,\delta_{allow}}"),
    "cant_udl": ("Cantilever, uniform load", "udl", r"M = \frac{w L^2}{2}",
                 r"I_{req} = \frac{w L^4}{8\,E\,\delta_{allow}}"),
    "ff_udl": ("Fixed–fixed, uniform load", "udl", r"M = \frac{w L^2}{12}",
               r"I_{req} = \frac{w L^4}{384\,E\,\delta_{allow}}"),
}


def _case_demand(case: str, L: float, w: float, P: float, E: float, d_allow: float):
    if case == "ss_udl":
        return w * L ** 2 / 8, 5 * w * L ** 4 / (384 * E * d_allow)
    if case == "ss_point":
        return P * L / 4, P * L ** 3 / (48 * E * d_allow)
    if case == "cant_point":
        return P * L, P * L ** 3 / (3 * E * d_allow)
    if case == "cant_udl":
        return w * L ** 2 / 2, w * L ** 4 / (8 * E * d_allow)
    if case == "ff_udl":
        return w * L ** 2 / 12, w * L ** 4 / (384 * E * d_allow)
    raise CalcError(f"Unknown load case '{case}'.")


def _compute_selector(x: Dict[str, Any]) -> Dict[str, Any]:
    steps = []
    notes = []
    if x["mode"] == "loads":
        mat = resolve_material(x)
        S, E = (mat["Sut"] if mat["brittle"] else mat["Sy"]), mat["E"]
        L, n_t = x["L"], x["n_target"]
        if L <= 0 or n_t <= 0:
            raise CalcError("Span and safety factor must be positive.")
        d_allow = L / float(x["defl_limit"])
        M, I_req = _case_demand(x["case"], L, x["w"], x["P"], E, d_allow)
        if M <= 0:
            raise CalcError("Enter a load greater than zero.")
        W_req = M * n_t / S
        _, kind, m_latex, i_latex = CASES[x["case"]]
        steps = [
            step("Design moment", m_latex, M, "torque", "kN*m"),
            step("Required elastic modulus", r"W_{req} = \frac{M\,n}{S_y}", W_req, "section_modulus", "cm**3"),
            step("Allowable deflection", r"\delta_{allow} = L/" + x["defl_limit"], d_allow, "length"),
            step("Required second moment", i_latex, I_req, "inertia", "cm**4"),
        ]
        notes.append("Self-weight not included — re-check the chosen profile in the beam analysis "
                     "calculator with self-weight on.")
    else:
        W_req, I_req = x["W_req"], x["I_req"]
        if W_req <= 0 and I_req <= 0:
            raise CalcError("Enter a required W and/or I greater than zero.")

    weak = x["axis"] == "weak"
    fams = FAMILIES if x["families"] == "all" else [x["families"]]
    passing = []
    for name, p in PROFILES.items():
        if p["family"] not in fams:
            continue
        W = p["Wz"] if weak else p["Wy"]
        I = p["Iz"] if weak else p["Iy"]
        if W >= W_req and (I_req <= 0 or I >= I_req):
            passing.append((p["mass"], name, p, W, I))
    passing.sort(key=lambda t: t[0])

    def row(p, W, I, status="ok"):
        return {"family": p["family"], "profile": p["name"], "mass": fmt(p["mass"], 3),
                "W": fmt(W * 1e6, 4), "I": fmt(I * 1e8, 4),
                "uW": f"{fmt(100 * W_req / W, 3)} %" if W_req > 0 else "–",
                "uI": f"{fmt(100 * I_req / I, 3)} %" if I_req > 0 else "–", "_status": status}

    per_family = []
    for fam in fams:
        best = next((t for t in passing if t[2]["family"] == fam), None)
        if best:
            per_family.append(row(best[2], best[3], best[4]))
        else:
            per_family.append({"family": fam, "profile": "none large enough", "mass": "–", "W": "–",
                               "I": "–", "uW": "–", "uI": "–", "_status": "fail"})

    cols = [{"key": "family", "label": "Family"}, {"key": "profile", "label": "Profile"},
            {"key": "mass", "label": "Mass", "unit": "kg/m"},
            {"key": "W", "label": "Wz" if weak else "Wy", "unit": "cm³"},
            {"key": "I", "label": "Iz" if weak else "Iy", "unit": "cm⁴"},
            {"key": "uW", "label": "W use"}, {"key": "uI", "label": "I use"}]

    values: Dict[str, Any] = {"W_req": W_req, "I_req": I_req if I_req > 0 else None}
    found = bool(passing)
    diagram: Dict[str, Any] = {"shape": None, "label": "No profile found"}
    if found:
        mass, name, p, W, I = passing[0]
        values.update({"recommended": name, "mass_rec": mass,
                       "util_W": W_req / W if W_req > 0 else None,
                       "util_I": I_req / I if I_req > 0 else None})
        diagram = _draw_params({**p, "label": name}, {
            "Wy": f"W = {fmt(W * 1e6, 4)} cm³ (req. {fmt(W_req * 1e6, 4)})",
            "Iy": f"I = {fmt(I * 1e8, 4)} cm⁴" + (f" (req. {fmt(I_req * 1e8, 4)})" if I_req > 0 else ""),
            "A": f"{fmt(mass, 3)} kg/m",
        })
    else:
        values["recommended"] = "none"

    checks = [check("Profile available", found,
                    f"Lightest passing: {passing[0][1]} ({fmt(passing[0][0], 3)} kg/m)" if found
                    else "No standard profile in the selected families meets the requirement. "
                         "Try 'All families', a stronger axis, or a built-up section.")]
    if weak:
        notes.append("Selection is for weak-axis (z–z) bending.")
    notes.append("Open sections (IPE/HEA/HEB/UPN) assume lateral restraint of the compression "
                  "flange; check lateral–torsional buckling separately.")

    return {
        "values": values, "checks": checks, "steps": steps,
        "tables": [
            table("Lightest passing profile per family", cols, per_family,
                  highlight={"profile": passing[0][1]} if found else None),
            table("Lightest passing profiles (all selected families)", cols,
                  [row(t[2], t[3], t[4]) for t in passing[:12]],
                  highlight={"profile": passing[0][1]} if found else None,
                  note="Utilisation = required / provided. Mass from EN 10365 / EN 10219 tables."),
        ],
        "diagram": diagram, "notes": notes,
    }


_load_show = {"mode": ["loads"]}
_sel_material = material_params(default="s355j2")
for _p in _sel_material:
    _p.show_if = {"mode": ["loads"], **(_p.show_if or {})}

PROFILE_SELECTOR = Calculator(
    id="beam_profile_selector",
    governing=["L", "case", "w", "P", "W_req"],
    title="Beam profile selector",
    category="Beams",
    summary="Lightest standard IPE/HEA/HEB/UPN/SHS/RHS/CHS profile meeting a required section "
            "modulus and stiffness — from loads or entered directly.",
    description=(
        "Derives the required elastic section modulus from the design moment and allowable stress, "
        "and the required second moment of area from a deflection limit, then searches the standard "
        "profile tables for the lightest section in each family that satisfies both."
    ),
    params=[
        Param("mode", "Requirement from", kind="select", default="loads", group="Requirement",
              options=[{"value": "loads", "label": "Span and load"},
                       {"value": "direct", "label": "Enter W and I directly"}]),
        Param("L", "Span L", dim="length", default=6, unit="m", min=0, group="Requirement",
              show_if=_load_show),
        Param("case", "Load case", kind="select", default="ss_udl", group="Requirement",
              options=[{"value": k, "label": v[0]} for k, v in CASES.items()], show_if=_load_show),
        Param("w", "Distributed load w", dim="line_load", default=10, unit="kN/m", group="Requirement",
              show_if={"mode": ["loads"], "case": ["ss_udl", "cant_udl", "ff_udl"]}),
        Param("P", "Point load P", dim="force", default=20, unit="kN", group="Requirement",
              show_if={"mode": ["loads"], "case": ["ss_point", "cant_point"]}),
        Param("n_target", "Safety factor on yield", default=1.5, min=1, group="Requirement",
              show_if=_load_show),
        Param("defl_limit", "Deflection limit", kind="select", default="250", group="Requirement",
              options=[o for o in DEFL_LIMITS if o["value"] != "custom"], show_if=_load_show),
        Param("W_req", "Required section modulus W", dim="section_modulus", default=250, unit="cm**3",
              min=0, group="Requirement", show_if={"mode": ["direct"]}),
        Param("I_req", "Required second moment I (0 = ignore)", dim="inertia", default=2500,
              unit="cm**4", min=0, group="Requirement", show_if={"mode": ["direct"]}),
        *_sel_material,
        Param("families", "Profile families", kind="select", default="all", group="Search",
              options=[{"value": "all", "label": "All families"}] +
                      [{"value": f, "label": f} for f in FAMILIES]),
        Param("axis", "Bending axis", kind="select", default="strong", group="Search",
              options=[{"value": "strong", "label": "Strong axis (y–y)"},
                       {"value": "weak", "label": "Weak axis (z–z)"}]),
    ],
    outputs=[
        Output("recommended", "Lightest profile", primary=True),
        Output("mass_rec", "Mass (kg/m)", primary=True, sig=3),
        Output("W_req", "Required W", "section_modulus", unit="cm**3", primary=True),
        Output("I_req", "Required I", "inertia", unit="cm**4"),
        Output("util_W", "W utilisation (req/provided)", sig=3),
        Output("util_I", "I utilisation (req/provided)", sig=3),
    ],
    compute=_compute_selector,
    diagram="beam_profile_selector",
    formulas=[r"W_{req} = \frac{M_{max}\,n}{S_y}", r"I_{req} = \frac{k\,w L^4}{E\,\delta_{allow}}"],
    references=REFERENCES,
    keywords=["beam size", "profile selection", "which beam", "IPE", "HEA", "HEB", "UPN", "RHS",
              "SHS", "CHS", "steel section", "lightest section", "section modulus required"],
    presets=[
        {"label": "Floor beam 6 m, 10 kN/m", "values": {"mode": "loads", "L": 6, "case": "ss_udl", "w": 10}},
        {"label": "Cantilever 2 m, 5 kN tip", "values": {"mode": "loads", "L": 2, "case": "cant_point",
                                                         "P": 5, "defl_limit": "180"}},
        {"label": "Direct: W ≥ 500 cm³", "values": {"mode": "direct", "W_req": 500, "I_req": 0}},
    ],
)


CALCULATORS: List[Calculator] = [BEAM_ANALYSIS, SECTION_PROPERTIES, PROFILE_SELECTOR]
