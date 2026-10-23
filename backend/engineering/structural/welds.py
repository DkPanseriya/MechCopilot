"""Fillet weld groups by the unit-length method (Shigley 10th ed., §9-3 to 9-5)."""
import math
from typing import Any, Dict, List, Tuple

from ..core import (Calculator, CalcError, Output, Param, check, fmt, linspace, series, step)

PATTERNS = {
    "line": "Single line (length d)",
    "two_vertical": "Two parallel lines, d long, b apart",
    "two_horizontal": "Two parallel lines, b long, d apart",
    "c_shape": "Two lines b + one line d (C shape)",
    "box": "All-around rectangle b × d",
    "circle": "All-around circle (diameter d)",
}

# Allowable shear stress on the throat.
CODES = {
    "aws_e60": ("AWS D1.1, E60xx electrode: 0.30·Exx", 0.30 * 413.7e6),
    "aws_e70": ("AWS D1.1, E70xx electrode: 0.30·Exx", 0.30 * 482.6e6),
    "ec3_s235": ("EN 1993-1-8 simplified, S235 (βw 0.80)", 360e6 / (math.sqrt(3) * 0.80 * 1.25)),
    "ec3_s275": ("EN 1993-1-8 simplified, S275 (βw 0.85)", 430e6 / (math.sqrt(3) * 0.85 * 1.25)),
    "ec3_s355": ("EN 1993-1-8 simplified, S355 (βw 0.90)", 490e6 / (math.sqrt(3) * 0.90 * 1.25)),
}


def weld_geometry(pattern: str, b: float, d: float) -> Dict[str, Any]:
    """Unit properties (treat weld as a line): Lu, Ju (Table 9-1), Iu (Table 9-2),
    extreme-fibre distance c, candidate critical points relative to the centroid,
    and the centroid offset xbar from the left/vertical weld (for drawing)."""
    xbar = 0.0
    if pattern == "line":
        Lu, Ju, Iu, c = d, d ** 3 / 12, d ** 3 / 12, d / 2
        pts = [(0.0, d / 2), (0.0, -d / 2)]
    elif pattern == "two_vertical":
        Lu, Ju, Iu, c = 2 * d, d * (3 * b ** 2 + d ** 2) / 6, d ** 3 / 6, d / 2
        pts = [(sx * b / 2, sy * d / 2) for sx in (1, -1) for sy in (1, -1)]
    elif pattern == "two_horizontal":
        Lu, Ju, Iu, c = 2 * b, b * (3 * d ** 2 + b ** 2) / 6, b * d ** 2 / 2, d / 2
        pts = [(sx * b / 2, sy * d / 2) for sx in (1, -1) for sy in (1, -1)]
    elif pattern == "c_shape":
        Lu = 2 * b + d
        xbar = b ** 2 / (2 * b + d)
        Ju = (8 * b ** 3 + 6 * b * d ** 2 + d ** 3) / 12 - b ** 4 / (2 * b + d)
        Iu, c = d ** 2 / 12 * (6 * b + d), d / 2
        pts = [(b - xbar, d / 2), (b - xbar, -d / 2), (-xbar, d / 2), (-xbar, -d / 2)]
    elif pattern == "box":
        Lu, Ju, Iu, c = 2 * (b + d), (b + d) ** 3 / 6, d ** 2 / 6 * (3 * b + d), d / 2
        pts = [(sx * b / 2, sy * d / 2) for sx in (1, -1) for sy in (1, -1)]
    elif pattern == "circle":
        r = d / 2
        Lu, Ju, Iu, c = 2 * math.pi * r, 2 * math.pi * r ** 3, math.pi * r ** 3, r
        pts = [(r * math.cos(t), r * math.sin(t)) for t in linspace(0, 2 * math.pi, 73)]
    else:
        raise CalcError(f"Unknown weld pattern '{pattern}'.")
    return {"Lu": Lu, "Ju": Ju, "Iu": Iu, "c": c, "pts": pts, "xbar": xbar}


def weld_stress(pattern: str, b: float, d: float, h: float, case: str,
                V: float, e: float, N: float) -> Dict[str, Any]:
    g = weld_geometry(pattern, b, d)
    t = 0.707 * h
    A = t * g["Lu"]
    tau_p = V / A
    tau_n = N / A
    out = {"A": A, "t": t, "geo": g, "tau_primary": tau_p}
    if case == "in_plane":
        J = t * g["Ju"]
        T = V * e
        best, crit = -1.0, (0.0, 0.0)
        for (px, py) in g["pts"]:
            tx = -T * py / J
            ty = tau_p + T * px / J
            val = math.sqrt(tx ** 2 + ty ** 2 + tau_n ** 2)
            if val > best:
                best, crit = val, (px, py)
        r = math.hypot(*crit)
        out.update({"J": J, "M": T, "tau_secondary": T * r / J, "tau": best, "crit": crit})
    else:
        I = t * g["Iu"]
        M = V * e
        sig_b = M * g["c"] / I
        tau = math.sqrt(tau_p ** 2 + (sig_b + tau_n) ** 2)
        out.update({"I": I, "M": M, "tau_secondary": sig_b, "tau": tau, "crit": (0.0, g["c"])})
    return out


def _compute_fillet(x: Dict[str, Any]) -> Dict[str, Any]:
    pattern, b, d, h = x["pattern"], x["b"], x["d"], x["h"]
    if d <= 0 or h <= 0:
        raise CalcError("Weld length/diameter d and leg size h must be positive.")
    if pattern in ("two_vertical", "two_horizontal", "c_shape", "box") and b <= 0:
        raise CalcError("Width b must be positive for this weld pattern.")
    V, e, N, case = x["V"], x["e"], x["N"], x["case"]
    if V < 0 or e < 0:
        raise CalcError("Use positive load and eccentricity; the critical weld point is found automatically.")
    code_label, allow = CODES[x["code"]]

    r = weld_stress(pattern, b, d, h, case, V, e, N)
    tau = r["tau"]
    util = tau / allow
    n = allow / tau if tau > 0 else float("inf")
    h_req = h * util
    f_line = tau * r["t"]

    hs = linspace(max(h_req * 0.5, h * 0.25), max(2 * h, 1.5 * h_req), 50)
    taus = [weld_stress(pattern, b, d, hi, case, V, e, N)["tau"] for hi in hs]

    secondary_label = ("Secondary (torsional) shear" if case == "in_plane"
                       else "Bending stress on throat")
    checks = [check("Throat stress", util <= 1.0,
                    f"τ = {fmt(tau / 1e6, 3)} MPa vs allowable {fmt(allow / 1e6, 3)} MPa "
                    f"({code_label}); utilisation {fmt(util * 100, 3)} %", value=util, limit=1.0)]
    checks.append(check("Minimum leg size", h >= 3e-3,
                        "Codes require a minimum fillet size that grows with plate thickness "
                        "(e.g. AWS Table 5.8: 3 mm for ≤6 mm plate, 5 mm to 13 mm, 6 mm to 19 mm, 8 mm above).",
                        warn=True))

    return {
        "values": {"tau": tau, "util": util, "n": n, "h_req": h_req, "A": r["A"],
                   "t": r["t"], "tau_p": r["tau_primary"], "tau_s": r["tau_secondary"],
                   "M": r["M"], "f_line": f_line, "allow": allow},
        "checks": checks,
        "steps": [
            step("Throat thickness", r"t = 0.707\,h", r["t"], "length"),
            step("Throat area", r"A = 0.707\,h\,L_u", r["A"], "area"),
            step("Primary shear", r"\tau' = V/A", r["tau_primary"], "stress"),
            *( [step("Polar moment of throat", r"J = 0.707\,h\,J_u", r["J"], "inertia"),
                step("Torque about weld centroid", r"T = V\,e", r["M"], "torque"),
                step(secondary_label, r"\tau'' = T\,r/J", r["tau_secondary"], "stress")]
               if case == "in_plane" else
               [step("Second moment of throat", r"I = 0.707\,h\,I_u", r["I"], "inertia"),
                step("Bending moment", r"M = V\,e", r["M"], "torque"),
                step(secondary_label, r"\sigma = M\,c/I", r["tau_secondary"], "stress")]),
            step("Resultant (critical point)", r"\tau = \sqrt{\tau'^2 + \tau''^2}", tau, "stress"),
            step("Utilisation", r"\tau/\tau_{allow}", util),
        ],
        "series": [series("tau_vs_h", "Throat stress vs leg size", hs, taus,
                          x_label="h", y_label="τ", x_dim="length", y_dim="stress",
                          markers=[{"x": h, "label": "current"}, {"x": h_req, "label": "required"}],
                          ref_lines=[{"y": allow, "label": "allowable"}])],
        "diagram": {
            "pattern": pattern, "case": case,
            "b": fmt(b * 1e3, 3), "d": fmt(d * 1e3, 3), "h": fmt(h * 1e3, 3), "e": fmt(e * 1e3, 3),
            "V": f"{fmt(V / 1e3, 3)} kN", "N": f"{fmt(N / 1e3, 3)} kN" if N else "",
            "tau": f"{fmt(tau / 1e6, 3)} MPa", "util": f"{fmt(util * 100, 3)} %", "ok": util <= 1.0,
            "xbar_frac": (r["geo"]["xbar"] / b) if b > 0 else 0.0,
            "crit_x": r["crit"][0] / max(b, d), "crit_y": r["crit"][1] / max(b, d),
        },
        "notes": ["Unit-length method: welds treated as lines, stress on the 45° throat "
                  "(conservative for most load directions).",
                  "Weld metal must not be weaker than the base metal; check the base metal "
                  "adjacent to the weld separately."],
    }


FILLET_WELD = Calculator(
    id="fillet_weld",
    title="Fillet weld group",
    category="Welds",
    summary="Shear in a fillet-welded joint under direct, torsional or bending load — throat stress, utilisation and required leg size.",
    description=(
        "Treats each weld as a line (Shigley Tables 9-1 and 9-2). In-plane eccentric loads create "
        "torsion about the weld-group centroid; out-of-plane loads create bending. Primary and "
        "secondary components are combined vectorially at the critical point and compared with "
        "the AWS or Eurocode 3 allowable throat stress."
    ),
    params=[
        Param("pattern", "Weld pattern", kind="select", default="two_vertical",
              options=[{"value": k, "label": v} for k, v in PATTERNS.items()], group="Geometry"),
        Param("b", "Width b", dim="length", default=60, unit="mm", min=0, group="Geometry",
              show_if={"pattern": ["two_vertical", "two_horizontal", "c_shape", "box"]}),
        Param("d", "Length / depth d", dim="length", default=100, unit="mm", min=0, group="Geometry",
              help="For a circle, the weld diameter."),
        Param("h", "Fillet leg size h", dim="length", default=6, unit="mm", min=0, group="Geometry"),
        Param("case", "Load direction", kind="select", default="in_plane",
              options=[{"value": "in_plane", "label": "In the weld plane (torsion)"},
                       {"value": "out_of_plane", "label": "Out of the weld plane (bending)"}],
              group="Load"),
        Param("V", "Shear load V", dim="force", default=10, unit="kN", min=0, group="Load"),
        Param("e", "Eccentricity e", dim="length", default=150, unit="mm", min=0, group="Load",
              help="In-plane: distance from the weld-group centroid to the load line. Out-of-plane: lever arm."),
        Param("N", "Axial load normal to weld plane", dim="force", default=0, unit="kN", group="Load",
              advanced=True),
        Param("code", "Allowable stress basis", kind="select", default="aws_e70",
              options=[{"value": k, "label": v[0]} for k, v in CODES.items()], group="Design"),
    ],
    outputs=[
        Output("tau", "Resultant throat stress τ", "stress", primary=True),
        Output("util", "Utilisation", primary=True, sig=3),
        Output("h_req", "Required leg size", "length", primary=True, sig=3),
        Output("n", "Safety factor vs allowable", sig=3),
        Output("allow", "Allowable throat stress", "stress"),
        Output("tau_p", "Primary shear τ'", "stress"),
        Output("tau_s", "Secondary stress τ''", "stress"),
        Output("M", "Torque / moment at weld", "torque"),
        Output("f_line", "Force per unit weld length", "line_load"),
        Output("A", "Throat area", "area"),
        Output("t", "Throat thickness", "length"),
    ],
    compute=_compute_fillet,
    diagram="fillet_weld",
    formulas=[r"A = 0.707\,h\,L_u,\quad J = 0.707\,h\,J_u,\quad I = 0.707\,h\,I_u",
              r"\tau' = \frac{V}{A},\quad \tau'' = \frac{T\,r}{J}\ \text{or}\ \frac{M\,c}{I}",
              r"\tau = \sqrt{\tau'^2 + \tau''^2} \le \tau_{allow}"],
    references=["Shigley's Mechanical Engineering Design, 10th ed., §9-3 to 9-5, Tables 9-1, 9-2",
                "AWS D1.1 Structural Welding Code — Steel (allowable 0.30·Exx)",
                "EN 1993-1-8:2005 §4.5.3.3 simplified method for fillet welds"],
    keywords=["fillet weld", "weld", "welded joint", "weld size", "throat", "eccentric weld",
              "weld group", "torsion weld", "bracket weld"],
    presets=[
        {"label": "Shigley Ex. 9-1 (two side welds, axial)", "values": {
            "pattern": "two_vertical", "b": {"value": 12.7, "unit": "mm"}, "d": {"value": 50.8, "unit": "mm"},
            "h": {"value": 9.525, "unit": "mm"}, "case": "in_plane", "V": {"value": 73.4, "unit": "kN"},
            "e": {"value": 0, "unit": "mm"}, "code": "aws_e70"}},
        {"label": "Bracket welded all round, bending", "values": {
            "pattern": "box", "b": {"value": 80, "unit": "mm"}, "d": {"value": 120, "unit": "mm"},
            "h": {"value": 5, "unit": "mm"}, "case": "out_of_plane", "V": {"value": 15, "unit": "kN"},
            "e": {"value": 200, "unit": "mm"}, "code": "ec3_s355"}},
    ],
)


CALCULATORS: List[Calculator] = [FILLET_WELD]
