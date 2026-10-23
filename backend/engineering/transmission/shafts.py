"""Shaft calculators: DE-Goodman fatigue sizing and first critical speed."""
import math
from typing import Any, Dict, List, Optional, Tuple

from ..core import (Calculator, CalcError, Output, Param, check, fmt, from_canonical,
                    linspace, series, step, table)
from ..materials import material_params, resolve_material

# --------------------------------------------------------------------------
# Shaft fatigue (Shigley 10th ed. §6-9, §7-4)
# --------------------------------------------------------------------------

# Surface factor ka = a * Sut[MPa]^b  (Shigley Table 6-2)
SURFACE = {
    "ground": (1.58, -0.085, "Ground"),
    "machined": (4.51, -0.265, "Machined or cold-drawn"),
    "hot_rolled": (57.7, -0.718, "Hot-rolled"),
    "as_forged": (272.0, -0.995, "As-forged"),
}

# Reliability factor ke (Shigley Table 6-5)
RELIABILITY = {
    "0.5": (1.000, "50 %"),
    "0.9": (0.897, "90 %"),
    "0.95": (0.868, "95 %"),
    "0.99": (0.814, "99 %"),
    "0.999": (0.753, "99.9 %"),
    "0.9999": (0.702, "99.99 %"),
    "0.99999": (0.659, "99.999 %"),
}

# First-iteration stress concentration (Shigley Table 7-1): (Kt bending, Kts torsion, label)
FEATURES = {
    "shoulder_sharp": (2.7, 2.2, "Shoulder fillet, sharp (r/d ≈ 0.02)"),
    "shoulder_round": (1.7, 1.5, "Shoulder fillet, well rounded (r/d ≈ 0.1)"),
    "keyseat_endmill": (2.14, 3.0, "End-mill keyseat (r/d ≈ 0.02)"),
    "keyseat_sled": (1.7, 3.0, "Sled-runner keyseat"),
    "ring_groove": (5.0, 3.0, "Retaining-ring groove"),
}


def size_factor(d: float) -> float:
    """kb for rotating round sections (Shigley eq. 6-20), d in metres."""
    dm = d * 1000
    if dm <= 2.79:
        return 1.0
    if dm <= 51:
        return 1.24 * dm ** -0.107
    if dm <= 254:
        return 1.51 * dm ** -0.157
    return 0.6


def endurance_limit(d: float, Sut: float, surface: str, ke: float, kd: float,
                    kmisc: float) -> Dict[str, float]:
    Se_prime = 0.5 * Sut if Sut <= 1400e6 else 700e6
    a, b, _ = SURFACE[surface]
    ka = a * (Sut / 1e6) ** b
    kb = size_factor(d)
    Se = ka * kb * 1.0 * kd * ke * kmisc * Se_prime
    return {"Se_prime": Se_prime, "ka": ka, "kb": kb, "Se": Se}


def de_factors(d: float, A: float, B: float, Se: float, Sut: float, Sy: float) -> Dict[str, float]:
    """DE fatigue safety factors (Shigley eqs. 7-8, 7-9, 7-11, 7-13).

    A = sqrt(4(Kf Ma)^2 + 3(Kfs Ta)^2), B = sqrt(4(Kf Mm)^2 + 3(Kfs Tm)^2)  [N·m]
    """
    k = 16 / (math.pi * d ** 3)
    inv = lambda x: float("inf") if x <= 0 else 1 / x
    goodman = inv(k * (A / Se + B / Sut))
    soderberg = inv(k * (A / Se + B / Sy))
    asme = inv(k * math.sqrt((A / Se) ** 2 + (B / Sy) ** 2))
    if A > 0:
        gerber = inv(8 * A / (math.pi * d ** 3 * Se)
                     * (1 + math.sqrt(1 + (2 * B * Se / (A * Sut)) ** 2)))
    else:
        gerber = inv(k * B / Sut)
    return {"goodman": goodman, "gerber": gerber, "asme": asme, "soderberg": soderberg,
            "sa": k * A, "sm": k * B}


def _kf(x: Dict[str, Any]) -> Tuple[float, float, str]:
    mode = x["kf_mode"]
    if mode == "direct":
        Kf, Kfs = x["Kf"], x["Kfs"]
        if Kf < 1 or Kfs < 1:
            raise CalcError("Kf and Kfs must be at least 1.")
        return Kf, Kfs, "Direct input"
    if mode == "none":
        return 1.0, 1.0, "No notch"
    Kt, Kts, label = FEATURES[mode]
    q, qs = x["q"], x["qs"]
    if not (0 <= q <= 1 and 0 <= qs <= 1):
        raise CalcError("Notch sensitivity q must lie between 0 and 1.")
    return 1 + q * (Kt - 1), 1 + qs * (Kts - 1), label


def _compute_shaft_fatigue(x: Dict[str, Any]) -> Dict[str, Any]:
    d = x["d"]
    if d <= 0:
        raise CalcError("Diameter must be positive.")
    Ma, Mm, Ta, Tm = (abs(x[k]) for k in ("Ma", "Mm", "Ta", "Tm"))
    if Ma == Mm == Ta == Tm == 0:
        raise CalcError("Enter at least one moment or torque.")
    mat = resolve_material(x)
    Sut, Sy = mat["Sut"], mat["Sy"]
    if Sy > Sut:
        raise CalcError("Yield strength cannot exceed ultimate strength.")
    ke = RELIABILITY[x["reliability"]][0]
    kd, kmisc, n_t = x["kd"], x["kmisc"], x["n_target"]
    if n_t <= 0:
        raise CalcError("Target safety factor must be positive.")
    Kf, Kfs, kf_label = _kf(x)

    A = math.sqrt(4 * (Kf * Ma) ** 2 + 3 * (Kfs * Ta) ** 2)
    B = math.sqrt(4 * (Kf * Mm) ** 2 + 3 * (Kfs * Tm) ** 2)
    se = endurance_limit(d, Sut, x["surface"], ke, kd, kmisc)
    Se = se["Se"]
    f = de_factors(d, A, B, Se, Sut, Sy)

    c = math.pi * d ** 3
    s_max = math.sqrt((32 * Kf * (Mm + Ma) / c) ** 2 + 3 * (16 * Kfs * (Tm + Ta) / c) ** 2)
    n_y = Sy / s_max if s_max > 0 else float("inf")

    # Required diameter for the target Goodman factor (kb depends on d -> iterate).
    d_req = d
    for _ in range(60):
        Se_i = endurance_limit(d_req, Sut, x["surface"], ke, kd, kmisc)["Se"]
        d_new = (16 * n_t / math.pi * (A / Se_i + B / Sut)) ** (1 / 3)
        if abs(d_new - d_req) < 1e-9:
            d_req = d_new
            break
        d_req = d_new

    # Plot 1: safety factors vs diameter.
    hi = max(1.8 * d, 1.3 * d_req)
    ds = linspace(0.6 * d, hi, 60)
    curves = {"goodman": [], "gerber": [], "asme": []}
    for di in ds:
        Se_i = endurance_limit(di, Sut, x["surface"], ke, kd, kmisc)["Se"]
        fi = de_factors(di, A, B, Se_i, Sut, Sy)
        for k in curves:
            curves[k].append(min(fi[k], 50.0))
    markers = [{"x": d, "label": "current"}, {"x": d_req, "label": f"required (n={fmt(n_t, 3)})"}]
    grp = "Fatigue safety factor vs diameter"
    s_nd = [
        series("n_goodman_d", "DE-Goodman", ds, curves["goodman"], x_label="d", y_label="n",
               x_dim="length", group=grp, markers=markers,
               ref_lines=[{"y": n_t, "label": f"target {fmt(n_t, 3)}"}]),
        series("n_gerber_d", "DE-Gerber", ds, curves["gerber"], x_label="d", y_label="n",
               x_dim="length", group=grp),
        series("n_asme_d", "DE-ASME elliptic", ds, curves["asme"], x_label="d", y_label="n",
               x_dim="length", group=grp),
    ]

    # Plot 2: fatigue diagram (σa vs σm) with the von Mises operating point.
    sa, sm = f["sa"], f["sm"]
    g2 = "Fatigue diagram (σa vs σm)"
    xm = linspace(0, Sut, 50)
    gerber_curve = [Se * (1 - (v / Sut) ** 2) for v in xm]
    t = 1 / (sa / Se + sm / Sut) if (sa > 0 or sm > 0) else 0
    s_fd = [
        series("gerber_line", "Gerber", xm, gerber_curve, x_label="σm", y_label="σa",
               x_dim="stress", y_dim="stress", group=g2),
        series("goodman_line", "Goodman", [0, Sut], [Se, 0], x_label="σm", y_label="σa",
               x_dim="stress", y_dim="stress", group=g2),
        series("yield_line", "First-cycle yield (Langer)", [0, Sy], [Sy, 0], x_label="σm",
               y_label="σa", x_dim="stress", y_dim="stress", group=g2),
        series("load_line", "Load line", [0, t * sm], [0, t * sa], x_label="σm", y_label="σa",
               x_dim="stress", y_dim="stress", group=g2),
        series("op_point", "Operating point", [sm], [sa], x_label="σm", y_label="σa",
               x_dim="stress", y_dim="stress", kind="scatter", group=g2),
    ]

    checks = [
        check("Fatigue (DE-Goodman)", f["goodman"] >= n_t,
              f"n = {fmt(f['goodman'], 3)} against a target of {fmt(n_t, 3)}",
              value=f["goodman"], limit=n_t),
        check("First-cycle yield", n_y >= n_t,
              f"n_y = {fmt(n_y, 3)} on the peak von Mises stress",
              value=n_y, limit=n_t),
    ]
    notes = [
        "DE-Goodman is conservative; DE-Gerber and DE-ASME elliptic are shown for comparison.",
        f"Stress concentration: {kf_label} → Kf = {fmt(Kf, 3)}, Kfs = {fmt(Kfs, 3)}.",
    ]
    if x["kf_mode"] not in ("direct", "none"):
        notes.append("Table 7-1 values are first-iteration estimates. Refine Kt with the real "
                     "fillet radius once the geometry is known.")
    if x["kf_mode"] == "keyseat_sled":
        notes.append("Shigley tabulates no torsion Kts for sled-runner keyseats; the end-mill "
                     "value (3.0) is used conservatively.")
    if Sut > 1400e6:
        notes.append("Sut > 1400 MPa: Se' capped at 700 MPa.")

    return {
        "values": {"n_goodman": f["goodman"], "n_yield": n_y, "d_req": d_req, "Se": Se,
                   "n_gerber": f["gerber"], "n_asme": f["asme"], "n_soderberg": f["soderberg"],
                   "sa": sa, "sm": sm, "Kf": Kf, "Kfs": Kfs, "ka": se["ka"], "kb": se["kb"]},
        "checks": checks,
        "steps": [
            step("Endurance limit (specimen)", r"S_e' = 0.5\,S_{ut}", se["Se_prime"], "stress"),
            step("Surface factor", r"k_a = a\,S_{ut}^{\,b}", se["ka"]),
            step("Size factor", r"k_b = 1.24\,d^{-0.107}\;(2.79 \le d \le 51\,\text{mm})", se["kb"]),
            step("Reliability factor", r"k_e", ke),
            step("Corrected endurance limit", r"S_e = k_a k_b k_c k_d k_e k_f S_e'", Se, "stress"),
            step("Alternating moment term", r"A = \sqrt{4(K_f M_a)^2 + 3(K_{fs} T_a)^2}", A, "torque"),
            step("Mean moment term", r"B = \sqrt{4(K_f M_m)^2 + 3(K_{fs} T_m)^2}", B, "torque"),
            step("von Mises alternating stress", r"\sigma_a' = 16A/(\pi d^3)", sa, "stress"),
            step("von Mises mean stress", r"\sigma_m' = 16B/(\pi d^3)", sm, "stress"),
            step("DE-Goodman", r"\frac{1}{n} = \frac{16}{\pi d^3}\left(\frac{A}{S_e} + \frac{B}{S_{ut}}\right)",
                 f["goodman"]),
            step("Peak von Mises", r"\sigma'_{max} = \sqrt{\left(\tfrac{32K_f(M_m+M_a)}{\pi d^3}\right)^2 + 3\left(\tfrac{16K_{fs}(T_m+T_a)}{\pi d^3}\right)^2}",
                 s_max, "stress"),
            step("Yield safety factor", r"n_y = S_y/\sigma'_{max}", n_y),
        ],
        "series": s_nd + s_fd,
        "tables": [table("Criteria comparison",
                         [{"key": "c", "label": "Criterion"}, {"key": "n", "label": "n"}],
                         [{"c": "DE-Goodman", "n": fmt(f["goodman"], 3)},
                          {"c": "DE-Gerber", "n": fmt(f["gerber"], 3)},
                          {"c": "DE-ASME elliptic", "n": fmt(f["asme"], 3)},
                          {"c": "DE-Soderberg", "n": fmt(f["soderberg"], 3)},
                          {"c": "First-cycle yield", "n": fmt(n_y, 3)}])],
        "diagram": {
            "d": fmt(from_canonical(d, "length"), 3),
            "Ma": f"{fmt(Ma, 3)} N·m", "Mm": f"{fmt(Mm, 3)} N·m",
            "Ta": f"{fmt(Ta, 3)} N·m", "Tm": f"{fmt(Tm, 3)} N·m",
            "Kf": fmt(Kf, 3), "Kfs": fmt(Kfs, 3), "feature": kf_label,
            "Se": f"{fmt(from_canonical(Se, 'stress'), 3)} MPa",
            "n": fmt(f["goodman"], 3), "ok": f["goodman"] >= n_t and n_y >= n_t,
        },
        "notes": notes,
    }


_feature_keys = list(FEATURES.keys())

SHAFT_FATIGUE = Calculator(
    id="shaft_fatigue",
    title="Shaft fatigue (DE-Goodman)",
    category="Shafts",
    summary="Fatigue safety factor and required diameter for a shaft under bending and torsion, "
            "with Marin-corrected endurance limit.",
    description=(
        "Distortion-energy fatigue criteria for shafts (Shigley ch. 7). Alternating and mean "
        "bending and torsion are combined into von Mises components, the endurance limit is "
        "corrected with Marin factors, and the safety factor is evaluated with DE-Goodman, "
        "DE-Gerber, DE-ASME elliptic and Soderberg. A rotating shaft with steady torque has "
        "Ma = M, Mm = 0, Ta = 0, Tm = T."
    ),
    params=[
        Param("d", "Diameter at the critical section d", dim="length", default=28, unit="mm",
              min=0, group="Geometry"),
        Param("Ma", "Alternating bending moment Ma", dim="torque", default=142.4, unit="N*m",
              group="Loads", help="Rotating shaft with fixed bending load: Ma = M."),
        Param("Mm", "Mean bending moment Mm", dim="torque", default=0, unit="N*m", group="Loads"),
        Param("Ta", "Alternating torque Ta", dim="torque", default=0, unit="N*m", group="Loads"),
        Param("Tm", "Mean torque Tm", dim="torque", default=124.3, unit="N*m", group="Loads",
              help="Steady transmitted torque goes here."),
        Param("kf_mode", "Notch / feature", kind="select", default="direct",
              options=[{"value": "direct", "label": "Enter Kf, Kfs directly"},
                       {"value": "none", "label": "No notch (Kf = 1)"}]
              + [{"value": k, "label": v[2]} for k, v in FEATURES.items()],
              group="Stress concentration"),
        Param("Kf", "Fatigue SCF Kf (bending)", default=1.58, min=1, group="Stress concentration",
              show_if={"kf_mode": ["direct"]}),
        Param("Kfs", "Fatigue SCF Kfs (torsion)", default=1.39, min=1,
              group="Stress concentration", show_if={"kf_mode": ["direct"]}),
        Param("q", "Notch sensitivity q (bending)", default=1.0, min=0, max=1,
              group="Stress concentration", show_if={"kf_mode": _feature_keys},
              help="q = 1 is conservative (Kf = Kt)."),
        Param("qs", "Notch sensitivity qs (torsion)", default=1.0, min=0, max=1,
              group="Stress concentration", show_if={"kf_mode": _feature_keys}),
        *material_params(default="c45_qt", need_E=False),
        Param("surface", "Surface finish", kind="select", default="machined",
              options=[{"value": k, "label": v[2]} for k, v in SURFACE.items()],
              group="Endurance limit"),
        Param("reliability", "Reliability", kind="select", default="0.99",
              options=[{"value": k, "label": v[1]} for k, v in RELIABILITY.items()],
              group="Endurance limit"),
        Param("kd", "Temperature factor kd", default=1.0, min=0, group="Endurance limit",
              advanced=True),
        Param("kmisc", "Miscellaneous factor kf", default=1.0, min=0, group="Endurance limit",
              advanced=True, help="Corrosion, plating, fretting, etc."),
        Param("n_target", "Target safety factor", default=1.5, min=1, group="Design"),
    ],
    outputs=[
        Output("n_goodman", "Fatigue safety factor (DE-Goodman)", primary=True, sig=3),
        Output("n_yield", "First-cycle yield safety factor", primary=True, sig=3),
        Output("d_req", "Required diameter for target n", "length", primary=True, sig=3),
        Output("Se", "Corrected endurance limit Se", "stress"),
        Output("n_gerber", "DE-Gerber safety factor", sig=3),
        Output("n_asme", "DE-ASME elliptic safety factor", sig=3),
        Output("n_soderberg", "DE-Soderberg safety factor", sig=3),
        Output("sa", "von Mises alternating stress σa'", "stress"),
        Output("sm", "von Mises mean stress σm'", "stress"),
        Output("Kf", "Kf used", sig=3),
        Output("Kfs", "Kfs used", sig=3),
        Output("ka", "Surface factor ka", sig=3),
        Output("kb", "Size factor kb", sig=3),
    ],
    compute=_compute_shaft_fatigue,
    diagram="shaft_fatigue",
    formulas=[
        r"\frac{1}{n} = \frac{16}{\pi d^3}\left\{\frac{1}{S_e}\left[4(K_fM_a)^2 + 3(K_{fs}T_a)^2\right]^{1/2} + \frac{1}{S_{ut}}\left[4(K_fM_m)^2 + 3(K_{fs}T_m)^2\right]^{1/2}\right\}",
        r"S_e = k_a k_b k_c k_d k_e k_f\, S_e'",
        r"d = \left(\frac{16n}{\pi}\left\{\frac{A}{S_e} + \frac{B}{S_{ut}}\right\}\right)^{1/3}",
    ],
    references=["Shigley's Mechanical Engineering Design, 10th ed., §6-9 (Marin factors), §7-4 (eqs. 7-7 to 7-16)",
                "Shigley Table 7-1: first-iteration stress concentration factors"],
    keywords=["shaft", "fatigue", "goodman", "gerber", "endurance limit", "marin", "rotating shaft",
              "keyway", "fillet", "shaft diameter", "infinite life", "de-goodman"],
    presets=[
        {"label": "Shigley Ex. 7-1 (rotating, steady torque)", "values": {
            "d": {"value": 28, "unit": "mm"}, "Ma": {"value": 142.4, "unit": "N*m"},
            "Mm": {"value": 0, "unit": "N*m"}, "Ta": {"value": 0, "unit": "N*m"},
            "Tm": {"value": 124.3, "unit": "N*m"}, "kf_mode": "direct", "Kf": 1.58, "Kfs": 1.39,
            "material": "custom", "material_Sy": {"value": 574, "unit": "MPa"},
            "material_Sut": {"value": 735, "unit": "MPa"}, "surface": "machined",
            "reliability": "0.99"}},
        {"label": "Gear seat with keyway", "values": {
            "d": {"value": 40, "unit": "mm"}, "Ma": {"value": 250, "unit": "N*m"},
            "Mm": {"value": 0, "unit": "N*m"}, "Ta": {"value": 0, "unit": "N*m"},
            "Tm": {"value": 300, "unit": "N*m"}, "kf_mode": "keyseat_endmill",
            "material": "42crmo4_qt"}},
    ],
)


# --------------------------------------------------------------------------
# First critical speed (Dunkerley / Rayleigh)
# --------------------------------------------------------------------------

# (βL)^2 for the first bending mode of a uniform beam
BETA_L2 = {
    "simply_supported": (math.pi ** 2, "Simply supported (bearings at both ends)"),
    "cantilever": (1.875104069 ** 2, "Cantilever (overhung)"),
    "fixed_fixed": (4.730040745 ** 2, "Fixed–fixed"),
}


def influence(xp: float, a: float, L: float, EI: float, support: str) -> float:
    """Deflection at xp due to a unit force at a."""
    if support == "simply_supported":
        if xp > a:  # mirror
            xp, a = L - xp, L - a
        b = L - a
        return b * xp * (L ** 2 - b ** 2 - xp ** 2) / (6 * EI * L)
    if support == "cantilever":
        if xp <= a:
            return xp ** 2 * (3 * a - xp) / (6 * EI)
        return a ** 2 * (3 * xp - a) / (6 * EI)
    # fixed-fixed
    if xp > a:
        xp, a = L - xp, L - a
    b = L - a
    return b ** 2 * xp ** 2 * (3 * a * L - 3 * a * xp - b * xp) / (6 * EI * L ** 3)


def _rad_to_rpm(w: float) -> float:
    return w * 60 / (2 * math.pi)


def critical_speeds(L: float, d: float, di: float, E: float, rho: float, support: str,
                    masses: List[Tuple[float, float]]) -> Dict[str, Optional[float]]:
    I = math.pi / 64 * (d ** 4 - di ** 4)
    A = math.pi / 4 * (d ** 2 - di ** 2)
    EI = E * I
    bl2 = BETA_L2[support][0]
    w_shaft = bl2 / L ** 2 * math.sqrt(EI / (rho * A))
    inv = 1 / w_shaft ** 2
    w_ray = None
    if masses:
        for m, xm in masses:
            inv += m * influence(xm, xm, L, EI, support)
        g = 9.80665
        y = [g * sum(mj * influence(xi, xj, L, EI, support) for mj, xj in masses)
             for _, xi in masses]
        num = g * sum(m * yi for (m, _), yi in zip(masses, y))
        den = sum(m * yi ** 2 for (m, _), yi in zip(masses, y))
        w_ray = math.sqrt(num / den) if den > 0 else None
    w_c = 1 / math.sqrt(inv)
    return {"w_shaft": w_shaft, "w_c": w_c, "w_ray": w_ray, "EI": EI, "rhoA": rho * A}


def _compute_critical_speed(x: Dict[str, Any]) -> Dict[str, Any]:
    L, d, di = x["L"], x["d"], x["di"]
    if L <= 0 or d <= 0:
        raise CalcError("Length and diameter must be positive.")
    if di < 0 or di >= d:
        raise CalcError("Bore must be ≥ 0 and smaller than the outer diameter.")
    support = x["support"]
    mat = resolve_material(x)
    n_op, margin = x["n_op"], x["margin"] / 100.0
    if n_op <= 0:
        raise CalcError("Operating speed must be positive.")

    masses: List[Tuple[float, float]] = []
    for i in (1, 2, 3):
        m, xm = x[f"m{i}"], x[f"x{i}"]
        if m <= 0:
            continue
        if not (0 < xm <= L) or (support != "cantilever" and xm >= L):
            raise CalcError(f"Mass {i} position must lie within the span (0 < x < L).")
        masses.append((m, xm))

    r = critical_speeds(L, d, di, mat["E"], mat["rho"], support, masses)
    n_c = _rad_to_rpm(r["w_c"])
    n_s = _rad_to_rpm(r["w_shaft"])
    n_r = _rad_to_rpm(r["w_ray"]) if r["w_ray"] else None
    ratio = n_c / n_op
    sep = (n_c - n_op) / n_op * 100

    if n_op <= n_c / (1 + margin):
        chk = check("Resonance separation", True,
                    f"Subcritical: operating speed is {fmt(ratio, 3)}× below the first critical speed.",
                    value=ratio, limit=1 + margin)
    elif n_op >= n_c * (1 + margin):
        chk = check("Resonance separation", False,
                    "Supercritical: the shaft passes through resonance during run-up. Ensure "
                    "fast acceleration and good damping, or stiffen the shaft.", warn=True,
                    value=ratio, limit=1 + margin)
    else:
        chk = check("Resonance separation", False,
                    f"Operating speed is within ±{fmt(margin * 100, 3)} % of the critical speed. "
                    "Increase diameter, shorten the span or reduce mass.",
                    value=ratio, limit=1 + margin)

    ds = linspace(0.5 * d, 2 * d, 50)
    ns = [_rad_to_rpm(critical_speeds(L, di_, di / d * di_, mat["E"], mat["rho"], support,
                                      masses)["w_c"]) for di_ in ds]

    values = {"n_crit": n_c, "ratio": ratio, "n_shaft": n_s, "sep": sep}
    if n_r:
        values["n_ray"] = n_r
    steps = [
        step("Second moment of area", r"I = \tfrac{\pi}{64}(d^4 - d_i^4)",
             math.pi / 64 * (d ** 4 - di ** 4), "inertia"),
        step("Bare shaft (continuous beam)", r"\omega_s = \frac{(\beta L)^2}{L^2}\sqrt{\frac{EI}{\rho A}}",
             n_s, "speed"),
    ]
    if masses:
        steps.append(step("Dunkerley combination",
                          r"\frac{1}{\omega_c^2} = \frac{1}{\omega_s^2} + \sum m_i\,a_{ii}", n_c, "speed"))
        if n_r:
            steps.append(step("Rayleigh (masses only)",
                              r"\omega^2 = \frac{g\sum m_i y_i}{\sum m_i y_i^2}", n_r, "speed"))
    return {
        "values": values,
        "checks": [chk],
        "steps": steps,
        "series": [series("ncrit_vs_d", "First critical speed vs diameter", ds, ns, x_label="d",
                          y_label="n_crit", x_dim="length", y_dim="speed",
                          markers=[{"x": d, "label": "current"}],
                          ref_lines=[{"y": n_op * (1 + margin),
                                      "label": f"n_op +{fmt(margin * 100, 3)} %"}])],
        "diagram": {
            "L": fmt(from_canonical(L, "length"), 4), "d": fmt(from_canonical(d, "length"), 3),
            "support": support,
            "masses": [{"pos": xm / L, "label": f"{fmt(m, 3)} kg"} for m, xm in masses],
            "n_crit": f"{fmt(n_c, 4)} rpm", "n_op": f"{fmt(n_op, 4)} rpm",
            "ok": chk["status"] == "ok",
        },
        "notes": [
            "Dunkerley gives a lower bound (conservative) on the first critical speed; Rayleigh "
            "with point masses gives an upper bound for the masses alone.",
            "Bearing and housing flexibility lower the real critical speed; keep a generous margin.",
        ],
    }


_mass_params: List[Param] = []
for _i, (_m, _x) in enumerate([(10, 300), (0, 150), (0, 450)], start=1):
    _mass_params.append(Param(f"m{_i}", f"Mass {_i} (0 = none)", dim="mass", default=_m, unit="kg",
                              min=0, group="Masses", advanced=_i > 1))
    _mass_params.append(Param(f"x{_i}", f"Mass {_i} position from left", dim="length", default=_x,
                              unit="mm", min=0, group="Masses", advanced=_i > 1))

SHAFT_CRITICAL_SPEED = Calculator(
    id="shaft_critical_speed",
    title="Shaft critical speed",
    category="Shafts",
    summary="First bending critical speed of a shaft with up to three point masses "
            "(Dunkerley / Rayleigh) and a resonance-separation check.",
    description=(
        "The bare-shaft first natural frequency comes from Euler–Bernoulli beam theory for the "
        "chosen support condition. Point masses (gears, pulleys, rotors) are combined with "
        "Dunkerley's method using exact influence coefficients, giving a conservative estimate."
    ),
    params=[
        Param("L", "Span / length L", dim="length", default=600, unit="mm", min=0, group="Geometry"),
        Param("d", "Shaft diameter d", dim="length", default=30, unit="mm", min=0, group="Geometry"),
        Param("di", "Bore diameter (0 = solid)", dim="length", default=0, unit="mm", min=0,
              group="Geometry"),
        Param("support", "Support condition", kind="select", default="simply_supported",
              options=[{"value": k, "label": v[1]} for k, v in BETA_L2.items()], group="Geometry"),
        *material_params(default="c45_n"),
        *_mass_params,
        Param("n_op", "Operating speed", dim="speed", default=1500, unit="rpm", min=0,
              group="Operation"),
        Param("margin", "Required separation (%)", default=25, min=0, group="Operation",
              help="Typical 20–25 % between operating and critical speed."),
    ],
    outputs=[
        Output("n_crit", "First critical speed", "speed", primary=True),
        Output("ratio", "Critical / operating speed", primary=True, sig=3),
        Output("n_shaft", "Bare shaft critical speed", "speed"),
        Output("n_ray", "Rayleigh estimate (masses only)", "speed"),
        Output("sep", "Separation from operating speed (%)", sig=3),
    ],
    compute=_compute_critical_speed,
    diagram="shaft_critical_speed",
    formulas=[r"\omega_s = \frac{(\beta L)^2}{L^2}\sqrt{\frac{EI}{\rho A}}",
              r"\frac{1}{\omega_c^2} = \frac{1}{\omega_s^2} + \sum_i m_i\,a_{ii}",
              r"\omega^2 = \frac{g\sum m_i y_i}{\sum m_i y_i^2}"],
    references=["Shigley's Mechanical Engineering Design, 10th ed., §7-6",
                "Blevins, Formulas for Natural Frequency and Mode Shape (beam modes)"],
    keywords=["critical speed", "whirl", "resonance", "natural frequency", "dunkerley", "rayleigh",
              "rotor dynamics", "shaft vibration"],
    presets=[
        {"label": "Fan shaft, overhung impeller", "values": {
            "support": "cantilever", "L": {"value": 250, "unit": "mm"},
            "d": {"value": 35, "unit": "mm"}, "m1": {"value": 8, "unit": "kg"},
            "x1": {"value": 250, "unit": "mm"}, "n_op": {"value": 2900, "unit": "rpm"}}},
        {"label": "Line shaft with two pulleys", "values": {
            "support": "simply_supported", "L": {"value": 1000, "unit": "mm"},
            "d": {"value": 40, "unit": "mm"}, "m1": {"value": 12, "unit": "kg"},
            "x1": {"value": 300, "unit": "mm"}, "m2": {"value": 8, "unit": "kg"},
            "x2": {"value": 700, "unit": "mm"}, "n_op": {"value": 1000, "unit": "rpm"}}},
    ],
)

CALCULATORS = [SHAFT_FATIGUE, SHAFT_CRITICAL_SPEED]
