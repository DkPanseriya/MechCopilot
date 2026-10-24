"""Pressure vessels: thick-wall (Lamé) cylinders and spheres, thin-wall comparison."""
import math
from typing import Any, Dict, List, Tuple

from ..core import (Calculator, CalcError, Output, Param, check, fmt, linspace, series, step)
from ..materials import material_params, resolve_material


def lame(shape: str, ri: float, ro: float, pi: float, po: float, r: float,
         closed: bool) -> Tuple[float, float, float]:
    """(hoop, radial, axial) stress at radius r."""
    if shape == "cylinder":
        den = ro ** 2 - ri ** 2
        a = (pi * ri ** 2 - po * ro ** 2) / den
        b = ri ** 2 * ro ** 2 * (pi - po) / den
        st = a + b / r ** 2
        sr = a - b / r ** 2
        sl = a if closed else 0.0
        return st, sr, sl
    den = ro ** 3 - ri ** 3
    a = (pi * ri ** 3 - po * ro ** 3) / den
    b = ri ** 3 * ro ** 3 * (pi - po) / den
    st = a + b / (2 * r ** 3)
    sr = a - b / r ** 3
    return st, sr, st  # sphere: two equal tangential components


def von_mises(s1: float, s2: float, s3: float) -> float:
    return math.sqrt(0.5 * ((s1 - s2) ** 2 + (s2 - s3) ** 2 + (s3 - s1) ** 2))


def max_vm(shape: str, ri: float, ro: float, pi: float, po: float, closed: bool) -> Tuple[float, float]:
    """Max von Mises over the wall (checked at inner and outer surface) and where."""
    vi = von_mises(*lame(shape, ri, ro, pi, po, ri, closed))
    vo = von_mises(*lame(shape, ri, ro, pi, po, ro, closed))
    return (vi, ri) if vi >= vo else (vo, ro)


def _required_t(shape, ri, pi, po, closed, allow) -> float:
    f = lambda t: max_vm(shape, ri, ri + t, pi, po, closed)[0] - allow
    lo, hi = ri * 1e-5, ri * 50
    if f(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return hi


def _compute_vessel(x: Dict[str, Any]) -> Dict[str, Any]:
    shape, Di, t = x["shape"], x["Di"], x["t"]
    pi, po = x["p_i"], x["p_o"]
    closed = x["closed"] if shape == "cylinder" else True
    if Di <= 0 or t <= 0:
        raise CalcError("Inner diameter and wall thickness must be positive.")
    if pi < 0 or po < 0:
        raise CalcError("Pressures are gauge values and must be ≥ 0.")
    if pi == 0 and po == 0:
        raise CalcError("Enter an internal or external pressure.")
    mat = resolve_material(x)
    S = mat["Sy"]
    ri, ro = Di / 2, Di / 2 + t
    n_t = x["n_target"]

    st_i, sr_i, sl_i = lame(shape, ri, ro, pi, po, ri, closed)
    st_o, sr_o, sl_o = lame(shape, ri, ro, pi, po, ro, closed)
    vm, r_vm = max_vm(shape, ri, ro, pi, po, closed)
    n = S / vm if vm > 0 else float("inf")
    t_req = _required_t(shape, ri, pi, po, closed, S / n_t)

    p = pi - po
    if shape == "cylinder":
        st_thin, sl_thin = p * Di / (2 * t), (p * Di / (4 * t) if closed else 0.0)
    else:
        st_thin = sl_thin = p * Di / (4 * t)
    thin = t / ri <= 0.1

    checks = [check("Wall strength (von Mises)", n >= n_t,
                    f"σ' max = {fmt(vm / 1e6, 4)} MPa at the {'inner' if r_vm == ri else 'outer'} surface, "
                    f"n = {fmt(n, 3)} vs yield (target {fmt(n_t, 3)})", value=n, limit=n_t)]
    if math.isnan(t_req):
        checks.append(check("Thickness limit", False,
                            "No wall thickness reaches the target: the pressure exceeds what a "
                            "thick wall of this material can carry elastically. Use stronger "
                            "material, autofrettage or compound (shrink-fit) cylinders.", warn=True))
    p_cr = None
    if po > 0:
        nu = mat["nu"]
        E = mat["E"]
        Dm = Di + t
        if shape == "cylinder":
            p_cr = 2 * E / (1 - nu ** 2) * (t / Dm) ** 3
            rule = "long-tube elastic collapse 2E/(1−ν²)·(t/D)³"
        else:
            p_cr = 2 * E * (t / (Dm / 2)) ** 2 / math.sqrt(3 * (1 - nu ** 2))
            rule = "classical sphere buckling (real shells can fail at ~25 % of this)"
        ratio = p_cr / po
        checks.append(check("External pressure buckling", ratio >= 3,
                            f"Elastic collapse estimate {fmt(p_cr / 1e5, 4)} bar ({rule}), "
                            f"{fmt(ratio, 3)}× the external pressure. Design external-pressure "
                            "shells to ASME VIII-1 UG-28 / EN 13445-3 §8.", warn=True,
                            value=ratio, limit=3))

    rs = linspace(ri, ro, 30)
    st_l, sr_l, sl_l = zip(*[lame(shape, ri, ro, pi, po, r, closed) for r in rs])
    out_series = [
        series("hoop", "Hoop σt", rs, list(st_l), x_label="r", y_label="σ", x_dim="length",
               y_dim="stress", group="Stress through the wall"),
        series("radial", "Radial σr", rs, list(sr_l), x_label="r", y_label="σ", x_dim="length",
               y_dim="stress", group="Stress through the wall"),
    ]
    if shape == "cylinder" and closed:
        out_series.append(series("axial", "Axial σl", rs, list(sl_l), x_label="r", y_label="σ",
                                 x_dim="length", y_dim="stress", group="Stress through the wall"))

    values = {"vm": vm, "n": n, "t_req": t_req, "st_i": st_i, "sr_i": sr_i, "sl_i": sl_i,
              "st_o": st_o, "st_thin": st_thin, "sl_thin": sl_thin, "t_over_r": t / ri}
    if p_cr is not None:
        values["p_cr"] = p_cr

    lame_latex = (r"\sigma_t = \frac{p_ir_i^2 - p_or_o^2}{r_o^2-r_i^2} + \frac{r_i^2r_o^2(p_i-p_o)}{r^2(r_o^2-r_i^2)}"
                  if shape == "cylinder" else
                  r"\sigma_t = \frac{p_ir_i^3 - p_or_o^3}{r_o^3-r_i^3} + \frac{r_i^3r_o^3(p_i-p_o)}{2r^3(r_o^3-r_i^3)}")
    return {
        "values": values,
        "checks": checks,
        "steps": [
            step("Inner / outer radius", r"r_i = D_i/2,\ r_o = r_i + t", ro, "length"),
            step("Hoop stress at bore (Lamé)", lame_latex, st_i, "stress"),
            step("Radial stress at bore", r"\sigma_r(r_i) = -p_i", sr_i, "stress"),
            step("Axial stress", r"\sigma_l = \frac{p_ir_i^2 - p_or_o^2}{r_o^2-r_i^2}" if shape == "cylinder"
                 else r"\sigma_l = \sigma_t", sl_i, "stress"),
            step("Max von Mises", r"\sigma' = \sqrt{\tfrac12[(\sigma_t-\sigma_r)^2+(\sigma_r-\sigma_l)^2+(\sigma_l-\sigma_t)^2]}",
                 vm, "stress"),
            step("Thin-wall hoop (comparison)", r"\sigma_t \approx \frac{p D_i}{2t}" if shape == "cylinder"
                 else r"\sigma \approx \frac{p D_i}{4t}", st_thin, "stress"),
            step("Safety factor", r"n = S_y/\sigma'", n),
        ],
        "series": out_series,
        "diagram": {
            "shape": shape, "Di": fmt(Di * 1e3, 4), "t": fmt(t * 1e3, 3),
            "pi": f"{fmt(pi / 1e5, 4)} bar" if pi else "", "po": f"{fmt(po / 1e5, 4)} bar" if po else "",
            "st": f"{fmt(st_i / 1e6, 4)} MPa", "vm": f"{fmt(vm / 1e6, 4)} MPa", "n": fmt(n, 3),
            "ok": n >= n_t, "t_frac": min(t / ro, 0.6),
        },
        "notes": [("Thin-wall formulas are within a few percent here (t/rᵢ ≤ 0.1)." if thin else
                   "Thick wall (t/rᵢ > 0.1): use the Lamé values, thin-wall formulas under-predict the bore stress."),
                  "Strength check only. Pressure-equipment design must follow ASME VIII / EN 13445 "
                  "(allowable stresses, weld efficiency, corrosion allowance, openings)."],
    }


PRESSURE_VESSEL = Calculator(
    id="pressure_vessel",
    governing=["p_i", "p_o", "Di"],
    trial=["t"],
    title="Pressure vessel wall (Lamé)",
    category="Pressure Vessels",
    summary="Hoop, radial and axial stress in a cylinder or sphere under internal/external pressure, thick or thin wall.",
    description=(
        "Exact Lamé solution for thick-walled cylinders and spheres with both internal and "
        "external pressure, compared with the thin-wall formulas. Finds the wall thickness that "
        "meets a target safety factor on von Mises stress and flags external-pressure buckling."
    ),
    params=[
        Param("shape", "Shape", kind="select", default="cylinder",
              options=[{"value": "cylinder", "label": "Cylinder"}, {"value": "sphere", "label": "Sphere"}],
              group="Geometry"),
        Param("Di", "Inner diameter Di", dim="length", default=200, unit="mm", min=0, group="Geometry"),
        Param("t", "Wall thickness t", dim="length", default=8, unit="mm", min=0, group="Geometry"),
        Param("closed", "Closed ends (axial stress)", kind="bool", default=True, group="Geometry",
              show_if={"shape": ["cylinder"]}),
        Param("p_i", "Internal pressure pi", dim="stress", default=100, unit="bar", min=0, group="Load"),
        Param("p_o", "External pressure po", dim="stress", default=0, unit="bar", min=0, group="Load"),
        *material_params(default="s355j2"),
        Param("n_target", "Target safety factor", default=2.0, min=1, group="Design"),
    ],
    outputs=[
        Output("vm", "Max von Mises σ'", "stress", primary=True),
        Output("n", "Safety factor", primary=True, sig=3),
        Output("t_req", "Required wall thickness", "length", primary=True, sig=3),
        Output("st_i", "Hoop stress at bore", "stress"),
        Output("sr_i", "Radial stress at bore", "stress"),
        Output("sl_i", "Axial stress", "stress"),
        Output("st_o", "Hoop stress at outer surface", "stress"),
        Output("st_thin", "Thin-wall hoop stress", "stress"),
        Output("sl_thin", "Thin-wall axial stress", "stress"),
        Output("t_over_r", "Wall ratio t/rᵢ", sig=3),
        Output("p_cr", "External collapse estimate", "stress", unit="bar"),
    ],
    compute=_compute_vessel,
    diagram="pressure_vessel",
    formulas=[r"\sigma_t = \frac{p_ir_i^2 - p_or_o^2 - r_i^2r_o^2(p_o-p_i)/r^2}{r_o^2 - r_i^2}",
              r"\sigma_r = \frac{p_ir_i^2 - p_or_o^2 + r_i^2r_o^2(p_o-p_i)/r^2}{r_o^2 - r_i^2}",
              r"\sigma_t^{thin} = \frac{pD_i}{2t},\quad \sigma_l^{thin} = \frac{pD_i}{4t}"],
    references=["Shigley's Mechanical Engineering Design, 10th ed., §3-13 and §3-14",
                "Roark's Formulas for Stress and Strain, 8th ed., Table 13.5",
                "ASME BPVC Section VIII Div. 1, UG-27 (thin shells) and UG-28 (external pressure)"],
    keywords=["pressure vessel", "lame", "thick wall", "thin wall", "hoop stress", "cylinder",
              "pipe wall thickness", "tank", "sphere", "hydraulic cylinder barrel"],
    presets=[
        {"label": "Hydraulic cylinder barrel 250 bar", "values": {
            "Di": {"value": 63, "unit": "mm"}, "t": {"value": 7, "unit": "mm"},
            "p_i": {"value": 250, "unit": "bar"}, "material": "steel_1045_cd"}},
        {"label": "Air receiver 11 bar", "values": {
            "Di": {"value": 500, "unit": "mm"}, "t": {"value": 4, "unit": "mm"},
            "p_i": {"value": 11, "unit": "bar"}, "material": "s235jr", "n_target": 3.5}},
    ],
)


CALCULATORS: List[Calculator] = [PRESSURE_VESSEL]
