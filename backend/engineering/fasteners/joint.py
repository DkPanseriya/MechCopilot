"""Axially loaded bolted joint — VDI 2230-1 (simplified: no thermal, no bending)."""
import math
from typing import Any, Dict

from ..core import Calculator, CalcError, Output, Param, check, fmt, series, step, table
from . import data
from .common import (CATEGORY, REFS_898, REFS_SHIG, REFS_VDI, MPa, class_param, friction_params,
                     head_geometry, head_param, kN, method_param, resolve_friction,
                     resolve_strength, resolve_thread, thread_param, torsion_section_modulus)

E_STEEL = 205000.0      # MPa
E_STAINLESS = 193000.0


def bolt_compliance(th: Dict[str, float], lK: float, l_shank: float, head_type: str,
                    joint_type: str, E_bolt: float, E_nut: float) -> Dict[str, float]:
    """δS (mm/N) as a chain of elastic sections — VDI 2230-1 §5.1.1."""
    d, AN, Ad3 = th["d"], th["AN"], th["Ad3"]
    l_thread = lK - l_shank
    dSK = (0.5 if head_type == "hex" else 0.4) * d / (E_bolt * AN)       # head
    d1 = l_shank / (E_bolt * AN)                                            # unthreaded shank
    dGew = l_thread / (E_bolt * Ad3)                                        # free loaded thread
    dG = 0.5 * d / (E_bolt * Ad3)                                           # engaged thread
    if joint_type == "through":
        dM = 0.4 * d / (E_bolt * AN)                                        # nut
    else:
        dM = 0.33 * d / (E_nut * AN)                                        # tapped thread in part
    return {"total": dSK + d1 + dGew + dG + dM, "head": dSK, "shank": d1, "thread": dGew,
            "engaged": dG + dM}


def plate_compliance(dW: float, dh: float, DA: float, lK: float, E_plate: float,
                     joint_type: str) -> Dict[str, float]:
    """δP (mm/N) from the VDI 2230 deformation cone / sleeve substitute body."""
    w = 1.0 if joint_type == "through" else 2.0
    beta = lK / dW
    y = DA / dW
    if joint_type == "through":
        tan_phi = 0.362 + 0.032 * math.log(beta / 2) + 0.153 * math.log(y)
    else:
        tan_phi = 0.348 + 0.013 * math.log(beta) + 0.193 * math.log(y)
    tan_phi = max(tan_phi, 0.05)
    DA_gr = dW + w * lK * tan_phi
    if DA >= DA_gr:
        num = (dW + dh) * (dW + w * lK * tan_phi - dh)
        den = (dW - dh) * (dW + w * lK * tan_phi + dh)
        dP = 2 * math.log(num / den) / (w * E_plate * math.pi * dh * tan_phi)
        body = "cone"
    elif DA > dW:
        cone = 2 / (w * dh * tan_phi) * math.log((dW + dh) * (DA - dh) / ((dW - dh) * (DA + dh)))
        sleeve = 4 / (DA ** 2 - dh ** 2) * (lK - (DA - dW) / (w * tan_phi))
        dP = (cone + sleeve) / (E_plate * math.pi)
        body = "cone + sleeve"
    else:
        dP = 4 * lK / (E_plate * math.pi * (DA ** 2 - dh ** 2))
        body = "sleeve"
    return {"dP": dP, "tan_phi": tan_phi, "DA_gr": DA_gr, "body": body}


def _compute_joint(x: Dict[str, Any]) -> Dict[str, Any]:
    th = resolve_thread(x)
    size, d = th["nominal"], th["d"]
    st = resolve_strength(x["cls"], d)
    fr = resolve_friction(x)
    pm = data.PLATE_MATERIALS[x["plate"]]
    alpha = data.TIGHTENING[x["method"]]["alpha"]
    jt = x["joint_type"]
    lK = x["lK"] * 1000
    l_shank = x["l_shank"] * 1000
    DA = x["DA"] * 1000
    FA_max, FA_min, FK_req = x["FA_max"], x["FA_min"], x["FK_req"]
    n = x["n_load"]
    interfaces = x["interfaces"]

    if lK <= 0:
        raise CalcError("Clamp length must be positive.")
    if l_shank < 0 or l_shank > lK:
        raise CalcError("Shank length in the clamp must be between 0 and the clamp length.")
    if FA_max < 0 or FA_min < 0 or FA_min > FA_max:
        raise CalcError("Axial loads must satisfy 0 ≤ FA,min ≤ FA,max.")
    if not 0.1 <= n <= 1.0:
        raise CalcError("Load introduction factor n must be between 0.1 and 1.")
    if interfaces < 0 or interfaces > 10:
        raise CalcError("Number of inner interfaces must be 0–10.")

    geo = head_geometry(x["head"], size)
    dh = geo["dh"]
    washer = data.WASHER.get(size) if x["washer"] else None
    if x["washer"] and washer is None:
        raise CalcError(f"No ISO 7089 washer listed for {size}.")
    # A hardened washer moves the bearing face onto the plate out to its outer diameter.
    dW = max(geo["dW"], washer["d2"]) if washer else geo["dW"]
    if DA <= dh:
        raise CalcError("Outer diameter of the clamped parts must exceed the hole diameter.")

    E_bolt = E_STAINLESS if st["stainless"] else E_STEEL
    bc = bolt_compliance(th, lK, l_shank, x["head"], jt, E_bolt, pm["E"])
    pc = plate_compliance(dW, dh, DA, lK, pm["E"], jt)
    dS, dP = bc["total"], pc["dP"]
    phi_K = dP / (dS + dP)
    phi = n * phi_K

    fZ_um = 3.0 + 3.0 * (2 if jt == "through" else 1) + 2.0 * interfaces
    FZ = (fZ_um / 1000.0) / (dS + dP)

    FM_zul = data.assembly_preload(th, st["Rp"], fr["muG"], x["nu"])
    FM_min = FM_zul / alpha
    FSA = phi * FA_max
    FPA = (1 - phi) * FA_max
    FKR = FM_min - FPA - FZ

    MG = FM_zul * data.thread_torque_factor(th, fr["muG"])
    tau = 0.5 * MG / torsion_section_modulus(th["ds"])          # residual torsion, kτ = 0.5
    sig_z = (FM_zul + FSA) / th["As"]
    sred = math.sqrt(sig_z ** 2 + 3 * tau ** 2)
    SF_static = st["Rp"] / sred

    sig_a = phi * (FA_max - FA_min) / (2 * th["As"])
    sig_ASV = data.endurance_limit_rolled(d)
    SF_fatigue = sig_ASV / sig_a if sig_a > 0 else None   # None: static load, no fatigue check

    Ap = math.pi / 4 * (dW ** 2 - dh ** 2)
    p = (FM_zul + FSA) / Ap
    SF_p = pm["pG"] / p

    MA = data.tightening_torque(FM_zul, th, fr["muG"], fr["muK"], geo["DKm"]) / 1000.0

    checks = []
    if FKR <= 0:
        checks.append(check("Joint separation", False,
                            f"Residual clamp force is {kN(FKR)} — the joint opens under load. Increase bolt "
                            "size/class, tighten more precisely (lower αA) or reduce the load per bolt."))
    else:
        checks.append(check("Residual clamp force", FKR >= FK_req,
                            f"FKR = {kN(FKR)} vs required {kN(FK_req)}."
                            + ("" if FKR >= FK_req else " Use a larger or stronger bolt, or a more accurate "
                               "tightening method."),
                            value=FKR, limit=FK_req))
    checks.append(check("Static bolt stress", SF_static >= 1.0,
                        f"σred = {MPa(sred)} vs Rp0.2 = {MPa(st['Rp'])} (SF {fmt(SF_static, 3)}).",
                        value=SF_static, limit=1.0))
    if sig_a > 0:
        if st["stainless"]:
            checks.append(check("Fatigue", True, "σASV formula is for rolled steel threads; verify "
                                "stainless fatigue with supplier data.", warn=True))
        else:
            checks.append(check("Fatigue (alternating stress)", SF_fatigue >= 1.2,
                                f"σa = {MPa(sig_a)} vs σASV = {MPa(sig_ASV)} (SF {fmt(SF_fatigue, 3)}, need ≥ 1.2).",
                                warn=SF_fatigue >= 1.0, value=SF_fatigue, limit=1.2))
    checks.append(check("Surface pressure under head", SF_p >= 1.0,
                        f"p = {MPa(p)} vs pG = {MPa(pm['pG'])} for {pm['label']}"
                        + (" (on hardened washer)." if washer else ".")
                        + ("" if SF_p >= 1 else (" Use a larger washer or a flanged head." if washer
                                                 else " Add a hardened washer to spread the load.")),
                        value=SF_p, limit=1.0))

    # Joint diagram with the minimum in-service preload (governs separation).
    FV = max(FM_min - FZ, 0.0)
    fS, fP = FV * dS, FV * dP
    x_op = fS + FSA * dS
    to_m = lambda v: v / 1000.0        # mm -> m (canonical length)
    x_end = max(x_op, fS) * 1.15
    bolt_x = [0.0, to_m(fS), to_m(x_end)]
    bolt_y = [0.0, FV, x_end / dS]     # bolt force is linear in its own elongation
    plate_x = [to_m(fS), to_m(fS + fP)]
    plate_y = [FV, 0.0]

    return {
        "values": {"phi": phi, "FKR": FKR, "SF_static": SF_static, "SF_fatigue": SF_fatigue,
                   "SF_p": SF_p, "FM_zul": FM_zul, "FM_min": FM_min, "MA": MA, "FZ": FZ,
                   "FSA": FSA, "kS": 1000.0 / dS, "kP": 1000.0 / dP, "sig_a": sig_a * 1e6,
                   "sig_ASV": sig_ASV * 1e6, "p": p * 1e6, "DA_gr": pc["DA_gr"] / 1000},
        "checks": checks,
        "steps": [
            step("Bolt compliance δS (mm/N)",
                 r"\delta_S = \delta_{SK} + \delta_1 + \delta_{Gew} + \delta_G + \delta_M", dS, sig=4),
            step(f"Plate compliance δP, {pc['body']} (mm/N)",
                 r"\delta_P = \frac{2\ln\left[\frac{(d_W + d_h)(d_W + w\,l_K\tan\varphi - d_h)}{(d_W - d_h)(d_W + w\,l_K\tan\varphi + d_h)}\right]}{w\,E_P\,\pi\,d_h\tan\varphi}",
                 dP, sig=4),
            step("Load factor", r"\Phi_n = n\,\frac{\delta_P}{\delta_S + \delta_P}", phi, sig=3),
            step("Embedding loss", r"F_Z = f_Z/(\delta_S + \delta_P)", FZ, "force", "kN"),
            step("Assembly preload", r"F_{M,zul} \;(\nu\,R_{p0.2})", FM_zul, "force", "kN"),
            step("Minimum preload", r"F_{M,min} = F_{M,zul}/\alpha_A", FM_min, "force", "kN"),
            step("Residual clamp force", r"F_{KR} = F_{M,min} - (1-\Phi_n)F_{A,max} - F_Z", FKR, "force", "kN"),
            step("Max bolt stress", r"\sigma_{red,B} = \sqrt{\left(\tfrac{F_{M,zul} + \Phi_n F_A}{A_s}\right)^2 + 3(0.5\tau)^2}",
                 sred * 1e6, "stress"),
            step("Alternating stress", r"\sigma_a = \Phi_n\,\frac{F_{A,max} - F_{A,min}}{2A_s}", sig_a * 1e6, "stress"),
            step("Endurance (rolled)", r"\sigma_{ASV} = 0.85\left(\tfrac{150}{d} + 45\right)", sig_ASV * 1e6, "stress"),
            step("Surface pressure", r"p = \frac{F_{M,zul} + \Phi_n F_A}{\tfrac{\pi}{4}(d_W^2 - d_h^2)}", p * 1e6, "stress"),
        ],
        "series": [
            series("bolt_line", "Bolt", bolt_x, bolt_y, x_label="elongation f", y_label="F",
                   x_dim="length", y_dim="force", x_unit="um", y_unit="kN", group="Joint diagram"),
            series("plate_line", "Clamped parts", plate_x, plate_y, x_label="elongation f", y_label="F",
                   x_dim="length", y_dim="force", x_unit="um", y_unit="kN", group="Joint diagram"),
            series("op_points", "Under load FA,max (bolt / plates)", [to_m(x_op), to_m(x_op)],
                   [FV + FSA, FV - FPA], x_label="elongation f", y_label="F", x_dim="length",
                   y_dim="force", x_unit="um", y_unit="kN", kind="scatter", group="Joint diagram"),
        ],
        "tables": [table("Stiffness breakdown", [
            {"key": "part", "label": "Section"}, {"key": "share", "label": "Compliance share", "unit": "%"}], [
            {"part": "Bolt head", "share": fmt(100 * bc["head"] / dS, 3)},
            {"part": "Shank (unthreaded)", "share": fmt(100 * bc["shank"] / dS, 3)},
            {"part": "Free loaded thread", "share": fmt(100 * bc["thread"] / dS, 3)},
            {"part": "Engaged thread + nut", "share": fmt(100 * bc["engaged"] / dS, 3)},
        ], note=f"Bolt {fmt(1 / dS / 1000, 4)} kN/mm vs clamped parts {fmt(1 / dP / 1000, 4)} kN/mm — "
                f"the plates are {fmt(dS / dP, 3)}× stiffer, so the bolt sees only Φ of the external load.")],
        "diagram": {
            "designation": th["designation"], "cls": x["cls"], "joint_type": jt, "head": x["head"],
            "lK": fmt(lK, 3), "DA": fmt(DA, 3), "FA": kN(FA_max), "FM": kN(FM_zul), "FKR": kN(FKR),
            "phi": fmt(phi, 3), "body": pc["body"], "ok_clamp": FKR > 0 and FKR >= FK_req,
            "interfaces": int(interfaces), "washer": bool(washer),
        },
        "notes": [
            "Simplified VDI 2230: concentric axial load, no prying/bending, no thermal preload change. "
            "Embedding uses VDI Table 5 values for Rz 10–40 µm.",
            f"Tighten to MA ≈ {fmt(MA, 3)} N·m ({fr['label'] if fr['label'] != 'custom' else 'custom friction'}).",
        ],
    }


BOLTED_JOINT = Calculator(
    id="bolted_joint",
    governing=["thread", "FA_max", "FA_min", "lK"],
    title="Bolted joint under axial load (VDI 2230)",
    category=CATEGORY,
    summary="Bolt and plate stiffness, load factor, embedding, residual clamp force, static, fatigue and surface-pressure checks with the joint diagram.",
    description=(
        "A simplified VDI 2230-1 analysis of a concentrically loaded bolted joint. The bolt is modelled "
        "as a chain of elastic sections and the clamped parts as the VDI deformation cone. The load "
        "factor Φ decides how much of the external load reaches the bolt; the rest relieves the "
        "clamping. Checks cover separation, static strength, fatigue of the rolled thread and "
        "pressure under the head."
    ),
    params=[
        thread_param("M10"),
        class_param("8.8"),
        head_param("hex"),
        Param("joint_type", "Joint type", kind="select", default="through", group="Joint",
              options=[{"value": "through", "label": "Through bolt with nut (DSV)"},
                       {"value": "tapped", "label": "Tapped hole in the part (ESV)"}]),
        Param("lK", "Clamp length lK", dim="length", default=30, unit="mm", min=0, group="Joint"),
        Param("l_shank", "Unthreaded shank inside clamp", dim="length", default=0, unit="mm", min=0,
              group="Joint", help="0 = fully threaded bolt."),
        Param("DA", "Outer diameter of clamped parts DA", dim="length", default=40, unit="mm",
              group="Joint", help="Width of material around the bolt (e.g. flange width or bolt spacing)."),
        Param("plate", "Clamped part material", kind="select", default="s355",
              options=data.PLATE_OPTIONS, group="Joint"),
        Param("interfaces", "Inner interfaces (plates − 1)", default=1, min=0, max=10, group="Joint"),
        Param("washer", "Hardened washer under head (ISO 7089 200 HV)", kind="bool", default=False,
              group="Joint", help="Spreads the head load over the washer OD — cuts surface pressure on soft parts."),
        Param("FA_max", "Axial load per bolt FA,max", dim="force", default=8, unit="kN", min=0, group="Loads"),
        Param("FA_min", "Axial load per bolt FA,min", dim="force", default=0, unit="kN", min=0, group="Loads",
              help="Equal to FA,max for static load."),
        Param("FK_req", "Required residual clamp FK,req", dim="force", default=2, unit="kN", min=0,
              group="Loads", help="Sealing pressure or friction grip needed at the interface."),
        *friction_params(),
        method_param(),
        Param("nu", "Yield utilisation ν", default=0.9, min=0.3, max=1.0, group="Tightening", advanced=True),
        Param("n_load", "Load introduction factor n", default=0.5, min=0.1, max=1.0, group="Joint",
              advanced=True, help="0.5 for load introduced mid-plate; 1.0 under the head (worst case for the bolt)."),
    ],
    outputs=[
        Output("FKR", "Residual clamp force FKR", "force", unit="kN", primary=True, sig=3),
        Output("phi", "Load factor Φn", primary=True, sig=3),
        Output("SF_static", "Static safety (yield)", primary=True, sig=3),
        Output("SF_fatigue", "Fatigue safety", primary=True, sig=3),
        Output("SF_p", "Surface-pressure safety", sig=3),
        Output("FM_zul", "Assembly preload FM,zul", "force", unit="kN"),
        Output("FM_min", "Min preload FM,min", "force", unit="kN"),
        Output("MA", "Tightening torque MA", "torque"),
        Output("FZ", "Embedding loss FZ", "force", unit="kN"),
        Output("FSA", "Additional bolt load FSA", "force", unit="kN"),
        Output("kS", "Bolt stiffness", "stiffness", unit="kN/mm"),
        Output("kP", "Plate stiffness", "stiffness", unit="kN/mm"),
        Output("sig_a", "Alternating stress σa", "stress"),
        Output("sig_ASV", "Thread endurance σASV", "stress"),
        Output("p", "Surface pressure p", "stress"),
        Output("DA_gr", "Limiting cone diameter DA,Gr", "length"),
    ],
    compute=_compute_joint,
    diagram="bolted_joint",
    formulas=[r"\Phi_n = n\,\frac{\delta_P}{\delta_S + \delta_P}",
              r"F_{KR} = F_{M,min} - (1 - \Phi_n)F_A - F_Z",
              r"\sigma_a = \Phi_n\,\frac{F_{A,max} - F_{A,min}}{2A_s} \le \sigma_{ASV}"],
    references=[REFS_VDI, REFS_898, REFS_SHIG],
    keywords=["bolted joint", "joint diagram", "load factor", "clamp force", "separation",
              "bolt fatigue", "joint stiffness", "vdi 2230", "flange bolts", "cylinder head bolts",
              "surface pressure"],
    presets=[
        {"label": "Flange, pulsating 10 kN", "values": {
            "thread": "M12", "cls": "10.9", "FA_max": {"value": 10, "unit": "kN"},
            "FA_min": {"value": 0, "unit": "kN"}, "lK": {"value": 40, "unit": "mm"},
            "DA": {"value": 50, "unit": "mm"}, "method": "torque_measured", "washer": True}},
        {"label": "M8 into aluminium housing", "values": {
            "thread": "M8", "joint_type": "tapped", "plate": "al6082", "head": "shcs",
            "lK": {"value": 15, "unit": "mm"}, "FA_max": {"value": 3, "unit": "kN"},
            "DA": {"value": 24, "unit": "mm"}, "interfaces": 0, "washer": True}},
    ],
)
