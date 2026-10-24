"""'Which bolt?' — select the smallest standard size and class for a load."""
import math
from typing import Any, Dict, List, Optional

from ..core import Calculator, CalcError, Output, Param, check, fmt, step, table
from . import data
from .common import (CATEGORY, REFS_898, REFS_SHIG, REFS_VDI, friction_params, head_geometry,
                     head_param, kN, method_param, resolve_friction, torsion_section_modulus)

CLASS_PREFS = {
    "any": ["8.8", "10.9", "12.9"],
    "8.8": ["8.8"],
    "10.9": ["10.9"],
    "12.9": ["12.9"],
    "A2-70": ["A2-70"],
    "A4-70": ["A4-70"],
    "A4-80": ["A4-80"],
}
CLASS_PREF_OPTIONS = [
    {"value": "any", "label": "Any steel class (8.8 → 12.9)"},
    {"value": "8.8", "label": "8.8 only"},
    {"value": "10.9", "label": "10.9 only"},
    {"value": "12.9", "label": "12.9 only"},
    {"value": "A2-70", "label": "Stainless A2-70"},
    {"value": "A4-70", "label": "Stainless A4-70"},
    {"value": "A4-80", "label": "Stainless A4-80"},
]
SELECTABLE = ["M3", "M4", "M5", "M6", "M8", "M10", "M12", "M14", "M16", "M18", "M20", "M22",
              "M24", "M27", "M30", "M33", "M36"]
EMBED_FRACTION = 0.05     # ≈ 5 % preload lost to embedding (typical, VDI 2230 Table 5)
MIN_CLAMP_FRACTION = 0.2  # residual clamp kept ≥ 20 % of the design axial load


def evaluate(size: str, cls: str, x: Dict[str, Any], fr: Dict[str, float], alpha: float,
             FA: float, FK_needed: float, phi: float) -> Optional[Dict[str, Any]]:
    th = data.thread(size)
    try:
        st = data.strength(cls, th["d"])
    except ValueError:
        return None
    if data.head(x["head"], size) is None:
        return None
    geo = head_geometry(x["head"], size)
    FM = data.assembly_preload(th, st["Rp"], fr["muG"], 0.9)
    FMmin = FM / alpha
    FZ = EMBED_FRACTION * FM
    FKR = FMmin - (1 - phi) * FA - FZ
    MG = FM * data.thread_torque_factor(th, fr["muG"])
    tau = 0.5 * MG / torsion_section_modulus(th["ds"])
    sig = (FM + phi * FA) / th["As"]
    util = math.sqrt(sig ** 2 + 3 * tau ** 2) / st["Rp"]
    MA = data.tightening_torque(FM, th, fr["muG"], fr["muK"], geo["DKm"]) / 1000
    ok = FKR > 0 and FKR >= FK_needed and util <= 1.0

    lK = x["lK"] * 1000
    jt = x["joint_type"]
    if jt == "through":
        nut, washer = data.NUT[size], data.WASHER[size]
        L_need = lK + washer["h"] + nut["m"] + 2 * th["P"]
        extras = f" + nut ISO 4032 {size} + washer ISO 7089 {size}"
    else:
        engage = 1.0 if jt == "tapped_steel" else 2.0
        L_need = lK + engage * th["d"]
        extras = f" (tap ≥ {fmt(engage * th['d'] + 2 * th['P'], 3)} mm deep)"
    L = data.stock_length(L_need)
    desig = (f"{data.HEAD_STD[x['head']]} {size}×{L} – {cls}" if L else
             f"{data.HEAD_STD[x['head']]} {size} – {cls} (special length {fmt(L_need, 3)} mm)")
    return {"size": size, "cls": cls, "d": th["d"], "As": th["As"], "FM": FM, "FMmin": FMmin,
            "FKR": FKR, "util": util, "MA": MA, "L": L, "L_need": L_need, "ok": ok,
            "designation": desig + extras}


def _compute_selector(x: Dict[str, Any]) -> Dict[str, Any]:
    FA, FQ, muT, sf, phi = x["FA"], x["FQ"], x["muT"], x["sf"], x["phi"]
    if FA < 0 or FQ < 0:
        raise CalcError("Loads must be non-negative.")
    if FA == 0 and FQ == 0:
        raise CalcError("Enter an axial and/or transverse load per bolt.")
    if muT <= 0 or sf < 1 or not 0.05 <= phi <= 1:
        raise CalcError("Check interface friction (>0), safety factor (≥1) and load factor (0.05–1).")
    if x["lK"] <= 0:
        raise CalcError("Clamp length must be positive.")
    fr = resolve_friction(x)
    alpha = data.TIGHTENING[x["method"]]["alpha"]
    FA_design = sf * FA
    # Clamp needed for friction transfer, but never less than 20 % of the axial load so the
    # joint keeps a real margin against opening.
    FK_needed = max(sf * FQ / muT, MIN_CLAMP_FRACTION * FA_design)

    classes = CLASS_PREFS[x["pref"]]
    limited_for_al = False
    if x["joint_type"] == "tapped_al":
        allowed = [c for c in classes if c not in ("10.9", "12.9")]
        limited_for_al = len(allowed) < len(classes)
        classes = allowed or ["8.8"]

    per_size: List[Dict[str, Any]] = []
    for size in SELECTABLE:
        cands = [evaluate(size, c, x, fr, alpha, FA_design, FK_needed, phi) for c in classes]
        cands = [c for c in cands if c]
        if not cands:
            continue
        good = [c for c in cands if c["ok"]]
        per_size.append(good[0] if good else cands[-1])
    if not per_size:
        raise CalcError("No standard size is available for this head type and class.")

    best_idx = next((i for i, r in enumerate(per_size) if r["ok"]), None)
    lo = max(0, (best_idx if best_idx is not None else len(per_size)) - 2)
    shown = per_size[lo:(best_idx + 4 if best_idx is not None else len(per_size))]
    best = per_size[best_idx] if best_idx is not None else None

    rows = [{"size": r["size"], "cls": r["cls"], "As": fmt(r["As"], 3),
             "FM": fmt(r["FM"] / 1000, 3), "FMmin": fmt(r["FMmin"] / 1000, 3),
             "MA": fmt(r["MA"], 3), "FKR": fmt(r["FKR"] / 1000, 3),
             "util": fmt(100 * r["util"], 3), "L": r["L"] or "special",
             "_status": "ok" if r["ok"] else "fail"} for r in shown]

    checks = []
    if best:
        checks.append(check("Adequate bolt found", True,
                            f"{best['size']} {best['cls']} keeps {kN(best['FKR'])} clamp "
                            f"(need {kN(FK_needed)}) at {fmt(100 * best['util'], 3)} % of yield."))
    else:
        checks.append(check("Adequate bolt found", False,
                            "No size up to M36 works with this tightening method — use more bolts, a more "
                            "accurate tightening method, or reduce the load per bolt."))
    if FQ > 0:
        checks.append(check("Transverse load by friction", True,
                            f"Transverse load is carried by clamp friction (μT = {fmt(muT, 2)}): required "
                            f"clamp {kN(FK_needed)}. Do not rely on bolt shear in machine joints.", warn=False))
    if limited_for_al:
        checks.append(check("Class limited for aluminium", True,
                            "10.9/12.9 bolts strip typical aluminium threads before reaching their preload, "
                            "so only 8.8 is considered. Use steel thread inserts to go higher.", warn=False))
    notes = ["Static selection. Run the bolted-joint calculator on the chosen size for fatigue, surface "
             "pressure and an exact load factor.",
             f"Assumes load factor Φn = {fmt(phi, 2)}, ≈ {int(EMBED_FRACTION * 100)} % embedding loss and a "
             f"residual clamp of at least {int(MIN_CLAMP_FRACTION * 100)} % of the design axial load."]

    vals = {"recommended": best["designation"] if best else "None up to M36",
            "MA": best["MA"] if best else None, "FMmin": best["FMmin"] if best else None,
            "FKR": best["FKR"] if best else None, "util": best["util"] if best else None,
            "FK_needed": FK_needed}
    return {
        "values": vals,
        "checks": checks,
        "steps": [
            step("Design axial load", r"F_{A,d} = S\,F_A", FA_design, "force", "kN"),
            step("Required residual clamp", r"F_{K,req} = \max\left(S\,F_Q/\mu_T,\; 0.2\,F_{A,d}\right)", FK_needed, "force", "kN"),
            step("Residual clamp (per candidate)", r"F_{KR} = F_{M}/\alpha_A - (1-\Phi_n)F_{A,d} - F_Z \ge F_{K,req}", None),
            step("Bolt stress (per candidate)", r"\sigma_{red} = \sqrt{\left(\tfrac{F_M + \Phi_n F_{A,d}}{A_s}\right)^2 + 3(0.5\tau)^2} \le R_{p0.2}", None),
        ],
        "tables": [table("Candidate bolts", [
            {"key": "size", "label": "Size"}, {"key": "cls", "label": "Class"},
            {"key": "As", "label": "As", "unit": "mm²"}, {"key": "FM", "label": "FM,max", "unit": "kN"},
            {"key": "FMmin", "label": "FM,min", "unit": "kN"}, {"key": "MA", "label": "Torque", "unit": "N·m"},
            {"key": "FKR", "label": "Residual clamp", "unit": "kN"}, {"key": "util", "label": "Util.", "unit": "%"},
            {"key": "L", "label": "Length", "unit": "mm"}], rows,
            highlight={"size": best["size"], "cls": best["cls"]} if best else None,
            note="Smallest adequate size first; within a size the lowest class that works.")],
        "diagram": {"designation": best["designation"] if best else "—",
                    "size": best["size"] if best else None, "L": best["L"] if best else None,
                    "lK": fmt(x["lK"] * 1000, 3), "joint_type": x["joint_type"], "head": x["head"],
                    "ok": bool(best)},
        "notes": notes,
    }


FASTENER_SELECTOR = Calculator(
    id="fastener_selector",
    governing=["FA", "FQ", "lK"],
    title="Which bolt? Fastener selector",
    category=CATEGORY,
    summary="Smallest standard ISO bolt size and property class for an axial and/or transverse load, with stock length, torque and full designation.",
    description=(
        "For each standard size the selector computes the VDI 2230 preload, the minimum preload after "
        "tightening scatter, and the clamp force left under load. It returns the smallest size (and "
        "lowest class) that keeps the joint closed, carries transverse load by friction and stays below "
        "yield, plus an orderable designation with a stock length."
    ),
    params=[
        Param("FA", "Axial service load per bolt FA", dim="force", default=8, unit="kN", min=0, group="Loads"),
        Param("FQ", "Transverse load per bolt FQ", dim="force", default=0, unit="kN", min=0, group="Loads",
              help="Carried by friction between the clamped parts."),
        Param("muT", "Interface friction μT", default=0.15, min=0.05, max=0.6, group="Loads",
              help="0.1–0.15 machined dry steel, 0.2–0.3 blasted, 0.5 friction-grip prepared."),
        Param("sf", "Safety factor on loads", default=1.25, min=1, group="Loads"),
        Param("pref", "Property class", kind="select", default="any", options=CLASS_PREF_OPTIONS, group="Bolt"),
        head_param("shcs", group="Bolt"),
        Param("joint_type", "Joint type", kind="select", default="through", group="Bolt",
              options=[{"value": "through", "label": "Through bolt + nut + washer"},
                       {"value": "tapped_steel", "label": "Tapped hole in steel/iron (≥1.0 d)"},
                       {"value": "tapped_al", "label": "Tapped hole in aluminium (≥2.0 d)"}]),
        Param("lK", "Clamp length", dim="length", default=20, unit="mm", min=0, group="Bolt"),
        *friction_params(),
        method_param(),
        Param("phi", "Assumed load factor Φn", default=0.2, min=0.05, max=1, group="Tightening",
              advanced=True, help="Typical 0.1–0.3 for steel joints; 1.0 is fully conservative."),
    ],
    outputs=[
        Output("recommended", "Recommended fastener", primary=True),
        Output("MA", "Tightening torque", "torque", primary=True, sig=3),
        Output("FMmin", "Min preload FM,min", "force", unit="kN", primary=True, sig=3),
        Output("FKR", "Residual clamp force", "force", unit="kN"),
        Output("util", "Yield utilisation under load", sig=3),
        Output("FK_needed", "Required clamp force", "force", unit="kN"),
    ],
    compute=_compute_selector,
    diagram="bolt_stack",
    formulas=[r"F_{KR} = \frac{F_{M,zul}}{\alpha_A} - (1-\Phi_n)F_A - F_Z \ge \frac{S F_Q}{\mu_T}"],
    references=[REFS_VDI, REFS_898, "ISO 4762, ISO 4017, ISO 4032, ISO 7089", REFS_SHIG],
    keywords=["which bolt", "bolt size", "select bolt", "fastener selection", "screw size for load",
              "bolt sizing", "bolt grade", "how big a bolt", "stock length", "fastener selector"],
    presets=[
        {"label": "Motor mount, 4 kN shear per bolt", "values": {
            "FA": {"value": 1, "unit": "kN"}, "FQ": {"value": 4, "unit": "kN"},
            "lK": {"value": 25, "unit": "mm"}}},
        {"label": "Tapped into aluminium, 3 kN", "values": {
            "FA": {"value": 3, "unit": "kN"}, "joint_type": "tapped_al", "lK": {"value": 12, "unit": "mm"}}},
        {"label": "Stainless, 5 kN axial", "values": {"FA": {"value": 5, "unit": "kN"}, "pref": "A4-70"}},
    ],
)
