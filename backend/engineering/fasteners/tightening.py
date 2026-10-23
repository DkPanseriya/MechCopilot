"""Bolt dimension lookup and VDI 2230 tightening torque / preload."""
import math
from typing import Any, Dict

from ..core import Calculator, CalcError, Output, Param, check, fmt, linspace, series, step, table
from . import data
from .common import (CATEGORY, REFS_261, REFS_898, REFS_SHIG, REFS_VDI, Nm, class_param,
                     friction_params, head_geometry, head_param, kN, method_param,
                     resolve_friction, resolve_strength, resolve_thread, thread_param)


# --------------------------------------------------------------------------
# 1. Bolt, nut & hole dimensions
# --------------------------------------------------------------------------

def _compute_lookup(x: Dict[str, Any]) -> Dict[str, Any]:
    th = resolve_thread(x)
    size = th["nominal"]
    st = resolve_strength(x["cls"], th["d"])
    hd = data.head(x["head"], size)
    if hd is None:
        raise CalcError(f"{data.HEAD_STD[x['head']]} is not listed for {size}. Choose another head type.")
    mu, nu = x["mu"], x["nu"]
    if not 0.03 <= mu <= 0.4:
        raise CalcError("Friction coefficient should be between 0.03 and 0.4.")
    if not 0.3 <= nu <= 1.0:
        raise CalcError("Utilisation ν must be between 0.3 and 1.0.")

    geo = head_geometry(x["head"], size)
    FM = data.assembly_preload(th, st["Rp"], mu, nu)
    MA = data.tightening_torque(FM, th, mu, mu, geo["DKm"]) / 1000.0  # N·m
    proof = th["As"] * st["Sp"]
    breaking = th["As"] * st["Rm"]
    nut, washer, hole = data.NUT.get(size), data.WASHER.get(size), data.CLEARANCE[size]

    rows = [
        {"item": "Thread", "value": f"{th['designation']}  (pitch {fmt(th['P'])} mm, {'coarse' if th['coarse'] else 'fine'})"},
        {"item": "Pitch diameter d2", "value": f"{fmt(th['d2'], 4)} mm"},
        {"item": "Minor diameter d3 (bolt)", "value": f"{fmt(th['d3'], 4)} mm"},
        {"item": "Minor diameter D1 (nut)", "value": f"{fmt(th['D1'], 4)} mm"},
        {"item": "Tensile stress area As", "value": f"{fmt(th['As'], 4)} mm²"},
        {"item": "Tap drill", "value": f"Ø{fmt(th['tap'])} mm"},
    ]
    if x["head"] == "hex":
        rows += [{"item": "Head across flats s (spanner)", "value": f"{fmt(hd['s'])} mm"},
                 {"item": "Head across corners e", "value": f"{fmt(hd['e'])} mm"},
                 {"item": "Head height k", "value": f"{fmt(hd['k'])} mm"}]
    else:
        rows += [{"item": "Head diameter dk", "value": f"{fmt(hd['dk'])} mm"},
                 {"item": "Head height k", "value": f"{fmt(hd['k'])} mm"},
                 {"item": "Hex key s", "value": f"{fmt(hd['s'])} mm"}]
    if nut:
        rows += [{"item": "Nut ISO 4032: across flats / height", "value": f"{fmt(nut['s'])} / {fmt(nut['m'])} mm"}]
    if washer:
        rows += [{"item": "Washer ISO 7089: d1 × d2 × h", "value": f"{fmt(washer['d1'])} × {fmt(washer['d2'])} × {fmt(washer['h'])} mm"}]
    rows += [{"item": "Clearance hole ISO 273 fine / medium / coarse",
              "value": f"{fmt(hole['fine'])} / {fmt(hole['medium'])} / {fmt(hole['coarse'])} mm"},
             {"item": "Proof load (As·Sp)", "value": kN(proof)},
             {"item": "Min. breaking load (As·Rm)", "value": kN(breaking)}]

    checks = [check("Preload within proof load", FM <= proof,
                    f"Assembly preload {kN(FM)} is {fmt(100 * FM / proof, 3)} % of the proof load.",
                    warn=True)]
    notes = [f"Preload and torque assume μG = μK = {fmt(mu, 3)}, {fmt(100 * nu, 3)} % utilisation of "
             f"Rp0.2 and a medium clearance hole. Use the tightening calculator for other conditions."]
    if st["stainless"]:
        notes.append("Stainless fasteners gall easily: use anti-seize and tighten slowly.")

    return {
        "values": {"As": th["As"] * 1e-6, "FM": FM, "MA": MA, "P": th["P"] / 1000,
                   "d2": th["d2"] / 1000, "d3": th["d3"] / 1000, "tap": th["tap"] / 1000,
                   "proof": proof, "breaking": breaking, "hole": hole["medium"] / 1000},
        "checks": checks,
        "steps": [
            step("Pitch diameter", r"d_2 = d - 0.6495\,P", th["d2"] / 1000, "length"),
            step("Minor diameter", r"d_3 = d - 1.2269\,P", th["d3"] / 1000, "length"),
            step("Stress area", r"A_s = \tfrac{\pi}{4}\left(\tfrac{d_2 + d_3}{2}\right)^2", th["As"] * 1e-6, "area"),
            step("Assembly preload", r"F_M = \frac{A_0\,\nu\,R_{p0.2}}{\sqrt{1 + 3\left[\tfrac{3}{2}\tfrac{d_2}{d_0}\left(\tfrac{P}{\pi d_2} + 1.155\mu_G\right)\right]^2}}",
                 FM, "force", "kN"),
            step("Tightening torque", r"M_A = F_M\left(0.16P + 0.58 d_2 \mu_G + \mu_K \tfrac{D_{Km}}{2}\right)",
                 MA, "torque"),
        ],
        "tables": [table(f"{th['designation']} – {x['cls']} – {data.HEAD_STD[x['head']]}",
                         [{"key": "item", "label": "Dimension"}, {"key": "value", "label": "Value"}], rows)],
        "diagram": {
            "size": size, "designation": th["designation"], "head": x["head"],
            "d": th["d"], "P": th["P"], "k": hd["k"],
            "dk": hd.get("dk"), "s": hd.get("s"), "e": hd.get("e"),
            "nut_m": nut["m"] if nut else None, "nut_s": nut["s"] if nut else None,
            "washer_d2": washer["d2"] if washer else None, "washer_h": washer["h"] if washer else None,
            "hole": hole["medium"], "tap": th["tap"], "As": fmt(th["As"], 3),
            "FM": kN(FM), "MA": Nm(MA), "cls": x["cls"],
        },
        "notes": notes,
    }


FASTENER_LOOKUP = Calculator(
    id="fastener_lookup",
    title="Bolt, nut & hole dimensions",
    category=CATEGORY,
    summary="Full ISO dimensions for a metric bolt: thread, head, nut, washer, clearance hole, tap drill, proof load and a recommended tightening torque.",
    description=(
        "Looks up ISO 261 thread geometry, ISO 4762 / 4017 / 10642 head dimensions, ISO 4032 nuts, "
        "ISO 7089 washers and ISO 273 clearance holes for one metric size, and gives the VDI 2230 "
        "assembly preload and tightening torque at 90 % yield utilisation."
    ),
    params=[
        thread_param("M10"),
        head_param("shcs"),
        class_param("8.8"),
        Param("mu", "Friction coefficient μ (thread = head)", default=0.12, min=0.04, max=0.4,
              group="Tightening", advanced=True),
        Param("nu", "Yield utilisation ν", default=0.9, min=0.3, max=1.0, group="Tightening",
              advanced=True, help="VDI 2230 tables use 90 % of Rp0.2 (combined tension + torsion)."),
    ],
    outputs=[
        Output("As", "Stress area As", "area", primary=True),
        Output("FM", "Assembly preload FM", "force", unit="kN", primary=True, sig=3),
        Output("MA", "Tightening torque MA", "torque", primary=True, sig=3),
        Output("P", "Pitch P", "length"),
        Output("d2", "Pitch diameter d2", "length"),
        Output("d3", "Minor diameter d3", "length"),
        Output("tap", "Tap drill", "length"),
        Output("hole", "Clearance hole (medium)", "length"),
        Output("proof", "Proof load", "force", unit="kN"),
        Output("breaking", "Min. breaking load", "force", unit="kN"),
    ],
    compute=_compute_lookup,
    diagram="bolt_dimensions",
    formulas=[r"A_s = \frac{\pi}{4}\left(\frac{d_2 + d_3}{2}\right)^2",
              r"M_A = F_M\left(0.16P + 0.58\,d_2\,\mu_G + \mu_K\,\frac{D_{Km}}{2}\right)"],
    references=[REFS_261, REFS_898, "ISO 4762, ISO 4017, ISO 10642, ISO 4032, ISO 7089, ISO 273",
                REFS_VDI],
    keywords=["bolt dimensions", "screw size", "metric thread", "stress area", "tap drill",
              "clearance hole", "hex key", "spanner size", "nut", "washer", "socket head cap screw",
              "iso 4762", "iso 4017", "proof load"],
    presets=[
        {"label": "M6 12.9 cap screw", "values": {"thread": "M6", "cls": "12.9", "head": "shcs"}},
        {"label": "M16 8.8 hex bolt", "values": {"thread": "M16", "cls": "8.8", "head": "hex"}},
        {"label": "M8 A2-70 stainless", "values": {"thread": "M8", "cls": "A2-70", "head": "shcs"}},
    ],
)


# --------------------------------------------------------------------------
# 2. Tightening torque & preload (VDI 2230)
# --------------------------------------------------------------------------

def _compute_tightening(x: Dict[str, Any]) -> Dict[str, Any]:
    th = resolve_thread(x)
    size = th["nominal"]
    st = resolve_strength(x["cls"], th["d"])
    fr = resolve_friction(x)
    muG, muK = fr["muG"], fr["muK"]
    nu = x["nu"]
    if not 0.3 <= nu <= 1.0:
        raise CalcError("Utilisation ν must be between 0.3 and 1.0.")
    alpha = data.TIGHTENING[x["method"]]["alpha"]
    geo = head_geometry(x["head"], size, x["hole"])

    FMmax = data.assembly_preload(th, st["Rp"], muG, nu)
    FMmin = FMmax / alpha
    MA_Nmm = data.tightening_torque(FMmax, th, muG, muK, geo["DKm"])
    MA = MA_Nmm / 1000.0
    pitch_part = FMmax * 0.16 * th["P"]
    thread_part = FMmax * 0.58 * th["d2"] * muG
    head_part = FMmax * muK * geo["DKm"] / 2
    MG = FMmax * data.thread_torque_factor(th, muG)
    # VDI 2230 assembly state uses the plastic torsional modulus Wp = π d0³/12 (this is
    # where the 3/2 in the FM,zul formula comes from), so σred = ν·Rp0.2 exactly.
    tau = MG / (math.pi * th["ds"] ** 3 / 12)
    sigM = FMmax / th["As"]
    sred = math.sqrt(sigM ** 2 + 3 * tau ** 2)
    proof = th["As"] * st["Sp"]

    # Sensitivity: preload produced by this torque if the real friction differs.
    mus = linspace(0.06, 0.24, 37)
    fm_at_mu = [data.preload_from_torque(MA_Nmm, th, m, m * muK / muG, geo["DKm"]) for m in mus]
    fm_yield = [data.assembly_preload(th, st["Rp"], m, 1.0) for m in mus]

    checks = [check("Preload vs proof load", FMmax <= proof,
                    f"FM,max = {kN(FMmax)} is {fmt(100 * FMmax / proof, 3)} % of the proof load {kN(proof)}.",
                    warn=True)]
    if alpha >= 2.5:
        checks.append(check("Preload scatter", False,
                            f"With αA = {fmt(alpha, 2)} the minimum preload may be as low as {kN(FMmin)}. "
                            "Use a calibrated torque wrench or angle-controlled tightening for critical joints.",
                            warn=True))
    notes = []
    low_mu = 0.75 * muG
    fm_low = data.preload_from_torque(MA_Nmm, th, low_mu, 0.75 * muK, geo["DKm"])
    fy_low = data.assembly_preload(th, st["Rp"], low_mu, 1.0)
    notes.append(f"Friction sensitivity: if the real friction were 25 % lower (μ ≈ {fmt(low_mu, 2)}, e.g. "
                 f"extra lubricant) this torque would give {kN(fm_low)} — "
                 f"{fmt(100 * fm_low / fy_low, 3)} % of the yield preload. VDI 2230 designs with the lowest "
                 "expected friction for this reason.")
    if st["stainless"] and x["friction"] in ("dry", "stainless_dry"):
        checks.append(check("Galling", False, "Dry stainless threads gall. Use anti-seize paste and "
                            "reduce tightening speed.", warn=True))
    notes.append(f"Torque split: pitch {fmt(100 * pitch_part / MA_Nmm, 3)} %, "
                 f"thread friction {fmt(100 * thread_part / MA_Nmm, 3)} %, "
                 f"head friction {fmt(100 * head_part / MA_Nmm, 3)} % — most torque goes into friction.")

    return {
        "values": {"MA": MA, "FMmax": FMmax, "FMmin": FMmin, "sigM": sigM * 1e6, "tau": tau * 1e6,
                   "sred": sred * 1e6, "DKm": geo["DKm"] / 1000, "alpha": alpha, "muG": muG,
                   "muK": muK},
        "checks": checks,
        "steps": [
            step("Mean head friction diameter", r"D_{Km} = (d_W + d_h)/2", geo["DKm"] / 1000, "length"),
            step("Assembly preload (ν·Rp0.2)", r"F_{M,max} = \frac{A_0\,\nu\,R_{p0.2}}{\sqrt{1 + 3\left[\tfrac{3}{2}\tfrac{d_2}{d_0}\left(\tfrac{P}{\pi d_2} + 1.155\mu_G\right)\right]^2}}",
                 FMmax, "force", "kN"),
            step("Tightening torque", r"M_A = F_{M}\left(0.16P + 0.58 d_2 \mu_G + \mu_K \tfrac{D_{Km}}{2}\right)", MA, "torque"),
            step("Tensile stress", r"\sigma_M = F_M/A_0", sigM * 1e6, "stress"),
            step("Thread torsion (plastic)", r"\tau = M_G/W_p,\; W_p = \pi d_0^3/12", tau * 1e6, "stress"),
            step("Equivalent stress", r"\sigma_{red} = \sqrt{\sigma_M^2 + 3\tau^2} = \nu\,R_{p0.2}", sred * 1e6, "stress"),
            step("Minimum preload", r"F_{M,min} = F_{M,max}/\alpha_A", FMmin, "force", "kN"),
        ],
        "series": [
            series("fm_mu", "Preload at this torque", mus, fm_at_mu, x_label="μ", y_label="F_M",
                   y_dim="force", y_unit="kN", group="Preload vs actual friction",
                   markers=[{"x": muG, "label": "specified μ"}]),
            series("fm_yield", "Preload at yield (ν = 1)", mus, fm_yield, x_label="μ", y_label="F_M",
                   y_dim="force", y_unit="kN", group="Preload vs actual friction"),
        ],
        "diagram": {
            "designation": th["designation"], "cls": x["cls"], "head": x["head"],
            "MA": Nm(MA), "FMmax": kN(FMmax), "FMmin": kN(FMmin), "alpha": fmt(alpha, 2),
            "mu": f"μG {fmt(muG, 2)} / μK {fmt(muK, 2)}",
        },
        "notes": notes,
    }


BOLT_PRELOAD_TORQUE = Calculator(
    id="bolt_preload_torque",
    title="Tightening torque & preload (VDI 2230)",
    category=CATEGORY,
    summary="Tightening torque for a target preload, with friction condition, tightening-method scatter and a friction sensitivity plot.",
    description=(
        "Computes the permissible assembly preload at a chosen utilisation of the bolt yield strength "
        "(von Mises with thread torsion), the tightening torque that produces it, and the minimum "
        "preload left after tightening-method scatter αA. The plot shows how the same torque gives a "
        "very different preload if the real friction differs from the assumed value."
    ),
    params=[
        thread_param("M10"),
        class_param("8.8"),
        head_param("hex"),
        Param("hole", "Clearance hole (ISO 273)", kind="select", default="medium", group="Bolt",
              options=[{"value": "fine", "label": "Fine"}, {"value": "medium", "label": "Medium"},
                       {"value": "coarse", "label": "Coarse"}]),
        *friction_params(),
        method_param(),
        Param("nu", "Yield utilisation ν", default=0.9, min=0.3, max=1.0, group="Tightening",
              advanced=True, help="0.9 is the VDI 2230 table basis. Lower it for re-used bolts."),
    ],
    outputs=[
        Output("MA", "Tightening torque MA", "torque", primary=True, sig=3),
        Output("FMmax", "Max assembly preload FM,max", "force", unit="kN", primary=True, sig=3),
        Output("FMmin", "Min assembly preload FM,min", "force", unit="kN", primary=True, sig=3),
        Output("sigM", "Tensile stress σM", "stress"),
        Output("tau", "Torsional stress τ", "stress"),
        Output("sred", "Equivalent stress σred", "stress"),
        Output("DKm", "Mean head friction dia DKm", "length"),
        Output("alpha", "Tightening factor αA", sig=3),
        Output("muG", "Thread friction μG", sig=3),
        Output("muK", "Head friction μK", sig=3),
    ],
    compute=_compute_tightening,
    diagram="bolt_tightening",
    formulas=[r"M_A = F_M\left(0.16P + 0.58\,d_2\,\mu_G + \mu_K\,\frac{D_{Km}}{2}\right)",
              r"F_{M,min} = F_{M,max}/\alpha_A"],
    references=[REFS_VDI, REFS_898, REFS_SHIG],
    keywords=["tightening torque", "bolt torque", "preload", "clamp force", "torque wrench",
              "friction coefficient", "vdi 2230", "lubrication", "anti-seize", "nut factor"],
    presets=[
        {"label": "M12 10.9, MoS₂, calibrated wrench",
         "values": {"thread": "M12", "cls": "10.9", "friction": "mos2", "method": "torque_measured"}},
        {"label": "M8 A2-70 stainless, dry",
         "values": {"thread": "M8", "cls": "A2-70", "friction": "stainless_dry", "head": "shcs"}},
        {"label": "M20 8.8, impact wrench",
         "values": {"thread": "M20", "cls": "8.8", "method": "impact"}},
    ],
)
