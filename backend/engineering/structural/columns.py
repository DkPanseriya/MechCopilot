"""Column buckling: Euler (long) and Johnson parabola (intermediate). Shigley §4-11 to 4-14."""
import math
from typing import Any, Dict, List

from ..core import (Calculator, CalcError, Output, Param, check, fmt, linspace, series, step)
from ..materials import material_params, resolve_material

END_CONDITIONS = {
    # key: (label, effective length factor K)
    "pinned_pinned": ("Pinned – pinned (K = 1.0)", 1.0),
    "fixed_free": ("Fixed – free / flagpole (K = 2.0)", 2.0),
    "fixed_pinned": ("Fixed – pinned, theoretical (K = 0.7)", 0.7),
    "fixed_pinned_rec": ("Fixed – pinned, recommended (K = 0.8)", 0.8),
    "fixed_fixed": ("Fixed – fixed, theoretical (K = 0.5)", 0.5),
    "fixed_fixed_rec": ("Fixed – fixed, recommended (K = 0.65)", 0.65),
}

SECTIONS = {
    "round": "Solid round",
    "tube": "Round tube",
    "rect": "Solid rectangle",
    "custom": "Custom (A and I)",
}


def section_props(x: Dict[str, Any]) -> Dict[str, float]:
    s = x["section"]
    if s == "round":
        d = x["d"]
        if d <= 0:
            raise CalcError("Diameter must be positive.")
        return {"A": math.pi * d ** 2 / 4, "I": math.pi * d ** 4 / 64}
    if s == "tube":
        D, t = x["D"], x["t"]
        if D <= 0 or t <= 0 or 2 * t >= D:
            raise CalcError("Tube needs D > 0 and 0 < t < D/2.")
        di = D - 2 * t
        return {"A": math.pi * (D ** 2 - di ** 2) / 4, "I": math.pi * (D ** 4 - di ** 4) / 64}
    if s == "rect":
        b, h = x["b"], x["h"]
        if b <= 0 or h <= 0:
            raise CalcError("Rectangle sides must be positive.")
        lo, hi = min(b, h), max(b, h)
        return {"A": b * h, "I": hi * lo ** 3 / 12}  # weak axis governs
    A, I = x["A"], x["I"]
    if A <= 0 or I <= 0:
        raise CalcError("Area and second moment must be positive.")
    return {"A": A, "I": I}


def critical_stress(slender: float, E: float, Sy: float) -> Dict[str, Any]:
    """σcr for effective slenderness Le/k; Johnson below the transition, Euler above."""
    trans = math.sqrt(2 * math.pi ** 2 * E / Sy)
    if slender >= trans:
        return {"scr": math.pi ** 2 * E / slender ** 2, "regime": "Euler (elastic)", "trans": trans}
    return {"scr": Sy - (Sy * slender / (2 * math.pi)) ** 2 / E,
            "regime": "Johnson (inelastic)", "trans": trans}


def _compute_column(x: Dict[str, Any]) -> Dict[str, Any]:
    L, P = x["L"], x["P"]
    if L <= 0:
        raise CalcError("Length must be positive.")
    if P < 0:
        raise CalcError("Use a positive compressive load.")
    mat = resolve_material(x)
    E, Sy = mat["E"], mat["Sy"]
    label, K = END_CONDITIONS[x["ends"]]
    props = section_props(x)
    A, I = props["A"], props["I"]
    k = math.sqrt(I / A)
    Le = K * L
    lam = Le / k
    cs = critical_stress(lam, E, Sy)
    scr, trans = cs["scr"], cs["trans"]
    Pcr = scr * A
    n = Pcr / P if P > 0 else float("inf")
    n_t = x["n_target"]
    P_allow = Pcr / n_t
    s_app = P / A

    checks = [check("Buckling safety", n >= n_t,
                    f"Pcr = {fmt(Pcr / 1e3, 4)} kN ({cs['regime']}), n = {fmt(n, 3)} "
                    f"(target {fmt(n_t, 3)})", value=n, limit=n_t)]
    if lam < 10:
        checks.append(check("Short block", False,
                            f"Le/k = {fmt(lam, 3)} is very low: this is a compression block, "
                            "governed by yield (P/A ≤ Sy) rather than buckling.", warn=True))
    if lam > 200:
        checks.append(check("Very slender", False,
                            f"Le/k = {fmt(lam, 3)} > 200 — sensitive to imperfections and side loads.",
                            warn=True))

    lam_max = max(2.2 * trans, 1.3 * lam)
    lj = linspace(0, trans, 40)
    le = linspace(trans * 0.75, lam_max, 50)
    return {
        "values": {"Pcr": Pcr, "n": n, "P_allow": P_allow, "lam": lam, "trans": trans,
                   "scr": scr, "s_app": s_app, "k": k, "Le": Le, "A": A, "I": I,
                   "regime": cs["regime"]},
        "checks": checks,
        "steps": [
            step("Area", r"A", A, "area"),
            step("Second moment (weak axis)", r"I", I, "inertia"),
            step("Radius of gyration", r"k = \sqrt{I/A}", k, "length"),
            step("Effective length", r"L_e = K\,L", Le, "length"),
            step("Slenderness", r"L_e/k", lam),
            step("Transition slenderness", r"(L_e/k)_1 = \sqrt{2\pi^2 E/S_y}", trans),
            step("Critical stress", r"\sigma_{cr} = \frac{\pi^2E}{(L_e/k)^2}" if lam >= trans
                 else r"\sigma_{cr} = S_y - \frac{1}{E}\left(\frac{S_y L_e}{2\pi k}\right)^2", scr, "stress"),
            step("Critical load", r"P_{cr} = \sigma_{cr}A", Pcr, "force", "kN"),
            step("Safety factor", r"n = P_{cr}/P", n),
        ],
        "series": [
            series("johnson", "Johnson parabola", lj, [critical_stress(v, E, Sy)["scr"] if v > 0 else Sy for v in lj],
                   x_label="Le/k", y_label="σcr", y_dim="stress", group="Column curve"),
            series("euler", "Euler hyperbola", le, [math.pi ** 2 * E / v ** 2 for v in le],
                   x_label="Le/k", y_label="σcr", y_dim="stress", group="Column curve"),
            series("point", "This column", [lam], [scr], x_label="Le/k", y_label="σcr",
                   y_dim="stress", kind="scatter", group="Column curve",
                   ref_lines=[{"y": s_app, "label": "applied P/A"}],
                   markers=[{"x": trans, "label": "transition"}]),
        ],
        "diagram": {
            "ends": x["ends"], "K": fmt(K, 3), "L": fmt(L * 1e3, 4), "Le": fmt(Le * 1e3, 4),
            "P": f"{fmt(P / 1e3, 3)} kN", "Pcr": f"{fmt(Pcr / 1e3, 4)} kN", "n": fmt(n, 3),
            "ok": n >= n_t, "regime": cs["regime"], "lam": fmt(lam, 3),
        },
        "notes": ["Assumes a straight, centrally loaded, prismatic column. For eccentric loads use "
                  "the secant formula; design codes (EN 1993-1-1, AISC 360) add imperfection factors."],
    }


COLUMN = Calculator(
    id="column_buckling",
    governing=["P", "L", "ends", "d", "D", "t", "b", "h", "A", "I"],
    title="Column buckling (Euler–Johnson)",
    category="Columns",
    summary="Critical load of a compression member with Euler for slender and Johnson for intermediate columns.",
    description=(
        "Computes slenderness from the weak-axis radius of gyration and the effective length "
        "factor. Above the transition slenderness the elastic Euler load applies; below it the "
        "Johnson parabola accounts for inelastic buckling."
    ),
    params=[
        Param("section", "Cross-section", kind="select", default="tube",
              options=[{"value": k, "label": v} for k, v in SECTIONS.items()], group="Section"),
        Param("d", "Diameter d", dim="length", default=30, unit="mm", min=0, group="Section",
              show_if={"section": ["round"]}),
        Param("D", "Outer diameter D", dim="length", default=48.3, unit="mm", min=0, group="Section",
              show_if={"section": ["tube"]}),
        Param("t", "Wall thickness t", dim="length", default=3.2, unit="mm", min=0, group="Section",
              show_if={"section": ["tube"]}),
        Param("b", "Width b", dim="length", default=40, unit="mm", min=0, group="Section",
              show_if={"section": ["rect"]}),
        Param("h", "Depth h", dim="length", default=20, unit="mm", min=0, group="Section",
              show_if={"section": ["rect"]}),
        Param("A", "Area A", dim="area", default=500, unit="mm**2", min=0, group="Section",
              show_if={"section": ["custom"]}),
        Param("I", "Second moment I (weak axis)", dim="inertia", default=50000, unit="mm**4", min=0,
              group="Section", show_if={"section": ["custom"]}),
        Param("L", "Length L", dim="length", default=1500, unit="mm", min=0, group="Geometry"),
        Param("ends", "End conditions", kind="select", default="pinned_pinned",
              options=[{"value": k, "label": v[0]} for k, v in END_CONDITIONS.items()], group="Geometry"),
        Param("P", "Axial load P", dim="force", default=20, unit="kN", min=0, group="Load"),
        *material_params(default="s355j2"),
        Param("n_target", "Target safety factor", default=3.0, min=1, group="Design",
              help="Buckling is sudden: 2.5–3.5 is common for machine design."),
    ],
    outputs=[
        Output("Pcr", "Critical load Pcr", "force", unit="kN", primary=True),
        Output("n", "Safety factor", primary=True, sig=3),
        Output("P_allow", "Allowable load", "force", unit="kN", primary=True),
        Output("regime", "Regime"),
        Output("lam", "Slenderness Le/k", sig=4),
        Output("trans", "Transition slenderness", sig=4),
        Output("scr", "Critical stress", "stress"),
        Output("s_app", "Applied stress P/A", "stress"),
        Output("k", "Radius of gyration", "length"),
        Output("Le", "Effective length", "length"),
        Output("A", "Area", "area"),
        Output("I", "Second moment (weak axis)", "inertia"),
    ],
    compute=_compute_column,
    diagram="column_buckling",
    formulas=[r"P_{cr} = \frac{\pi^2 E I}{(K L)^2}",
              r"\frac{P_{cr}}{A} = S_y - \frac{1}{E}\left(\frac{S_y}{2\pi}\frac{KL}{k}\right)^2",
              r"\left(\frac{KL}{k}\right)_1 = \sqrt{\frac{2\pi^2E}{S_y}}"],
    references=["Shigley's Mechanical Engineering Design, 10th ed., §4-11 to 4-14, Table 4-2",
                "AISC 360 Commentary, effective length factors"],
    keywords=["column", "buckling", "euler", "johnson", "slenderness", "strut", "compression member",
              "critical load", "effective length"],
    presets=[
        {"label": "Hydraulic cylinder rod (fixed–free)", "values": {
            "section": "round", "d": {"value": 30, "unit": "mm"}, "L": {"value": 600, "unit": "mm"},
            "ends": "fixed_free", "P": {"value": 15, "unit": "kN"}, "material": "c45_qt"}},
        {"label": "Scaffold tube 48.3×3.2", "values": {
            "section": "tube", "L": {"value": 2000, "unit": "mm"}, "ends": "pinned_pinned",
            "P": {"value": 18, "unit": "kN"}, "material": "s235jr"}},
    ],
)


CALCULATORS: List[Calculator] = [COLUMN]
