"""Shear-loaded joints: EN 1993-1-8 lap joint, thread engagement, eccentric bolt groups."""
import math
from typing import Any, Dict, List

from ..core import Calculator, CalcError, Output, Param, check, fmt, linspace, series, step, table
from . import data
from .common import (CATEGORY, REFS_261, REFS_898, REFS_EC3, REFS_SHIG, REFS_VDI, MPa, class_param,
                     int_param, kN, resolve_strength, resolve_thread, thread_param)

PLATE_FU = {"s235": {"label": "S235 (fu 360 MPa)", "fu": 360},
            "s275": {"label": "S275 (fu 430 MPa)", "fu": 430},
            "s355": {"label": "S355 (fu 490 MPa)", "fu": 490},
            "s460": {"label": "S460 (fu 540 MPa)", "fu": 540}}

HOLE_KS = {"normal": {"label": "Normal clearance (ks 1.0)", "ks": 1.0},
           "oversize": {"label": "Oversize / short slot ⟂ (ks 0.85)", "ks": 0.85},
           "long_slot_perp": {"label": "Long slot ⟂ load (ks 0.70)", "ks": 0.70},
           "long_slot_par": {"label": "Long slot ∥ load (ks 0.63)", "ks": 0.63}}

SLIP_MU = {"A": {"label": "Class A – blasted, no coating (μ 0.5)", "mu": 0.5},
           "B": {"label": "Class B – blasted + Al/Zn spray (μ 0.4)", "mu": 0.4},
           "C": {"label": "Class C – wire-brushed / flame cleaned (μ 0.3)", "mu": 0.3},
           "D": {"label": "Class D – untreated (μ 0.2)", "mu": 0.2}}


def ec3_hole(d: float) -> float:
    """Normal hole diameter d0 per EN 1090-2 (mm)."""
    if d <= 14:
        return d + 1
    if d <= 24:
        return d + 2
    return d + 3


# --------------------------------------------------------------------------
# 4. Shear joint
# --------------------------------------------------------------------------

def _compute_shear(x: Dict[str, Any]) -> Dict[str, Any]:
    th = resolve_thread(x)
    d = th["d"]
    st = resolve_strength(x["cls"], d)
    n = int_param(x, "n_bolts", "Number of bolts", 1, 100)
    m = int(x["planes"])
    t = x["t"] * 1000
    e1, e2 = x["e1"] * 1000, x["e2"] * 1000
    FEd = x["FEd"]
    gM2, gM3 = x["gM2"], x["gM3"]
    fu = PLATE_FU[x["plate"]]["fu"]
    fub = st["Rm"]
    cat = x["category"]
    if t <= 0 or FEd < 0:
        raise CalcError("Plate thickness must be positive and the load non-negative.")
    if st["stainless"]:
        raise CalcError("EN 1993-1-8 covers carbon-steel bolt classes; use EN 1993-1-4 for stainless.")

    d0 = ec3_hole(d)
    in_thread = x["thread_in_plane"]
    A = th["As"] if in_thread else th["AN"]
    av = 0.6 if (not in_thread or x["cls"] in ("4.6", "5.6", "8.8")) else 0.5
    Fv = m * av * fub * A / gM2                               # per bolt (all planes)

    alpha_d = e1 / (3 * d0)
    alpha_b = min(alpha_d, fub / fu, 1.0)
    k1 = min(2.8 * e2 / d0 - 1.7, 2.5)
    if k1 <= 0:
        raise CalcError(f"Edge distance e2 = {fmt(e2, 3)} mm is too small for d0 = {fmt(d0, 3)} mm "
                        f"(EN 1993-1-8 minimum 1.2·d0 = {fmt(1.2 * d0, 3)} mm).")
    Fb = k1 * alpha_b * fu * d * t / gM2                      # per bolt

    preloadable = x["cls"] in ("8.8", "10.9")
    FpC = 0.7 * fub * th["As"]
    ks = HOLE_KS[x["hole"]]["ks"]
    mu = SLIP_MU[x["mu_class"]]["mu"]
    gamma_slip = 1.1 if cat == "slip_sls" else gM3
    Fs = ks * m * mu * FpC / gamma_slip if preloadable else 0.0

    if cat == "bearing":
        per_bolt = min(Fv, Fb)
        mode = "bolt shear" if Fv <= Fb else "plate bearing"
    else:
        if not preloadable:
            raise CalcError("Slip-resistant joints need preloaded class 8.8 or 10.9 bolts.")
        per_bolt = Fs
        mode = "slip"
    resistance = n * per_bolt
    util = FEd / resistance if resistance > 0 else float("inf")

    checks = [check("Design resistance", util <= 1.0,
                    f"FEd = {kN(FEd)} vs FRd = {kN(resistance)} (utilisation {fmt(100 * util, 3)} %, "
                    f"governed by {mode}).", value=util, limit=1.0)]
    if cat != "bearing":
        bearing_ok = FEd <= n * min(Fv, Fb)
        checks.append(check("Ultimate shear / bearing", bearing_ok,
                            f"Even when slip occurs the joint must carry FEd in bearing: "
                            f"{kN(n * min(Fv, Fb))} available."))
    if e1 < 1.2 * d0 or e2 < 1.2 * d0:
        checks.append(check("Edge distances", False,
                            f"EN 1993-1-8 minimum is 1.2·d0 = {fmt(1.2 * d0, 3)} mm (e1 = {fmt(e1, 3)}, e2 = {fmt(e2, 3)})."))
    elif e1 < 3 * d0:
        checks.append(check("End distance", False,
                            f"e1 = {fmt(e1, 3)} mm < 3·d0 limits bearing (αb = {fmt(alpha_b, 3)}). "
                            f"Use e1 ≥ {fmt(3 * d0, 3)} mm for full bearing capacity.", warn=True))
    if x["cls"] == "12.9":
        checks.append(check("Bolt class", False, "Class 12.9 is outside EN 1993-1-8; treat as 10.9 or "
                            "use product-specific data.", warn=True))

    rows = [
        {"mode": "Bolt shear (per bolt)", "value": kN(Fv), "total": kN(n * Fv)},
        {"mode": "Plate bearing (per bolt)", "value": kN(Fb), "total": kN(n * Fb)},
    ]
    if preloadable:
        rows.append({"mode": f"Slip ({'SLS γ 1.1' if cat == 'slip_sls' else 'ULS γM3'})",
                     "value": kN(Fs), "total": kN(n * Fs)})

    return {
        "values": {"FRd": resistance, "util": util, "mode": mode, "Fv": Fv, "Fb": Fb,
                   "Fs": Fs if preloadable else None, "FpC": FpC if preloadable else None,
                   "d0": d0 / 1000, "alpha_b": alpha_b, "k1": k1},
        "checks": checks,
        "steps": [
            step("Hole diameter (EN 1090-2)", r"d_0", d0 / 1000, "length"),
            step("Shear resistance per bolt", r"F_{v,Rd} = m\,\frac{\alpha_v f_{ub} A}{\gamma_{M2}}", Fv, "force", "kN"),
            step("Bearing factor", r"\alpha_b = \min\left(\tfrac{e_1}{3d_0},\, \tfrac{f_{ub}}{f_u},\, 1\right)", alpha_b, sig=3),
            step("Edge factor", r"k_1 = \min\left(2.8\tfrac{e_2}{d_0} - 1.7,\, 2.5\right)", k1, sig=3),
            step("Bearing resistance per bolt", r"F_{b,Rd} = \frac{k_1 \alpha_b f_u\, d\, t}{\gamma_{M2}}", Fb, "force", "kN"),
            step("Slip resistance per bolt", r"F_{s,Rd} = \frac{k_s\, m\, \mu\, F_{p,C}}{\gamma_{M3}},\; F_{p,C} = 0.7 f_{ub} A_s",
                 Fs, "force", "kN"),
            step("Joint resistance", r"F_{Rd} = n \cdot F_{Rd,bolt}", resistance, "force", "kN"),
        ],
        "tables": [table("Resistances", [{"key": "mode", "label": "Mode"},
                                         {"key": "value", "label": "Per bolt"},
                                         {"key": "total", "label": f"× {n} bolts"}], rows,
                         note="Long-joint reduction βLf and block tearing are not included.")],
        "diagram": {"n": n, "planes": m, "d": d, "t": fmt(t, 3), "e1": fmt(e1, 3), "e2": fmt(e2, 3),
                    "F": kN(FEd), "util": f"{fmt(100 * util, 3)} %", "ok": util <= 1.0,
                    "designation": th["designation"], "cls": x["cls"], "mode": mode},
        "notes": ["Bearing check uses end/edge bolt factors for all bolts (conservative)."],
    }


BOLT_SHEAR_JOINT = Calculator(
    id="bolt_shear_joint",
    governing=["FEd", "thread", "n_bolts", "t"],
    title="Bolted lap joint in shear (EN 1993-1-8)",
    category=CATEGORY,
    summary="Bearing-type or slip-resistant (friction-grip) shear joint: bolt shear, plate bearing and slip resistance with edge-distance checks.",
    description=(
        "Eurocode 3 resistances for bolts loaded perpendicular to their axis. Category A relies on "
        "bolt shear and plate bearing; categories B/C rely on friction from preloaded 8.8/10.9 bolts "
        "and must also survive in bearing once slip occurs."
    ),
    params=[
        thread_param("M16", coarse_only=True),
        class_param("8.8", steel_only=True),
        Param("n_bolts", "Number of bolts", default=4, min=1, group="Joint"),
        Param("planes", "Shear planes per bolt", kind="select", default="1", group="Joint",
              options=[{"value": "1", "label": "1 (single lap)"}, {"value": "2", "label": "2 (double lap / splice)"}]),
        Param("thread_in_plane", "Thread in the shear plane", kind="bool", default=True, group="Joint"),
        Param("t", "Thinnest plate thickness t", dim="length", default=12, unit="mm", min=0, group="Plates"),
        Param("plate", "Plate steel", kind="select", default="s355", group="Plates",
              options=[{"value": k, "label": v["label"]} for k, v in PLATE_FU.items()]),
        Param("e1", "End distance e1 (load direction)", dim="length", default=55, unit="mm", group="Plates"),
        Param("e2", "Edge distance e2 (⟂ load)", dim="length", default=30, unit="mm", group="Plates"),
        Param("FEd", "Design shear load FEd (total)", dim="force", default=150, unit="kN", min=0, group="Loads"),
        Param("category", "Joint category", kind="select", default="bearing", group="Design",
              options=[{"value": "bearing", "label": "A – bearing type"},
                       {"value": "slip_sls", "label": "B – slip-resistant at SLS"},
                       {"value": "slip_uls", "label": "C – slip-resistant at ULS"}]),
        Param("mu_class", "Faying surface class", kind="select", default="B", group="Design",
              options=[{"value": k, "label": v["label"]} for k, v in SLIP_MU.items()],
              show_if={"category": ["slip_sls", "slip_uls"]}),
        Param("hole", "Hole type", kind="select", default="normal", group="Design",
              options=[{"value": k, "label": v["label"]} for k, v in HOLE_KS.items()],
              show_if={"category": ["slip_sls", "slip_uls"]}),
        Param("gM2", "γM2", default=1.25, min=1, group="Design", advanced=True),
        Param("gM3", "γM3 (slip ULS)", default=1.25, min=1, group="Design", advanced=True),
    ],
    outputs=[
        Output("FRd", "Joint resistance FRd", "force", unit="kN", primary=True, sig=3),
        Output("util", "Utilisation FEd/FRd", primary=True, sig=3),
        Output("mode", "Governing mode", primary=True),
        Output("Fv", "Shear resistance / bolt", "force", unit="kN"),
        Output("Fb", "Bearing resistance / bolt", "force", unit="kN"),
        Output("Fs", "Slip resistance / bolt", "force", unit="kN"),
        Output("FpC", "Preload Fp,C", "force", unit="kN"),
        Output("d0", "Hole diameter d0", "length"),
        Output("alpha_b", "Bearing factor αb", sig=3),
        Output("k1", "Edge factor k1", sig=3),
    ],
    compute=_compute_shear,
    diagram="bolt_shear_joint",
    formulas=[r"F_{v,Rd} = \frac{\alpha_v f_{ub} A}{\gamma_{M2}}",
              r"F_{b,Rd} = \frac{k_1 \alpha_b f_u d t}{\gamma_{M2}}",
              r"F_{s,Rd} = \frac{k_s n \mu}{\gamma_{M3}} F_{p,C}"],
    references=[REFS_EC3, "EN 1090-2 Execution of steel structures (hole sizes)", REFS_898],
    keywords=["shear joint", "lap joint", "bolt shear", "bearing", "slip resistant", "friction grip",
              "eurocode 3", "steel connection", "splice", "bracket bolts"],
    presets=[
        {"label": "Double splice, 10.9 friction grip", "values": {
            "planes": "2", "cls": "10.9", "category": "slip_uls", "thread": "M20",
            "FEd": {"value": 400, "unit": "kN"}, "n_bolts": 4, "e1": {"value": 70, "unit": "mm"},
            "e2": {"value": 40, "unit": "mm"}, "t": {"value": 15, "unit": "mm"}}},
        {"label": "Small bracket, 2× M12", "values": {
            "thread": "M12", "n_bolts": 2, "t": {"value": 8, "unit": "mm"},
            "FEd": {"value": 40, "unit": "kN"}, "e1": {"value": 25, "unit": "mm"},
            "e2": {"value": 20, "unit": "mm"}}},
    ],
)


# --------------------------------------------------------------------------
# 5. Thread engagement length
# --------------------------------------------------------------------------

def _engagement_capacity(th: Dict[str, float], tau_int: float, tau_bolt: float, factor: float):
    """Stripping force per mm of engagement (N/mm) for internal and external thread."""
    a_int = math.pi * th["d"] * 0.875        # internal thread shears at major dia d
    a_ext = math.pi * th["D1"] * 0.75        # bolt thread shears at nut minor dia D1
    return factor * tau_int * a_int, factor * tau_bolt * a_ext


def _compute_engagement(x: Dict[str, Any]) -> Dict[str, Any]:
    th = resolve_thread(x)
    d = th["d"]
    st = resolve_strength(x["cls"], d)
    mat = data.TAPPED_MATERIALS[x["material"]]
    LE = x["LE"] * 1000
    factor, sf = x["factor"], x["sf"]
    if not 0.5 <= factor <= 1.0:
        raise CalcError("Strength reduction factor must be between 0.5 and 1.0.")
    if sf <= 0 or LE < 0:
        raise CalcError("Safety factor must be positive and engagement length non-negative.")

    F_bolt = st["Rm"] * th["As"]
    tau_bolt = 0.6 * st["Rm"]
    q_int, q_ext = _engagement_capacity(th, mat["tau"], tau_bolt, factor)
    L_int = sf * F_bolt / q_int
    L_ext = sf * F_bolt / q_ext
    L_req = max(L_int, L_ext)
    governs = f"internal thread in {mat['label']}" if L_int >= L_ext else "bolt thread"
    F_strip = min(q_int, q_ext) * LE
    margin = F_strip / F_bolt if F_bolt else 0.0

    rows = []
    for key, m in data.TAPPED_MATERIALS.items():
        qi, qe = _engagement_capacity(th, m["tau"], tau_bolt, factor)
        Lr = sf * F_bolt / min(qi, qe)
        rows.append({"material": m["label"], "rule": m["rule"], "L": fmt(Lr, 3), "Ld": fmt(Lr / d, 3)})

    Ls = linspace(0.2 * d, max(2.5 * d, 1.3 * L_req, 1.2 * LE), 40)
    Fs = [min(q_int, q_ext) * L for L in Ls]
    checks = [check("Engagement length", LE >= L_req,
                    f"LE = {fmt(LE, 3)} mm vs required {fmt(L_req, 3)} mm ({fmt(L_req / d, 3)}·d). "
                    + ("The bolt breaks before the thread strips." if LE >= L_req else
                       "The thread would strip before the bolt breaks: deepen the hole, use a thread "
                       "insert (e.g. helical coil) or a lower bolt class."),
                    value=LE, limit=L_req)]
    if x["material"].startswith("al") and LE < 1.5 * d:
        checks.append(check("Aluminium threads", False, "Less than 1.5·d in aluminium: consider a "
                            "steel thread insert for repeated assembly.", warn=True))

    return {
        "values": {"L_req": L_req / 1000, "ratio": L_req / d, "margin": margin, "F_bolt": F_bolt,
                   "F_strip": F_strip, "L_int": L_int / 1000, "L_ext": L_ext / 1000,
                   "governs": governs},
        "checks": checks,
        "steps": [
            step("Bolt breaking force", r"F_B = R_m A_s", F_bolt, "force", "kN"),
            step("Internal thread shear area / mm", r"a_n = \pi d\left[\tfrac{1}{2} + 0.577\tfrac{d - d_2}{P}\right] = 0.875\,\pi d",
                 math.pi * d * 0.875 * 1e-6, "area"),
            step("External thread shear area / mm", r"a_s = \pi D_1\left[\tfrac{1}{2} + 0.577\tfrac{d_2 - D_1}{P}\right] = 0.75\,\pi D_1",
                 math.pi * th["D1"] * 0.75 * 1e-6, "area"),
            step("Length for internal thread", r"L_n = \frac{S\,F_B}{C\,\tau_{B,n}\,a_n}", L_int / 1000, "length"),
            step("Length for bolt thread", r"L_s = \frac{S\,F_B}{C\,\tau_{B,s}\,a_s}", L_ext / 1000, "length"),
            step("Required engagement", r"L_{req} = \max(L_n, L_s)", L_req / 1000, "length"),
        ],
        "series": [series("strip", "Stripping force vs engagement", [L / 1000 for L in Ls], Fs,
                          x_label="LE", y_label="F", x_dim="length", y_dim="force", y_unit="kN",
                          markers=[{"x": L_req / 1000, "label": "required"}, {"x": LE / 1000, "label": "actual"}],
                          ref_lines=[{"y": F_bolt, "label": "bolt breaks"}])],
        "tables": [table(f"Required engagement for {th['designation']} {x['cls']} by material",
                         [{"key": "material", "label": "Tapped material"},
                          {"key": "rule", "label": "Rule of thumb"},
                          {"key": "L", "label": "Calculated", "unit": "mm"},
                          {"key": "Ld", "label": "L / d"}], rows,
                         highlight={"material": mat["label"]})],
        "diagram": {"designation": th["designation"], "d": d, "LE": fmt(LE, 3), "L_req": fmt(L_req, 3),
                    "material": mat["label"], "ok": LE >= L_req, "tap": th["tap"]},
        "notes": ["The required length is the theoretical minimum where thread stripping and bolt "
                  "fracture balance (at the safety factor S entered). Design practice adds margin for "
                  "thread tolerances, repeated assembly and fatigue: about 1.0–1.25·d in steel, "
                  "1.5–2·d in aluminium and brass, 2–2.5·d in cast iron and cast aluminium "
                  "(see the rule-of-thumb column).",
                  "Basic-profile shear areas with a strength reduction factor C for tolerances and nut "
                  "dilation; for VDI 2230-level accuracy use its meff method."],
    }


THREAD_ENGAGEMENT = Calculator(
    id="thread_engagement",
    governing=["thread"],
    trial=["LE"],
    title="Minimum thread engagement length",
    category=CATEGORY,
    summary="Required depth of thread engagement so a tapped hole (steel, aluminium, cast iron, brass) does not strip before the bolt breaks.",
    description=(
        "Compares the shear strength of the internal thread (in the tapped part) and of the bolt "
        "thread with the bolt's breaking force, and returns the engagement length at which the bolt "
        "fails first — the usual design goal."
    ),
    params=[
        thread_param("M8"),
        class_param("8.8"),
        Param("material", "Tapped part material", kind="select", default="al6082",
              options=data.TAPPED_OPTIONS, group="Tapped hole"),
        Param("LE", "Actual engagement length LE", dim="length", default=16, unit="mm", min=0,
              group="Tapped hole"),
        Param("sf", "Safety factor on bolt breaking force", default=1.0, min=0.5, group="Design",
              advanced=True),
        Param("factor", "Strength reduction C (tolerances, dilation)", default=0.8, min=0.5, max=1.0,
              group="Design", advanced=True),
    ],
    outputs=[
        Output("L_req", "Minimum engagement (theoretical)", "length", primary=True, sig=3),
        Output("ratio", "Required L / d", primary=True, sig=3),
        Output("margin", "Strip force / bolt break force", primary=True, sig=3),
        Output("governs", "Strips first"),
        Output("F_bolt", "Bolt breaking force", "force", unit="kN"),
        Output("F_strip", "Stripping force at LE", "force", unit="kN"),
        Output("L_int", "Length for internal thread", "length"),
        Output("L_ext", "Length for bolt thread", "length"),
    ],
    compute=_compute_engagement,
    diagram="thread_engagement",
    formulas=[r"A_n = \pi\,d\,L_E\left[\tfrac{1}{2} + 0.577\,\tfrac{d - d_2}{P}\right]",
              r"L_{req} = \frac{R_m A_s}{C\,\tau_B\,a}"],
    references=["Machinery's Handbook, 31st ed. — thread stripping areas", REFS_VDI, REFS_261],
    keywords=["thread engagement", "tapped hole depth", "thread stripping", "aluminium thread",
              "helicoil", "thread insert", "cast iron thread", "how deep to tap"],
    presets=[
        {"label": "M10 10.9 into cast iron", "values": {"thread": "M10", "cls": "10.9",
                                                        "material": "gjl250", "LE": {"value": 15, "unit": "mm"}}},
        {"label": "M6 12.9 into cast aluminium", "values": {"thread": "M6", "cls": "12.9",
                                                            "material": "al_cast", "LE": {"value": 12, "unit": "mm"}}},
    ],
)


# --------------------------------------------------------------------------
# 6. Eccentrically loaded bolt group (elastic method)
# --------------------------------------------------------------------------

def bolt_pattern(x: Dict[str, Any]) -> List[Dict[str, float]]:
    if x["pattern"] == "grid":
        rows = int_param(x, "rows", "Rows", 1, 20)
        cols = int_param(x, "cols", "Columns", 1, 20)
        if rows * cols < 2:
            raise CalcError("A bolt group needs at least two bolts.")
        px, py = x["px"] * 1000, x["py"] * 1000
        if (cols > 1 and px <= 0) or (rows > 1 and py <= 0):
            raise CalcError("Bolt pitches must be positive.")
        pts = []
        for r in range(rows):
            for c in range(cols):
                pts.append({"x": (c - (cols - 1) / 2) * px, "y": ((rows - 1) / 2 - r) * py})
        return pts
    n = int_param(x, "n_circle", "Bolts on circle", 2, 72)
    R = x["radius"] * 1000
    if R <= 0:
        raise CalcError("Pitch-circle radius must be positive.")
    return [{"x": R * math.cos(2 * math.pi * i / n + math.pi / 2),
             "y": R * math.sin(2 * math.pi * i / n + math.pi / 2)} for i in range(n)]


def _compute_group(x: Dict[str, Any]) -> Dict[str, Any]:
    pts = bolt_pattern(x)
    th = resolve_thread(x)
    st = resolve_strength(x["cls"], th["d"])
    F, Fx, e = x["F"], x["Fx"], x["e"] * 1000
    gamma = x["gamma"]
    n = len(pts)
    Ip = sum(p["x"] ** 2 + p["y"] ** 2 for p in pts)
    if Ip <= 0:
        raise CalcError("Bolts must not all sit at the centroid.")
    M = F * e                                      # N·mm, clockwise (load downward at +e)
    A = th["As"] if x["thread_in_plane"] else th["AN"]
    capacity = 0.6 * st["Rm"] * A / gamma         # per bolt, N

    bolts, Rmax, crit = [], 0.0, 0
    for i, p in enumerate(pts):
        dx, dy = Fx / n, -F / n
        tx, ty = M / Ip * p["y"], -M / Ip * p["x"]
        fx, fy = dx + tx, dy + ty
        R = math.hypot(fx, fy)
        bolts.append({"i": i + 1, "x": p["x"], "y": p["y"], "fx": fx, "fy": fy, "R": R,
                      "direct": math.hypot(dx, dy), "tors": math.hypot(tx, ty)})
        if R > Rmax:
            Rmax, crit = R, i
    util = Rmax / capacity

    rows = [{"bolt": b["i"], "x": fmt(b["x"], 3), "y": fmt(b["y"], 3),
             "direct": fmt(b["direct"] / 1000, 3), "tors": fmt(b["tors"] / 1000, 3),
             "R": fmt(b["R"] / 1000, 3), "util": fmt(100 * b["R"] / capacity, 3),
             "_status": "fail" if b["R"] > capacity else ("warn" if b["i"] == crit + 1 else "ok")}
            for b in bolts]
    checks = [check("Critical bolt shear", util <= 1.0,
                    f"Bolt {crit + 1} carries {kN(Rmax)} vs capacity {kN(capacity)} "
                    f"(0.6·Rm·A/γ, utilisation {fmt(100 * util, 3)} %).", value=util, limit=1.0)]
    notes = ["Elastic (vector) method: direct shear shared equally, torsional shear proportional to "
             "distance from the centroid. It is conservative compared with the instantaneous-centre method."]
    if Fx:
        notes.append("Horizontal load Fx is assumed to act through the group centroid.")

    return {
        "values": {"Rmax": Rmax, "crit": f"Bolt {crit + 1}", "util": util, "M": M / 1000,
                   "Ip": Ip * 1e-6, "direct": math.hypot(Fx, F) / n, "capacity": capacity, "n": n},
        "checks": checks,
        "steps": [
            step("Moment about the centroid", r"M = F\,e", M / 1000, "torque"),
            step("Polar moment of the group", r"\textstyle\sum r_i^2 = \sum (x_i^2 + y_i^2)", Ip * 1e-6, "area"),
            step("Direct shear per bolt", r"F_d = F/n", math.hypot(Fx, F) / n, "force", "kN"),
            step("Torsional shear, critical bolt", r"F_t = \frac{M\,r_i}{\sum r^2}",
                 bolts[crit]["tors"], "force", "kN"),
            step("Resultant, critical bolt", r"R = |\vec F_d + \vec F_t|", Rmax, "force", "kN"),
        ],
        "tables": [table("Bolt forces", [{"key": "bolt", "label": "#"}, {"key": "x", "label": "x", "unit": "mm"},
                                         {"key": "y", "label": "y", "unit": "mm"},
                                         {"key": "direct", "label": "Direct", "unit": "kN"},
                                         {"key": "tors", "label": "Torsional", "unit": "kN"},
                                         {"key": "R", "label": "Resultant", "unit": "kN"},
                                         {"key": "util", "label": "Utilisation", "unit": "%"}], rows,
                         highlight={"bolt": crit + 1})],
        "diagram": {"bolts": [{"x": b["x"], "y": b["y"], "fx": b["fx"], "fy": b["fy"], "R": b["R"]}
                              for b in bolts],
                    "crit": crit, "e": e, "F": kN(F), "Rmax": kN(Rmax), "ok": util <= 1.0,
                    "pattern": x["pattern"]},
        "notes": notes,
    }


BOLT_GROUP_ECCENTRIC = Calculator(
    id="bolt_group_eccentric",
    governing=["F", "Fx", "e", "thread", "rows", "cols", "px", "py", "n_circle", "radius"],
    title="Bolt group under eccentric shear",
    category=CATEGORY,
    summary="Forces in each bolt of a rectangular or circular pattern loaded off-centre (bracket, console), critical bolt and utilisation.",
    description=(
        "A load applied away from the centroid of a bolt group creates direct shear plus a twisting "
        "moment. The elastic method distributes the moment to the bolts in proportion to their "
        "distance from the centroid; the bolt farthest out on the loaded side is critical."
    ),
    params=[
        Param("pattern", "Bolt pattern", kind="select", default="grid", group="Pattern",
              options=[{"value": "grid", "label": "Rectangular grid"},
                       {"value": "circle", "label": "Circular (pitch circle)"}]),
        Param("rows", "Rows", default=3, min=1, group="Pattern", show_if={"pattern": ["grid"]}),
        Param("cols", "Columns", default=2, min=1, group="Pattern", show_if={"pattern": ["grid"]}),
        Param("px", "Column pitch (x)", dim="length", default=80, unit="mm", group="Pattern",
              show_if={"pattern": ["grid"]}),
        Param("py", "Row pitch (y)", dim="length", default=70, unit="mm", group="Pattern",
              show_if={"pattern": ["grid"]}),
        Param("n_circle", "Bolts on circle", default=6, min=2, group="Pattern",
              show_if={"pattern": ["circle"]}),
        Param("radius", "Pitch-circle radius", dim="length", default=60, unit="mm", group="Pattern",
              show_if={"pattern": ["circle"]}),
        Param("F", "Vertical load F", dim="force", default=20, unit="kN", group="Loads"),
        Param("e", "Eccentricity e (from centroid)", dim="length", default=200, unit="mm", group="Loads"),
        Param("Fx", "Horizontal load Fx (through centroid)", dim="force", default=0, unit="kN",
              group="Loads", advanced=True),
        thread_param("M16", group="Bolts"),
        class_param("8.8", group="Bolts"),
        Param("thread_in_plane", "Thread in the shear plane", kind="bool", default=True, group="Bolts"),
        Param("gamma", "Partial safety factor γ", default=1.25, min=1, group="Bolts", advanced=True),
    ],
    outputs=[
        Output("Rmax", "Critical bolt force", "force", unit="kN", primary=True, sig=3),
        Output("util", "Utilisation", primary=True, sig=3),
        Output("crit", "Critical bolt", primary=True),
        Output("M", "Moment F·e", "torque"),
        Output("direct", "Direct shear per bolt", "force", unit="kN"),
        Output("Ip", "Σ r²", "area"),
        Output("capacity", "Shear capacity per bolt", "force", unit="kN"),
        Output("n", "Number of bolts", sig=3),
    ],
    compute=_compute_group,
    diagram="bolt_group",
    formulas=[r"F_{t,i} = \frac{M\,r_i}{\sum r_j^2}", r"\vec R_i = \frac{\vec F}{n} + \vec F_{t,i}"],
    references=[REFS_SHIG + " §8-12 (shear joints)", REFS_EC3, REFS_898],
    keywords=["bolt group", "eccentric load", "bolt pattern", "bracket", "console", "pitch circle",
              "flange bolts shear", "torsion on bolts", "critical bolt"],
    presets=[
        {"label": "Console bracket, 6 bolts", "values": {"pattern": "grid", "rows": 3, "cols": 2,
                                                         "F": {"value": 30, "unit": "kN"},
                                                         "e": {"value": 250, "unit": "mm"}}},
        {"label": "Flange, 8 bolts on PCD 160", "values": {"pattern": "circle", "n_circle": 8,
                                                           "radius": {"value": 80, "unit": "mm"},
                                                           "e": {"value": 120, "unit": "mm"},
                                                           "thread": "M12"}},
    ],
)
