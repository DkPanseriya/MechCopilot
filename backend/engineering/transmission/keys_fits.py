"""Keys & fits: DIN 6885 parallel keys, ISO 286 limits and fits, Lamé interference fits."""
import math
from typing import Any, Dict, List

from ..core import (Calculator, CalcError, Output, Param, check, fmt, from_canonical,
                    linspace, series, step, table)
from ..materials import material_params, resolve_material
from . import iso286

# --------------------------------------------------------------------------
# Parallel key — DIN 6885-1 (ISO 773 equivalent sizes)
# --------------------------------------------------------------------------

# (shaft over, up to, b, h, t1 shaft keyway depth, t2 hub keyway depth) in mm
KEY_TABLE = [
    (6, 8, 2, 2, 1.2, 1.0), (8, 10, 3, 3, 1.8, 1.4), (10, 12, 4, 4, 2.5, 1.8),
    (12, 17, 5, 5, 3.0, 2.3), (17, 22, 6, 6, 3.5, 2.8), (22, 30, 8, 7, 4.0, 3.3),
    (30, 38, 10, 8, 5.0, 3.3), (38, 44, 12, 8, 5.0, 3.3), (44, 50, 14, 9, 5.5, 3.8),
    (50, 58, 16, 10, 6.0, 4.3), (58, 65, 18, 11, 7.0, 4.4), (65, 75, 20, 12, 7.5, 4.9),
    (75, 85, 22, 14, 9.0, 5.4), (85, 95, 25, 14, 9.0, 5.4), (95, 110, 28, 16, 10.0, 6.4),
    (110, 130, 32, 18, 11.0, 7.4), (130, 150, 36, 20, 12.0, 8.4), (150, 170, 40, 22, 13.0, 9.4),
    (170, 200, 45, 25, 15.0, 10.4), (200, 230, 50, 28, 17.0, 11.4),
    (230, 260, 56, 32, 20.0, 12.4), (260, 290, 63, 32, 20.0, 12.4),
    (290, 330, 70, 36, 22.0, 14.4), (330, 380, 80, 40, 25.0, 15.4),
    (380, 440, 90, 45, 28.0, 17.4), (440, 500, 100, 50, 31.0, 19.5),
]

KEY_LENGTHS = [6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 32, 36, 40, 45, 50, 56, 63, 70, 80,
               90, 100, 110, 125, 140, 160, 180, 200, 220, 250, 280, 320, 360, 400]

APPLICATION = {
    "1.0": "Uniform (electric motor, steady load)",
    "1.25": "Light shock",
    "1.5": "Moderate shock",
    "1.75": "Heavy shock",
}


def key_for_shaft(d_mm: float):
    for row in KEY_TABLE:
        if row[0] < d_mm <= row[1]:
            return row
    raise CalcError("DIN 6885-1 covers shaft diameters above 6 mm up to 500 mm.")


def _std_length(l_mm: float) -> float:
    for L in KEY_LENGTHS:
        if L >= l_mm - 1e-9:
            return float(L)
    return float("nan")


def _compute_key(x: Dict[str, Any]) -> Dict[str, Any]:
    d, T, L, L_hub = x["d"], abs(x["T"]), x["L"], x["L_hub"]
    if d <= 0 or L <= 0:
        raise CalcError("Shaft diameter and key length must be positive.")
    d_mm = d * 1000
    _, _, b, h, t1, t2 = key_for_shaft(d_mm)
    b_m, h_m, t1_m = b / 1000, h / 1000, t1 / 1000
    hub_h = h_m - t1_m
    form_a = x["form"] == "A"
    l_eff = L - b_m if form_a else L
    if l_eff <= 0:
        raise CalcError("Key is shorter than its width: increase the length (form A keys lose b to the rounded ends).")
    KA, S = float(x["KA"]), x["S"]
    if S <= 0:
        raise CalcError("Safety factor must be positive.")

    key = resolve_material(x, "key_material")
    hub = resolve_material(x, "hub_material")
    shaft = resolve_material(x, "shaft_material")

    F = 2 * KA * T / d
    tau = F / (b_m * l_eff)
    p_shaft = F / (t1_m * l_eff)
    p_hub = F / (hub_h * l_eff)
    Sy_hub_side = min(key["Sy"], hub["Sy"])
    Sy_shaft_side = min(key["Sy"], shaft["Sy"])
    tau_y = 0.577 * key["Sy"]
    n_shear = tau_y / tau
    n_crush = min(Sy_hub_side / p_hub, Sy_shaft_side / p_shaft)

    l_req = max(S * F / (b_m * tau_y), S * F / (hub_h * Sy_hub_side), S * F / (t1_m * Sy_shaft_side))
    L_req = l_req + (b_m if form_a else 0)
    L_std = _std_length(L_req * 1000) / 1000

    checks = [
        check("Key shear", n_shear >= S, f"n = {fmt(n_shear, 3)} (τ = {fmt(tau / 1e6, 3)} MPa)",
              value=n_shear, limit=S),
        check("Surface pressure (crushing)", n_crush >= S,
              f"n = {fmt(n_crush, 3)}; hub side p = {fmt(p_hub / 1e6, 3)} MPa",
              value=n_crush, limit=S),
        check("Key fits in hub", L <= L_hub + 1e-9,
              f"key {fmt(L * 1000, 3)} mm vs hub {fmt(L_hub * 1000, 3)} mm", value=L, limit=L_hub),
    ]
    if L > 1.5 * d:
        checks.append(check("Key length", False,
                            "Key longer than 1.5·d: load is not shared evenly along the key. "
                            "Consider two keys at 180° or a spline.", warn=True))

    Ls = linspace(max(b_m * 1.2, 0.25 * L), max(2 * L, 1.3 * L_req), 50)
    ps = [F / (hub_h * (Li - b_m if form_a else Li)) for Li in Ls]

    neighbours = [r for r in KEY_TABLE if r[1] >= d_mm - 25 and r[0] <= d_mm + 25]
    rows = [{"range": f"{r[0]}–{r[1]}", "bh": f"{r[2]} × {r[3]}", "t1": r[4], "t2": r[5]}
            for r in neighbours]

    return {
        "values": {"key": f"{b} × {h}", "n_min": min(n_shear, n_crush), "L_req": L_std,
                   "tau": tau, "p_hub": p_hub, "p_shaft": p_shaft, "F": F, "n_shear": n_shear,
                   "n_crush": n_crush, "l_eff": l_eff},
        "checks": checks,
        "steps": [
            step("Key size (DIN 6885-1)", rf"b \times h = {b} \times {h}\;\text{{mm}},\; t_1 = {t1},\; t_2 = {t2}"),
            step("Effective length", r"l = L - b\;(\text{form A}),\; l = L\;(\text{form B})", l_eff, "length"),
            step("Tangential force", r"F = 2K_A T/d", F, "force"),
            step("Key shear stress", r"\tau = F/(b\,l)", tau, "stress"),
            step("Pressure, hub side", r"p = F/((h - t_1)\,l)", p_hub, "stress"),
            step("Pressure, shaft side", r"p = F/(t_1\,l)", p_shaft, "stress"),
            step("Required length", r"L_{req} = \max\!\left(\tfrac{SF}{b\,\tau_y}, \tfrac{SF}{(h-t_1)S_y}, \tfrac{SF}{t_1 S_y}\right) + b",
                 L_req, "length"),
        ],
        "series": [series("p_vs_L", "Hub surface pressure vs key length", Ls, ps, x_label="L",
                          y_label="p", x_dim="length", y_dim="stress",
                          markers=[{"x": L, "label": "current"}],
                          ref_lines=[{"y": Sy_hub_side / S, "label": f"allowable Sy/{fmt(S, 3)}"}])],
        "tables": [table("DIN 6885-1 key sizes", [
            {"key": "range", "label": "Shaft d", "unit": "mm"}, {"key": "bh", "label": "b × h", "unit": "mm"},
            {"key": "t1", "label": "t1", "unit": "mm"}, {"key": "t2", "label": "t2", "unit": "mm"}],
            rows, highlight={"bh": f"{b} × {h}"})],
        "diagram": {"d": fmt(d_mm, 3), "b": b, "h": h, "t1": t1, "t2": t2,
                    "F": f"{fmt(F / 1000, 3)} kN", "tau": f"{fmt(tau / 1e6, 3)} MPa",
                    "p": f"{fmt(p_hub / 1e6, 3)} MPa", "n": fmt(min(n_shear, n_crush), 3),
                    "ok": all(c["status"] == "ok" for c in checks)},
        "notes": ["Crushing (surface pressure) on the hub side usually governs. Allowables use "
                  "yield strength divided by the safety factor; DIN 6892 gives refined factors."],
    }


PARALLEL_KEY = Calculator(
    id="parallel_key",
    governing=["d", "T", "L_hub"],
    trial=["L"],
    title="Parallel key (DIN 6885)",
    category="Keys & Fits",
    summary="Key size from shaft diameter, shear and surface-pressure check, and required key length.",
    description=(
        "Selects the DIN 6885-1 parallel key for the shaft diameter, then checks key shear and "
        "crushing on the shaft and hub sides for the transmitted torque (times an application "
        "factor). The required length is rounded up to the standard key length series."
    ),
    params=[
        Param("d", "Shaft diameter d", dim="length", default=40, unit="mm", min=6, group="Geometry"),
        Param("L", "Key length L", dim="length", default=40, unit="mm", min=0, group="Geometry"),
        Param("form", "Key form", kind="select", default="A",
              options=[{"value": "A", "label": "Form A (round ends)"},
                       {"value": "B", "label": "Form B (square ends)"}], group="Geometry"),
        Param("L_hub", "Hub length", dim="length", default=50, unit="mm", min=0, group="Geometry"),
        Param("T", "Torque T", dim="torque", default=250, unit="N*m", group="Loads"),
        Param("KA", "Application factor KA", kind="select", default="1.0",
              options=[{"value": k, "label": f"{k} – {v}"} for k, v in APPLICATION.items()],
              group="Loads"),
        Param("S", "Required safety factor", default=2.0, min=1, group="Loads"),
        *material_params("key_material", default="c45_n", label="Key material", group="Materials",
                         need_E=False),
        *material_params("hub_material", default="s355j2", label="Hub material", group="Materials",
                         need_E=False),
        *material_params("shaft_material", default="c45_n", label="Shaft material",
                         group="Materials", need_E=False),
    ],
    outputs=[
        Output("key", "Key b × h (mm)", primary=True),
        Output("n_min", "Minimum safety factor", primary=True, sig=3),
        Output("L_req", "Required standard key length", "length", primary=True, sig=3),
        Output("tau", "Key shear stress τ", "stress"),
        Output("p_hub", "Surface pressure, hub side", "stress"),
        Output("p_shaft", "Surface pressure, shaft side", "stress"),
        Output("F", "Tangential force F", "force"),
        Output("n_shear", "Shear safety factor", sig=3),
        Output("n_crush", "Crushing safety factor", sig=3),
        Output("l_eff", "Effective key length", "length"),
    ],
    compute=_compute_key,
    diagram="parallel_key",
    formulas=[r"F = \frac{2 K_A T}{d}", r"\tau = \frac{F}{b\,l}", r"p = \frac{F}{(h - t_1)\,l}"],
    references=["DIN 6885-1:1968 Parallel keys, deep pattern", "ISO 773:1969",
                "DIN 6892:2012 Calculation of parallel key connections",
                "Shigley's Mechanical Engineering Design, 10th ed., §7-7"],
    keywords=["key", "keyway", "parallel key", "feather key", "din 6885", "hub", "torque transmission",
              "keyseat"],
    presets=[
        {"label": "Motor shaft Ø24, 60 N·m", "values": {"d": {"value": 24, "unit": "mm"},
         "T": {"value": 60, "unit": "N*m"}, "L": {"value": 32, "unit": "mm"},
         "L_hub": {"value": 40, "unit": "mm"}}},
        {"label": "Gearbox output Ø60, 1.2 kN·m", "values": {"d": {"value": 60, "unit": "mm"},
         "T": {"value": 1200, "unit": "N*m"}, "L": {"value": 100, "unit": "mm"},
         "L_hub": {"value": 110, "unit": "mm"}, "KA": "1.25", "hub_material": "42crmo4_qt"}},
    ],
)


# --------------------------------------------------------------------------
# ISO 286 limits and fits
# --------------------------------------------------------------------------

def _um(v: float) -> float:
    return v * 1e-6


def _fit_row(size_mm: float, hole: str, shaft: str) -> Dict[str, Any]:
    f = iso286.fit(size_mm, iso286.parse_class(hole), iso286.parse_class(shaft))
    return {"fit": f"{hole}/{shaft}", "cmax": fmt(f["c_max"], 4), "cmin": fmt(f["c_min"], 4),
            "type": f["type"].replace(" fit", "")}


def _compute_iso_fits(x: Dict[str, Any]) -> Dict[str, Any]:
    size = from_canonical(x["size"], "length", "mm")
    hl, hg = x["hole_letter"], int(x["hole_grade"])
    sl, sg = x["shaft_letter"], int(x["shaft_grade"])
    f = iso286.fit(size, (hl, hg), (sl, sg))
    it_h, it_s = iso286.it_value(size, hg), iso286.it_value(size, sg)
    hole, shaft = f"{hl}{hg}", f"{sl}{sg}"

    rows = [
        {"part": "Hole", "cls": hole, "up": fmt(f["ES"], 4), "lo": fmt(f["EI"], 4),
         "max": f"{size + f['ES'] / 1000:.4f}", "min": f"{size + f['EI'] / 1000:.4f}"},
        {"part": "Shaft", "cls": shaft, "up": fmt(f["es"], 4), "lo": fmt(f["ei"], 4),
         "max": f"{size + f['es'] / 1000:.4f}", "min": f"{size + f['ei'] / 1000:.4f}"},
    ]
    common = [_fit_row(size, "H7", s) for s in ("g6", "h6", "js6", "k6", "n6", "p6", "s6", "u6")]
    current = f"{hole}/{shaft}"

    return {
        "values": {"c_max": _um(f["c_max"]), "c_min": _um(f["c_min"]), "fit_type": f["type"],
                   "ES": _um(f["ES"]), "EI": _um(f["EI"]), "es": _um(f["es"]), "ei": _um(f["ei"]),
                   "it_h": _um(it_h), "it_s": _um(it_s),
                   "c_mean": _um((f["c_max"] + f["c_min"]) / 2)},
        "checks": [],
        "steps": [
            step("Size range (ISO 286-1)", rf"\text{{{iso286.size_range(size)}}}"),
            step(f"Hole tolerance IT{hg}", rf"\mathrm{{IT}}{hg}", _um(it_h), "length", "um"),
            step(f"Shaft tolerance IT{sg}", rf"\mathrm{{IT}}{sg}", _um(it_s), "length", "um"),
            step("Hole limits", r"ES,\;EI = ES - \mathrm{IT}", _um(f["ES"]), "length", "um"),
            step("Shaft limits", r"ei,\;es = ei + \mathrm{IT}", _um(f["es"]), "length", "um"),
            step("Maximum clearance", r"C_{max} = ES - ei", _um(f["c_max"]), "length", "um"),
            step("Minimum clearance", r"C_{min} = EI - es\;(\text{negative = interference})",
                 _um(f["c_min"]), "length", "um"),
        ],
        "series": [],
        "tables": [
            table(f"Limits for Ø{fmt(size, 4)} {current}", [
                {"key": "part", "label": "Part"}, {"key": "cls", "label": "Class"},
                {"key": "up", "label": "Upper dev.", "unit": "µm"},
                {"key": "lo", "label": "Lower dev.", "unit": "µm"},
                {"key": "max", "label": "Max size", "unit": "mm"},
                {"key": "min", "label": "Min size", "unit": "mm"}], rows),
            table(f"Common hole-basis fits at Ø{fmt(size, 4)}", [
                {"key": "fit", "label": "Fit"}, {"key": "cmax", "label": "C max", "unit": "µm"},
                {"key": "cmin", "label": "C min", "unit": "µm"}, {"key": "type", "label": "Type"}],
                common, highlight={"fit": current},
                note="Negative clearance = interference."),
        ],
        "diagram": {"size": fmt(size, 4), "hole": hole, "shaft": shaft, "ES": f["ES"], "EI": f["EI"],
                    "es": f["es"], "ei": f["ei"], "type": f["type"]},
        "notes": ["Deviations from ISO 286-2 (IT3–IT11, sizes to 500 mm). Hole K–S deviations use "
                  "the Δ rule of ISO 286-1."],
    }


ISO_FITS = Calculator(
    id="iso_fits",
    governing=["size", "hole_letter", "shaft_letter"],
    title="ISO 286 limits & fits",
    category="Keys & Fits",
    summary="Hole and shaft limit deviations, clearance or interference and fit type for any ISO 286 fit.",
    description=(
        "Computes the limit deviations of a hole and a shaft from ISO 286 tolerance grades and "
        "fundamental deviations, and classifies the pairing as a clearance, transition or "
        "interference fit."
    ),
    params=[
        Param("size", "Nominal size", dim="length", default=50, unit="mm", min=0, max=500,
              group="Size"),
        Param("hole_letter", "Hole deviation", kind="select", default="H",
              options=[{"value": v, "label": v} for v in iso286.HOLE_LETTERS], group="Hole"),
        Param("hole_grade", "Hole grade (IT)", kind="select", default=7,
              options=[{"value": g, "label": f"IT{g}"} for g in iso286.GRADES], group="Hole"),
        Param("shaft_letter", "Shaft deviation", kind="select", default="g",
              options=[{"value": v, "label": v} for v in iso286.SHAFT_LETTERS], group="Shaft"),
        Param("shaft_grade", "Shaft grade (IT)", kind="select", default=6,
              options=[{"value": g, "label": f"IT{g}"} for g in iso286.GRADES], group="Shaft"),
    ],
    outputs=[
        Output("c_max", "Max clearance (− = interference)", "length", unit="um", primary=True),
        Output("c_min", "Min clearance (− = interference)", "length", unit="um", primary=True),
        Output("fit_type", "Fit type", primary=True),
        Output("ES", "Hole upper deviation ES", "length", unit="um"),
        Output("EI", "Hole lower deviation EI", "length", unit="um"),
        Output("es", "Shaft upper deviation es", "length", unit="um"),
        Output("ei", "Shaft lower deviation ei", "length", unit="um"),
        Output("it_h", "Hole tolerance", "length", unit="um"),
        Output("it_s", "Shaft tolerance", "length", unit="um"),
        Output("c_mean", "Mean clearance", "length", unit="um"),
    ],
    compute=_compute_iso_fits,
    diagram="iso_fits",
    formulas=[r"C_{max} = ES - ei", r"C_{min} = EI - es",
              r"ES = -ei + \Delta,\;\; \Delta = \mathrm{IT}_n - \mathrm{IT}_{n-1}"],
    references=["ISO 286-1:2010 Basis of tolerances, deviations and fits",
                "ISO 286-2:2010 Tables of standard tolerance classes"],
    keywords=["fit", "tolerance", "iso 286", "h7", "g6", "k6", "p6", "clearance", "interference",
              "transition", "limits and fits", "bore", "hole basis"],
    presets=[
        {"label": "H7/g6 sliding", "values": {"hole_letter": "H", "hole_grade": 7,
                                             "shaft_letter": "g", "shaft_grade": 6}},
        {"label": "H7/h6 locating", "values": {"hole_letter": "H", "hole_grade": 7,
                                              "shaft_letter": "h", "shaft_grade": 6}},
        {"label": "H7/k6 transition", "values": {"hole_letter": "H", "hole_grade": 7,
                                                "shaft_letter": "k", "shaft_grade": 6}},
        {"label": "H7/p6 press", "values": {"hole_letter": "H", "hole_grade": 7,
                                           "shaft_letter": "p", "shaft_grade": 6}},
        {"label": "H7/s6 shrink", "values": {"hole_letter": "H", "hole_grade": 7,
                                            "shaft_letter": "s", "shaft_grade": 6}},
    ],
)


# --------------------------------------------------------------------------
# Interference (shrink / press) fit — Lamé thick cylinders
# --------------------------------------------------------------------------

FIT_CHOICES = ["H7/n6", "H7/p6", "H7/r6", "H7/s6", "H7/u6", "H8/u8"]


def _contact_pressure(delta: float, d: float, di: float, D: float, Eh: float, nuh: float,
                      Es: float, nus: float) -> float:
    C = d * ((1 / Eh) * ((D ** 2 + d ** 2) / (D ** 2 - d ** 2) + nuh)
             + (1 / Es) * ((d ** 2 + di ** 2) / (d ** 2 - di ** 2) - nus))
    return delta / C


def _vm2(s1: float, s2: float) -> float:
    return math.sqrt(s1 ** 2 - s1 * s2 + s2 ** 2)


def _compute_interference(x: Dict[str, Any]) -> Dict[str, Any]:
    d, di, D, L = x["d"], x["di"], x["D"], x["L"]
    if d <= 0 or L <= 0:
        raise CalcError("Diameter and length must be positive.")
    if not (0 <= di < d < D):
        raise CalcError("Need 0 ≤ shaft bore < joint diameter < hub outer diameter.")
    hub = resolve_material(x, "hub_material")
    sh = resolve_material(x, "shaft_material")
    mu, loss = x["mu"], x["loss"]
    T_req, S_slip, n_t = abs(x["T_req"]), x["S_slip"], x["n_target"]

    if x["mode"] == "fit":
        hole, shaft = x["fit"].split("/")
        f = iso286.fit(d * 1000, iso286.parse_class(hole), iso286.parse_class(shaft))
        dmax, dmin = -f["c_min"] * 1e-6, -f["c_max"] * 1e-6
        src = f"{x['fit']} at Ø{fmt(d * 1000, 4)} mm: interference {fmt(-f['c_max'], 4)}…{fmt(-f['c_min'], 4)} µm"
    else:
        dmax = dmin = x["delta"]
        src = "Direct interference input"
    dmax_e, dmin_e = dmax - loss, max(dmin - loss, 0.0)
    if dmax_e <= 0:
        raise CalcError("No effective interference: increase the interference or choose a tighter fit.")

    p = lambda dl: _contact_pressure(dl, d, di, D, hub["E"], hub["nu"], sh["E"], sh["nu"])
    p_max, p_min = p(dmax_e), p(dmin_e)

    T_cap = math.pi * mu * p_min * d ** 2 * L / 2
    F_ax = math.pi * mu * p_min * d * L
    F_press = math.pi * mu * p_max * d * L

    st_h = p_max * (D ** 2 + d ** 2) / (D ** 2 - d ** 2)
    vm_h = _vm2(st_h, -p_max)
    st_s = -p_max * (d ** 2 + di ** 2) / (d ** 2 - di ** 2)
    vm_s = _vm2(st_s, -p_max)
    if di > 0:  # hollow shaft: the bore (sigma_r = 0) carries the highest stress, Shigley eq. 3-50 at r = ri
        vm_s = max(vm_s, 2 * p_max * d ** 2 / (d ** 2 - di ** 2))
    n_hub, n_shaft = hub["Sy"] / vm_h, sh["Sy"] / vm_s
    dT = (dmax + 0.001 * d) / (hub["alpha"] * d)

    checks = [
        check("Hub stress", n_hub >= n_t, f"n = {fmt(n_hub, 3)} at maximum interference",
              value=n_hub, limit=n_t),
        check("Shaft stress", n_shaft >= n_t, f"n = {fmt(n_shaft, 3)} at maximum interference",
              value=n_shaft, limit=n_t),
    ]
    if T_req > 0:
        checks.append(check("Torque capacity", T_cap >= S_slip * T_req,
                            f"{fmt(T_cap, 4)} N·m at minimum interference vs {fmt(S_slip, 3)} × "
                            f"{fmt(T_req, 4)} N·m required", value=T_cap, limit=S_slip * T_req))
    if dmin - loss <= 0:
        checks.append(check("Minimum interference", False,
                            "At the loosest tolerance combination there is no interference left: "
                            "torque capacity is zero. Choose a tighter fit.", warn=True))
    if dT > 250:
        checks.append(check("Shrink temperature", False,
                            f"ΔT = {fmt(dT, 3)} K: heating a steel hub this much risks tempering. "
                            "Combine with shaft cooling or use a press fit.", warn=True))

    dl = linspace(0, 1.5 * dmax_e, 50)
    pl = [p(v) for v in dl]
    tl = [math.pi * mu * p(v) * d ** 2 * L / 2 for v in dl]
    marks = [{"x": dmax_e, "label": "max"}]
    if dmin_e != dmax_e:
        marks.append({"x": dmin_e, "label": "min"})

    return {
        "values": {"T_cap": T_cap, "n_hub": n_hub, "p_max": p_max, "p_min": p_min,
                   "n_shaft": n_shaft, "F_ax": F_ax, "F_press": F_press, "vm_hub": vm_h,
                   "vm_shaft": vm_s, "dT": dT, "dmax": dmax_e, "dmin": dmin_e},
        "checks": checks,
        "steps": [
            step("Effective interference (max)", r"\delta_{eff} = \delta - \text{smoothing loss}",
                 dmax_e, "length", "um"),
            step("Contact pressure",
                 r"p = \frac{\delta}{d\left[\frac{1}{E_h}\left(\frac{D^2+d^2}{D^2-d^2} + \nu_h\right) + \frac{1}{E_s}\left(\frac{d^2+d_i^2}{d^2-d_i^2} - \nu_s\right)\right]}",
                 p_max, "stress"),
            step("Hub tangential stress (bore)", r"\sigma_t = p\frac{D^2+d^2}{D^2-d^2}", st_h, "stress"),
            step("Hub von Mises", r"\sigma' = \sqrt{\sigma_t^2 - \sigma_t\sigma_r + \sigma_r^2},\;\sigma_r = -p",
                 vm_h, "stress"),
            step("Torque capacity (min interference)", r"T = \tfrac{\pi}{2}\,\mu\,p\,d^2 L", T_cap, "torque"),
            step("Press-in force (max interference)", r"F = \pi\,\mu\,p\,d\,L", F_press, "force"),
            step("Shrink heating", r"\Delta T = \frac{\delta_{max} + 0.001d}{\alpha_h d}", dT,
                 "temperature_delta"),
        ],
        "series": [
            series("p_vs_delta", "Contact pressure vs interference", dl, pl, x_label="δ",
                   y_label="p", x_dim="length", y_dim="stress", x_unit="um", markers=marks),
            series("t_vs_delta", "Torque capacity vs interference", dl, tl, x_label="δ",
                   y_label="T", x_dim="length", y_dim="torque", x_unit="um", markers=marks,
                   ref_lines=[{"y": S_slip * T_req, "label": "required"}] if T_req > 0 else []),
        ],
        "diagram": {"d": fmt(d * 1000, 4), "D": fmt(D * 1000, 4), "L": fmt(L * 1000, 4),
                    "di": fmt(di * 1000, 4),
                    "p": f"{fmt(p_max / 1e6, 3)} MPa", "T": f"{fmt(T_cap, 4)} N·m",
                    "delta": f"{fmt(dmax_e * 1e6, 3)} µm", "n": fmt(min(n_hub, n_shaft), 3),
                    "ok": all(c["status"] == "ok" for c in checks)},
        "notes": [src, "Assembly clearance for shrink fitting taken as 0.001·d. "
                       "Press-fit friction is often higher than the holding friction; use μ for both "
                       "as a first estimate (DIN 7190 gives refined values)."],
    }


INTERFERENCE_FIT = Calculator(
    id="interference_fit",
    governing=["d", "T_req", "D", "L"],
    trial=["delta", "fit"],
    title="Interference fit (shrink / press)",
    category="Keys & Fits",
    summary="Contact pressure, torque capacity, hub and shaft stresses, press force and shrink "
            "temperature for a shaft–hub interference fit.",
    description=(
        "Thick-walled cylinder (Lamé) solution for a hub shrunk or pressed onto a solid or "
        "hollow shaft. Interference can be entered directly or taken from an ISO 286 fit; the "
        "loosest tolerance combination sets the torque capacity and the tightest one sets the "
        "stresses and the press force."
    ),
    params=[
        Param("d", "Joint diameter d", dim="length", default=40, unit="mm", min=0, group="Geometry"),
        Param("di", "Shaft bore (0 = solid)", dim="length", default=0, unit="mm", min=0, group="Geometry"),
        Param("D", "Hub outer diameter D", dim="length", default=80, unit="mm", min=0, group="Geometry"),
        Param("L", "Joint length L", dim="length", default=40, unit="mm", min=0, group="Geometry"),
        Param("mode", "Interference from", kind="select", default="direct",
              options=[{"value": "direct", "label": "Direct value"},
                       {"value": "fit", "label": "ISO 286 fit"}], group="Interference"),
        Param("delta", "Diametral interference δ", dim="length", default=30, unit="um", min=0,
              group="Interference", show_if={"mode": ["direct"]}),
        Param("fit", "ISO fit", kind="select", default="H7/s6",
              options=[{"value": v, "label": v} for v in FIT_CHOICES], group="Interference",
              show_if={"mode": ["fit"]}),
        Param("loss", "Smoothing loss", dim="length", default=0, unit="um", min=0,
              group="Interference", advanced=True,
              help="DIN 7190: ≈ 0.8·(Rz_shaft + Rz_hub)."),
        Param("mu", "Friction coefficient μ", default=0.15, min=0, group="Friction",
              help="Steel/steel dry ~0.15 (press fit) to ~0.2 (shrink fit)."),
        *material_params("hub_material", default="c45_n", label="Hub material", group="Hub"),
        *material_params("shaft_material", default="c45_qt", label="Shaft material", group="Shaft"),
        Param("T_req", "Torque to transmit", dim="torque", default=300, unit="N*m", group="Requirements"),
        Param("S_slip", "Slip safety factor", default=1.5, min=1, group="Requirements"),
        Param("n_target", "Yield safety factor target", default=1.5, min=1, group="Requirements"),
    ],
    outputs=[
        Output("T_cap", "Torque capacity (min interference)", "torque", primary=True),
        Output("n_hub", "Hub safety factor", primary=True, sig=3),
        Output("p_max", "Contact pressure (max)", "stress", primary=True),
        Output("p_min", "Contact pressure (min)", "stress"),
        Output("n_shaft", "Shaft safety factor", sig=3),
        Output("F_ax", "Axial holding force", "force", unit="kN"),
        Output("F_press", "Press-in force", "force", unit="kN"),
        Output("vm_hub", "Hub von Mises stress", "stress"),
        Output("vm_shaft", "Shaft von Mises stress", "stress"),
        Output("dT", "Hub heating for shrink fit", "temperature_delta", sig=3),
        Output("dmax", "Effective interference (max)", "length", unit="um"),
        Output("dmin", "Effective interference (min)", "length", unit="um"),
    ],
    compute=_compute_interference,
    diagram="interference_fit",
    formulas=[r"p = \frac{\delta}{d\left[\frac{1}{E_h}\left(\frac{D^2+d^2}{D^2-d^2}+\nu_h\right)+\frac{1}{E_s}\left(\frac{d^2+d_i^2}{d^2-d_i^2}-\nu_s\right)\right]}",
              r"T = \frac{\pi}{2}\mu p d^2 L", r"\sigma_{t,hub} = p\frac{D^2+d^2}{D^2-d^2}"],
    references=["Shigley's Mechanical Engineering Design, 10th ed., §3-16 (press and shrink fits)",
                "DIN 7190-1:2017 Interference fits", "ISO 286-2:2010"],
    keywords=["interference fit", "press fit", "shrink fit", "lame", "hub", "contact pressure",
              "torque capacity", "shaft hub connection"],
    presets=[
        {"label": "Gear on shaft, H7/s6", "values": {"mode": "fit", "fit": "H7/s6",
         "d": {"value": 50, "unit": "mm"}, "D": {"value": 100, "unit": "mm"},
         "L": {"value": 50, "unit": "mm"}, "T_req": {"value": 500, "unit": "N*m"}}},
        {"label": "Aluminium hub on steel shaft", "values": {"hub_material": "al_6082_t6",
         "delta": {"value": 25, "unit": "um"}, "T_req": {"value": 150, "unit": "N*m"}}},
    ],
)

CALCULATORS: List[Calculator] = [PARALLEL_KEY, ISO_FITS, INTERFERENCE_FIT]
