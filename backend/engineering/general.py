"""
General stress calculators. Also the REFERENCE implementation for the
calculator framework — copy its structure for new calculators.
"""
import math
from typing import Any, Dict, List

from .core import (Calculator, CalcError, Output, Param, check, fmt, from_canonical,
                   linspace, series, step)
from .materials import material_params, resolve_material


# --------------------------------------------------------------------------
# Round bar under combined axial + bending + torsion
# --------------------------------------------------------------------------

def _round_bar_stresses(D: float, d: float, F: float, M: float, T: float,
                        Kt: float, Kts: float) -> Dict[str, float]:
    A = math.pi / 4 * (D ** 2 - d ** 2)
    I = math.pi / 64 * (D ** 4 - d ** 4)
    J = 2 * I
    c = D / 2
    s_a = F / A
    s_b = M * c / I
    t_t = T * c / J
    s_x = Kt * (abs(s_a) + abs(s_b))     # worst fibre
    tau = Kts * abs(t_t)
    s_vm = math.sqrt(s_x ** 2 + 3 * tau ** 2)
    t_max = math.sqrt((s_x / 2) ** 2 + tau ** 2)
    return {"A": A, "I": I, "J": J, "s_a": s_a, "s_b": s_b, "t_t": t_t,
            "s_x": s_x, "tau": tau, "s_vm": s_vm, "t_max": t_max}


def _required_diameter(ratio: float, F: float, M: float, T: float, Kt: float, Kts: float,
                       allow: float) -> float:
    """Smallest outer diameter with σ_vm <= allow, keeping inner/outer ratio fixed."""
    lo, hi = 1e-4, 10.0
    f = lambda D: _round_bar_stresses(D, ratio * D, F, M, T, Kt, Kts)["s_vm"] - allow
    if f(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return hi


def _compute_round_bar(x: Dict[str, Any]) -> Dict[str, Any]:
    D, d = x["D"], x["d"]
    if D <= 0:
        raise CalcError("Outer diameter must be positive.")
    if d < 0 or d >= D:
        raise CalcError("Inner diameter must be ≥ 0 and smaller than the outer diameter.")
    mat = resolve_material(x)
    F, M, T, Kt, Kts, n_t = x["F"], x["M"], x["T"], x["Kt"], x["Kts"], x["n_target"]
    if n_t <= 0:
        raise CalcError("Target safety factor must be positive.")

    s = _round_bar_stresses(D, d, F, M, T, Kt, Kts)
    S = mat["Sut"] if mat["brittle"] else mat["Sy"]
    n = S / s["s_vm"] if s["s_vm"] > 0 else float("inf")
    allow = S / n_t
    D_req = _required_diameter(d / D, F, M, T, Kt, Kts, allow)

    # Sizing sweep: von Mises stress vs outer diameter.
    D_hi = max(2 * D, 1.3 * D_req if math.isfinite(D_req) else 0)
    xs = linspace(0.5 * D, D_hi, 60)
    ys = [_round_bar_stresses(Di, d / D * Di, F, M, T, Kt, Kts)["s_vm"] for Di in xs]
    markers = [{"x": D, "label": "current"}]
    if math.isfinite(D_req):
        markers.append({"x": D_req, "label": f"required (n={fmt(n_t, 3)})"})

    checks = [check("Safety factor vs yield", n >= n_t,
                    f"n = {fmt(n, 3)} against a target of {fmt(n_t, 3)}",
                    value=n, limit=n_t)]
    notes = ["Static strength check only. For rotating shafts or fluctuating loads, run the "
             "shaft fatigue (DE-Goodman) calculator."]
    if mat["brittle"]:
        checks.append(check("Brittle material", False,
                            "Grey cast iron has no yield point: safety factor is taken against "
                            "ultimate strength. Prefer the modified-Mohr criterion for final design.",
                            warn=True))
    if Kt == 1 and Kts == 1:
        notes.append("No stress concentration applied (Kt = Kts = 1). Add Kt for fillets, "
                     "grooves or keyways.")

    return {
        "values": {"s_a": s["s_a"], "s_b": s["s_b"], "t_t": s["t_t"], "s_vm": s["s_vm"],
                   "t_max": s["t_max"], "n": n, "D_req": D_req},
        "checks": checks,
        "steps": [
            step("Cross-section area", r"A = \tfrac{\pi}{4}(D^2 - d^2)", s["A"], "area"),
            step("Second moment of area", r"I = \tfrac{\pi}{64}(D^4 - d^4)", s["I"], "inertia"),
            step("Axial stress", r"\sigma_a = F/A", s["s_a"], "stress"),
            step("Bending stress", r"\sigma_b = M\,c/I,\; c = D/2", s["s_b"], "stress"),
            step("Torsional shear", r"\tau_t = T\,c/J,\; J = 2I", s["t_t"], "stress"),
            step("Worst-fibre normal stress", r"\sigma_x = K_t(|\sigma_a| + |\sigma_b|)",
                 s["s_x"], "stress"),
            step("von Mises equivalent", r"\sigma' = \sqrt{\sigma_x^2 + 3\tau^2}", s["s_vm"], "stress"),
            step("Safety factor", r"n = S_y/\sigma'", n),
        ],
        "series": [series("svm_vs_D", "Equivalent stress vs outer diameter", xs, ys,
                          x_label="D", y_label="σ'", x_dim="length", y_dim="stress",
                          markers=markers,
                          ref_lines=[{"y": allow, "label": f"allowable Sy/{fmt(n_t, 3)}"}])],
        "diagram": {
            "D": from_canonical(D, "length"), "d": from_canonical(d, "length"),
            "F": f"{fmt(from_canonical(F, 'force', 'kN'), 3)} kN",
            "M": f"{fmt(M, 3)} N·m", "T": f"{fmt(T, 3)} N·m",
            "s_x": f"{fmt(from_canonical(s['s_x'], 'stress'), 3)} MPa",
            "tau": f"{fmt(from_canonical(s['tau'], 'stress'), 3)} MPa",
            "s_vm": f"{fmt(from_canonical(s['s_vm'], 'stress'), 3)} MPa",
            "n": fmt(n, 3), "ok": n >= n_t,
        },
        "notes": notes,
    }


ROUND_BAR = Calculator(
    id="round_bar_combined",
    governing=["F", "M", "T"],
    trial=["D"],
    title="Round bar: combined loading",
    category="Stress",
    summary="Axial + bending + torsion on a solid or hollow round section, von Mises check and required diameter.",
    description=(
        "Superposes axial, bending and torsional stress at the worst outer fibre of a round "
        "section, combines them with the von Mises criterion and compares against yield. "
        "Also solves for the outer diameter that meets a target safety factor."
    ),
    params=[
        Param("D", "Outer diameter D", dim="length", default=40, unit="mm", min=0, group="Geometry"),
        Param("d", "Inner diameter d (0 = solid)", dim="length", default=0, unit="mm", min=0,
              group="Geometry"),
        Param("F", "Axial force F", dim="force", default=5, unit="kN", group="Loads"),
        Param("M", "Bending moment M", dim="torque", default=200, unit="N*m", group="Loads"),
        Param("T", "Torque T", dim="torque", default=300, unit="N*m", group="Loads"),
        *material_params(default="c45_n"),
        Param("n_target", "Target safety factor", default=2.0, min=1, group="Design"),
        Param("Kt", "Stress concentration Kt (normal)", default=1.0, min=1, group="Design",
              advanced=True, help="Use ~1.5–2.5 for shoulder fillets, ~2 for keyways."),
        Param("Kts", "Stress concentration Kts (shear)", default=1.0, min=1, group="Design",
              advanced=True),
    ],
    outputs=[
        Output("s_vm", "von Mises stress σ'", "stress", primary=True),
        Output("n", "Safety factor n", primary=True, sig=3),
        Output("D_req", "Required outer diameter", "length", primary=True, sig=3),
        Output("s_a", "Axial stress σa", "stress"),
        Output("s_b", "Bending stress σb", "stress"),
        Output("t_t", "Torsional shear τt", "stress"),
        Output("t_max", "Max shear (Tresca)", "stress"),
    ],
    compute=_compute_round_bar,
    diagram="round_bar_combined",
    formulas=[r"\sigma_b = \frac{32 M}{\pi D^3}", r"\tau_t = \frac{16 T}{\pi D^3}",
              r"\sigma' = \sqrt{\sigma_x^2 + 3\tau^2}", r"n = \frac{S_y}{\sigma'}"],
    references=["Shigley's Mechanical Engineering Design, 10th ed., §3-14 and §5-5",
                "Roark's Formulas for Stress and Strain, 8th ed."],
    keywords=["combined stress", "von mises", "shaft", "bending", "torsion", "axial",
              "round bar", "factor of safety", "diameter sizing"],
    presets=[
        {"label": "Drive shaft (torsion dominant)", "values": {"D": {"value": 30, "unit": "mm"},
         "F": {"value": 0, "unit": "kN"}, "M": {"value": 50, "unit": "N*m"},
         "T": {"value": 400, "unit": "N*m"}}},
        {"label": "Axle (bending dominant)", "values": {"D": {"value": 50, "unit": "mm"},
         "F": {"value": 0, "unit": "kN"}, "M": {"value": 1500, "unit": "N*m"},
         "T": {"value": 0, "unit": "N*m"}}},
    ],
)


CALCULATORS: List[Calculator] = [ROUND_BAR]
