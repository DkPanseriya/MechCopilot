"""High-cycle fatigue (stress-life) and stress concentration. Shigley 10th ed., ch. 6."""
import math
from typing import Any, Dict, List, Optional, Tuple

from ..core import (Calculator, CalcError, Output, Param, check, fmt, linspace, series, step)
from ..materials import BY_ID, material_params, resolve_material

# Marin surface factor ka = a·Sut^b (Sut in MPa), Shigley Table 6-2.
SURFACE = {
    "ground": ("Ground", 1.58, -0.085),
    "machined": ("Machined or cold-drawn", 4.51, -0.265),
    "hot_rolled": ("Hot-rolled", 57.7, -0.718),
    "as_forged": ("As-forged", 272.0, -0.995),
}
# Reliability factor ke, Shigley Table 6-5.
RELIABILITY = {"50": 1.000, "90": 0.897, "95": 0.868, "99": 0.814, "99.9": 0.753,
               "99.99": 0.702, "99.999": 0.659, "99.9999": 0.620}
LOAD_KC = {"bending": 1.0, "axial": 0.85, "torsion": 0.59}


def size_factor(d_mm: float) -> Tuple[float, bool]:
    """kb for rotating round sections in bending/torsion (Shigley Eq. 6-20)."""
    if d_mm <= 2.79:
        return 1.0, False
    if d_mm <= 51:
        return 1.24 * d_mm ** -0.107, True
    if d_mm <= 254:
        return 1.51 * d_mm ** -0.157, True
    return 1.51 * 254 ** -0.157, False


def temperature_factor(T_c: float) -> Tuple[float, bool]:
    """kd (Shigley Eq. 6-27, fit valid 70–1000 °F)."""
    TF = T_c * 9 / 5 + 32
    if TF <= 70:
        return 1.0, True
    TFc = min(TF, 1000)
    kd = (0.975 + 0.432e-3 * TFc - 0.115e-5 * TFc ** 2 + 0.104e-8 * TFc ** 3
          - 0.595e-12 * TFc ** 4)
    return kd, TF <= 1000


def fatigue_fraction(Sut_mpa: float) -> float:
    """f at 10^3 cycles (Shigley Eq. 6-10 in SI form, valid 490–1400 MPa)."""
    if Sut_mpa < 490:
        return 0.9
    s = min(Sut_mpa, 1400)
    return 1.06 - 4.1e-4 * s + 1.5e-7 * s ** 2


def mean_stress_factors(sa: float, sm: float, Se: float, Sut: float, Sy: float) -> Dict[str, float]:
    inf = float("inf")
    if sa <= 0 and sm <= 0:
        return {"goodman": inf, "gerber": inf, "asme": inf, "soderberg": inf, "langer": inf}
    if sm <= 0:  # compressive mean stress: Shigley takes n = Se/σa
        n = Se / sa if sa > 0 else inf
        return {"goodman": n, "gerber": n, "asme": n, "soderberg": n,
                "langer": Sy / (sa + abs(sm)) if (sa + abs(sm)) > 0 else inf}
    goodman = 1 / (sa / Se + sm / Sut)
    if sa > 0:
        gerber = 0.5 * (Sut / sm) ** 2 * (sa / Se) * (
            -1 + math.sqrt(1 + (2 * sm * Se / (Sut * sa)) ** 2))
    else:
        gerber = Sut / sm
    asme = 1 / math.sqrt((sa / Se) ** 2 + (sm / Sy) ** 2)
    soderberg = 1 / (sa / Se + sm / Sy)
    langer = Sy / (sa + sm)
    return {"goodman": goodman, "gerber": gerber, "asme": asme, "soderberg": soderberg,
            "langer": langer}


CRITERIA = {"goodman": "Modified Goodman", "gerber": "Gerber", "asme": "ASME elliptic",
            "soderberg": "Soderberg"}

NO_ENDURANCE = ("Aluminium Alloy", "Copper Alloy", "Engineering Plastic",
                "High-Performance Plastic", "Thermoplastic", "3D Printing")


def _compute_fatigue(x: Dict[str, Any]) -> Dict[str, Any]:
    mat = resolve_material(x)
    sa_nom, sm_nom, Kf = x["sa"], x["sm"], x["Kf"]
    if sa_nom < 0:
        raise CalcError("Alternating stress amplitude must be ≥ 0.")
    if Kf < 1:
        raise CalcError("Fatigue stress-concentration factor Kf must be ≥ 1.")
    load = x["load"]
    torsion = load == "torsion"
    # For torsion, inputs are shear stresses; compare with shear strengths.
    Sut = mat["Sut"] * (0.67 if torsion else 1.0)
    Sy = mat["Sy"] * (0.577 if torsion else 1.0)
    Sut_mpa = mat["Sut"] / 1e6

    Se_prime = 0.5 * mat["Sut"] if Sut_mpa <= 1400 else 700e6
    _, a, b = SURFACE[x["surface"]]
    ka = a * Sut_mpa ** b
    d_mm = x["d"] * 1000
    if load == "axial":
        kb, kb_ok = 1.0, True
    else:
        de = d_mm if x["rotating"] else 0.370 * d_mm
        kb, kb_ok = size_factor(de)
    kc = LOAD_KC[load]
    kd, kd_ok = temperature_factor(x["temp"])
    ke = RELIABILITY[x["reliability"]]
    kf = x["k_misc"]
    Se = ka * kb * kc * kd * ke * kf * Se_prime

    sa, sm = Kf * sa_nom, Kf * sm_nom
    ns = mean_stress_factors(sa, sm, Se, Sut, Sy)
    crit = x["criterion"]
    nf = ns[crit]
    ny = ns["langer"]

    # Finite life via Basquin with Goodman-equivalent reversed stress.
    f = fatigue_fraction(Sut_mpa)
    aS = (f * Sut) ** 2 / Se
    bS = -math.log10(f * Sut / Se) / 3
    s_rev = sa / (1 - sm / Sut) if 0 < sm < Sut else sa
    if sm >= Sut:
        raise CalcError("Mean stress at or above ultimate strength — the part fails statically.")
    if s_rev <= Se:
        N = float("inf")
    else:
        N = (s_rev / aS) ** (1 / bS)

    n_t = x["n_target"]
    checks = [check(f"Fatigue ({CRITERIA[crit]})", nf >= n_t,
                    f"nf = {fmt(nf, 3)} (target {fmt(n_t, 3)}); Se = {fmt(Se / 1e6, 4)} MPa",
                    value=nf, limit=n_t),
              check("First-cycle yield (Langer)", ny >= 1.0,
                    f"ny = {fmt(ny, 3)}: peak stress {fmt((sa + abs(sm)) / 1e6, 4)} MPa vs Sy "
                    f"{fmt(Sy / 1e6, 4)} MPa", value=ny, limit=1.0)]
    if math.isfinite(N):
        checks.append(check("Life", N >= 1e6,
                            f"Finite life ≈ {fmt(N, 3)} cycles (Basquin, Goodman-equivalent "
                            f"σrev = {fmt(s_rev / 1e6, 4)} MPa).", warn=True, value=N, limit=1e6))
        if N < 1e3:
            checks.append(check("Low-cycle regime", False,
                                "Below 10³ cycles the stress-life method is not valid; use strain-life.",
                                warn=True))
    sub = BY_ID.get(mat["id"], {}).get("sub_category", "")
    if sub in NO_ENDURANCE:
        checks.append(check("No endurance limit", False,
                            f"{mat['name']} has no true endurance limit; Se' = 0.5·Sut is a steel "
                            "rule. Use the fatigue strength at 5×10⁸ cycles from supplier data.",
                            warn=True))
    if not kb_ok:
        checks.append(check("Size factor range", False,
                            "Diameter outside 2.79–254 mm; kb clamped.", warn=True))
    if not kd_ok:
        checks.append(check("Temperature range", False,
                            "Temperature above ~540 °C: creep governs, kd fit not valid.", warn=True))

    # S–N curve (log–log).
    Ns = [10 ** (3 + i * 0.1) for i in range(51)]  # 1e3 .. 1e8
    Ss = [min(aS * n ** bS, f * Sut) if n <= 1e6 else Se for n in Ns]
    Ss = [max(s, Se) for s in Ss]
    op_N = N if math.isfinite(N) else 1e7
    sn = [
        series("sn", "S–N curve", Ns, Ss, x_label="N", y_label="S", y_dim="stress",
               x_scale="log", y_scale="log", group="S–N curve"),
        series("sn_point", "Operating point", [op_N], [max(s_rev, 1e3)], x_label="N", y_label="S",
               y_dim="stress", kind="scatter", x_scale="log", y_scale="log", group="S–N curve"),
    ]
    # Haigh diagram.
    xm = linspace(0, Sut, 40)
    haigh = [
        series("goodman", "Goodman", [0, Sut], [Se, 0], x_label="σm", y_label="σa",
               x_dim="stress", y_dim="stress", group="Haigh diagram"),
        series("gerber", "Gerber", xm, [Se * (1 - (v / Sut) ** 2) for v in xm], x_label="σm",
               y_label="σa", x_dim="stress", y_dim="stress", group="Haigh diagram"),
        series("asme", "ASME elliptic", [v for v in xm if v <= Sy],
               [Se * math.sqrt(max(0.0, 1 - (v / Sy) ** 2)) for v in xm if v <= Sy],
               x_label="σm", y_label="σa", x_dim="stress", y_dim="stress", group="Haigh diagram"),
        series("langer", "Langer (yield)", [0, Sy], [Sy, 0], x_label="σm", y_label="σa",
               x_dim="stress", y_dim="stress", group="Haigh diagram"),
        series("op", "Operating point", [max(sm, 0.0)], [sa], x_label="σm", y_label="σa",
               x_dim="stress", y_dim="stress", kind="scatter", group="Haigh diagram"),
    ]

    sym = "\\tau" if torsion else "\\sigma"
    return {
        "values": {"Se": Se, "nf": nf, "N": N, "ny": ny, "n_goodman": ns["goodman"],
                   "n_gerber": ns["gerber"], "n_asme": ns["asme"], "n_soderberg": ns["soderberg"],
                   "Se_prime": Se_prime, "ka": ka, "kb": kb, "kc": kc, "kd": kd, "ke": ke,
                   "s_rev": s_rev, "sa_eff": sa, "sm_eff": sm, "f": f},
        "checks": checks,
        "steps": [
            step("Rotating-beam endurance limit", r"S_e' = 0.5\,S_{ut}", Se_prime, "stress"),
            step("Surface factor", r"k_a = a\,S_{ut}^{\,b}", ka),
            step("Size factor", r"k_b = 1.24\,d^{-0.107}" if d_mm <= 51 else r"k_b = 1.51\,d^{-0.157}", kb),
            step("Load factor", r"k_c", kc),
            step("Temperature factor", r"k_d", kd),
            step("Reliability factor", r"k_e", ke),
            step("Corrected endurance limit", r"S_e = k_ak_bk_ck_dk_ek_f\,S_e'", Se, "stress"),
            step("Effective stresses", sym + r"_a = K_f" + sym + r"_{a,nom}", sa, "stress"),
            step("Goodman factor", r"\frac{1}{n_f} = \frac{" + sym + r"_a}{S_e} + \frac{" + sym + r"_m}{S_{ut}}",
                 ns["goodman"]),
            step("Equivalent reversed stress", sym + r"_{rev} = \frac{" + sym + r"_a}{1 - " + sym + r"_m/S_{ut}}",
                 s_rev, "stress"),
            step("Life (Basquin)", r"N = \left(\frac{" + sym + r"_{rev}}{a}\right)^{1/b},\ a = \frac{(fS_{ut})^2}{S_e},\ b = -\tfrac13\log\frac{fS_{ut}}{S_e}",
                 N if math.isfinite(N) else None),
        ],
        "series": sn + haigh,
        "diagram": {
            "sa": f"{fmt(sa / 1e6, 4)} MPa", "sm": f"{fmt(sm / 1e6, 4)} MPa",
            "smax": f"{fmt((sm + sa) / 1e6, 4)} MPa", "smin": f"{fmt((sm - sa) / 1e6, 4)} MPa",
            "R": fmt((sm - sa) / (sm + sa), 3) if (sm + sa) != 0 else "–",
            "ratio": (sa / (abs(sm) + sa)) if (abs(sm) + sa) > 0 else 1.0,
            "mean_frac": (sm / (abs(sm) + sa)) if (abs(sm) + sa) > 0 else 0.0,
            "nf": fmt(nf, 3), "ok": nf >= n_t, "life": "∞" if not math.isfinite(N) else f"{fmt(N, 3)} cycles",
            "shear": torsion,
        },
        "notes": ["Enter nominal stresses at the critical section; Kf scales both alternating and "
                  "mean stress (conservative for ductile materials).",
                  "For combined loading, enter von Mises equivalent alternating and mean stresses "
                  "with load type 'bending'."],
    }


FATIGUE = Calculator(
    id="fatigue_life",
    title="Fatigue strength & life (S–N)",
    category="Fatigue",
    summary="Marin-corrected endurance limit, Goodman/Gerber/ASME/Soderberg safety factors and finite life from the S–N curve.",
    description=(
        "Stress-life method of Shigley ch. 6: corrects the rotating-beam endurance limit with the "
        "Marin factors, applies a mean-stress criterion for the fatigue safety factor, checks "
        "first-cycle yield (Langer) and estimates finite life with Basquin's equation."
    ),
    params=[
        *material_params(default="steel_1045_cd", need_E=False),
        Param("sa", "Alternating stress σa (nominal)", dim="stress", default=90, unit="MPa", min=0, group="Stresses"),
        Param("sm", "Mean stress σm (nominal)", dim="stress", default=80, unit="MPa", group="Stresses"),
        Param("Kf", "Fatigue SCF Kf", default=1.0, min=1, group="Stresses",
              help="Use the stress-concentration calculator to get Kf from geometry."),
        Param("load", "Load type", kind="select", default="bending",
              options=[{"value": "bending", "label": "Bending"}, {"value": "axial", "label": "Axial"},
                       {"value": "torsion", "label": "Torsion (inputs are shear stresses)"}],
              group="Marin factors"),
        Param("surface", "Surface finish", kind="select", default="machined",
              options=[{"value": k, "label": v[0]} for k, v in SURFACE.items()], group="Marin factors"),
        Param("d", "Section diameter (size factor)", dim="length", default=25, unit="mm", min=0,
              group="Marin factors"),
        Param("rotating", "Rotating section", kind="bool", default=True, group="Marin factors",
              help="Non-rotating round sections use the equivalent diameter 0.370·d."),
        Param("reliability", "Reliability (%)", kind="select", default="99",
              options=[{"value": k, "label": f"{k} %"} for k in RELIABILITY], group="Marin factors"),
        Param("temp", "Operating temperature", dim="temperature", default=20, unit="degC",
              group="Marin factors", advanced=True),
        Param("k_misc", "Miscellaneous factor kf", default=1.0, min=0, group="Marin factors",
              advanced=True, help="Corrosion, plating, fretting… (≤ 1)."),
        Param("criterion", "Mean-stress criterion", kind="select", default="goodman",
              options=[{"value": k, "label": v} for k, v in CRITERIA.items()], group="Design"),
        Param("n_target", "Target fatigue safety factor", default=1.5, min=1, group="Design"),
    ],
    outputs=[
        Output("nf", "Fatigue safety factor", primary=True, sig=3),
        Output("Se", "Endurance limit Se", "stress", primary=True),
        Output("N", "Life (cycles)", primary=True, sig=3),
        Output("ny", "Yield factor (Langer)", sig=3),
        Output("n_goodman", "n — Goodman", sig=3),
        Output("n_gerber", "n — Gerber", sig=3),
        Output("n_asme", "n — ASME elliptic", sig=3),
        Output("n_soderberg", "n — Soderberg", sig=3),
        Output("s_rev", "Equivalent reversed stress", "stress"),
        Output("Se_prime", "Uncorrected Se'", "stress"),
        Output("ka", "ka surface", sig=3), Output("kb", "kb size", sig=3),
        Output("kc", "kc load", sig=3), Output("kd", "kd temperature", sig=3),
        Output("ke", "ke reliability", sig=3), Output("f", "Fatigue fraction f", sig=3),
    ],
    compute=_compute_fatigue,
    diagram="fatigue_life",
    formulas=[r"S_e = k_ak_bk_ck_dk_ek_f\,S_e'", r"\frac{1}{n_f} = \frac{\sigma_a}{S_e} + \frac{\sigma_m}{S_{ut}}",
              r"N = \left(\frac{\sigma_{rev}}{a}\right)^{1/b}"],
    references=["Shigley's Mechanical Engineering Design, 10th ed., §6-7 to 6-14, Tables 6-2, 6-5, 6-7",
                "Norton, Machine Design, 5th ed., ch. 6"],
    keywords=["fatigue", "endurance limit", "goodman", "gerber", "soderberg", "s-n curve",
              "fatigue life", "marin factors", "alternating stress", "infinite life"],
    presets=[
        {"label": "Rotating shaft, reversed bending", "values": {
            "sa": {"value": 150, "unit": "MPa"}, "sm": {"value": 0, "unit": "MPa"},
            "material": "42crmo4_qt", "d": {"value": 40, "unit": "mm"}}},
        {"label": "Bracket, pulsating load (finite life)", "values": {
            "sa": {"value": 200, "unit": "MPa"}, "sm": {"value": 200, "unit": "MPa"},
            "material": "steel_1045_cd", "load": "axial", "surface": "hot_rolled", "Kf": 1.3}},
    ],
)


# --------------------------------------------------------------------------
# Stress concentration
# --------------------------------------------------------------------------
# Kt = C1 + C2(2h/D) + C3(2h/D)^2 + C4(2h/D)^3, coefficients in √(h/r) and h/r.
# Curve fits after Peterson as tabulated in Roark's Formulas for Stress and Strain
# (Table 17.1). Each entry: list of (h/r range, [C1..C4] as (a, b·√(h/r), c·h/r)).
_FIT = {
    ("stepped", "tension"): [((0.1, 2.0), [(0.926, 1.157, -0.099), (0.012, -3.036, 0.961),
                                           (-0.302, 3.977, -1.744), (0.365, -2.098, 0.878)]),
                             ((2.0, 20.0), [(1.200, 0.860, -0.022), (-1.805, -0.346, -0.038),
                                            (2.198, -0.486, 0.165), (-0.593, -0.028, -0.106)])],
    ("stepped", "bending"): [((0.1, 2.0), [(0.947, 1.206, -0.131), (0.022, -3.405, 0.915),
                                           (0.869, 1.777, -0.555), (-0.810, 0.422, -0.260)]),
                             ((2.0, 20.0), [(1.232, 0.832, -0.008), (-3.813, 0.968, -0.260),
                                            (7.423, -4.868, 0.869), (-3.839, 3.070, -0.600)])],
    ("stepped", "torsion"): [((0.25, 4.0), [(0.905, 0.783, -0.075), (-0.437, -1.969, 0.553),
                                            (1.557, 1.073, -0.578), (-1.061, 0.171, 0.086)])],
    ("groove", "tension"): [((0.1, 2.0), [(0.455, 3.354, -0.769), (3.129, -15.955, 7.404),
                                          (-6.909, 29.286, -16.104), (4.325, -16.685, 9.469)]),
                            ((2.0, 50.0), [(0.935, 1.922, 0.004), (0.552, -5.327, 0.086),
                                           (-0.754, 6.281, -0.121), (0.267, -2.876, 0.031)])],
    ("groove", "bending"): [((0.25, 2.0), [(0.594, 2.958, -0.520), (0.422, -10.545, 2.692),
                                           (0.501, 14.375, -4.486), (-0.613, -6.573, 2.177)]),
                            ((2.0, 50.0), [(0.965, 1.926, 0.0), (-2.773, -4.414, -0.017),
                                           (4.785, 4.681, 0.096), (-1.995, -2.241, -0.074)])],
    ("groove", "torsion"): [((0.25, 2.0), [(1.245, 0.264, 0.491), (-3.030, 3.269, -2.051),
                                           (3.432, -6.513, 3.360), (-1.647, 2.980, -1.800)]),
                            ((2.0, 50.0), [(1.651, 0.614, 0.040), (-4.794, -0.314, -0.217),
                                           (8.457, -0.962, 0.389), (-4.314, 0.662, -0.212)])],
}


def kt_round(kind: str, load: str, D: float, d: float, r: float) -> Tuple[float, bool]:
    """Kt for stepped bar (kind='stepped') or U-groove (kind='groove'). Returns (Kt, in_range)."""
    h = (D - d) / 2
    hr = h / r
    ranges = _FIT[(kind, load)]
    lo_all, hi_all = ranges[0][0][0], ranges[-1][0][1]
    in_range = lo_all <= hr <= hi_all
    hr_c = min(max(hr, lo_all), hi_all)
    coeffs = next(c for (lo, hi), c in ranges if lo <= hr_c <= hi)
    s = math.sqrt(hr_c)
    C = [a + b * s + c * hr_c for (a, b, c) in coeffs]
    xr = 2 * h / D
    kt = C[0] + C[1] * xr + C[2] * xr ** 2 + C[3] * xr ** 3
    return max(kt, 1.0), in_range


def kt_plate_hole(d_hole: float, W: float) -> float:
    """Finite-width plate with central hole in tension, Kt on the net section."""
    x = d_hole / W
    return 3.00 - 3.13 * x + 3.66 * x ** 2 - 1.53 * x ** 3


def neuber_sqrt_a(Sut_mpa: float, torsion: bool) -> Tuple[float, bool]:
    """Neuber constant √a in √mm (Shigley Eq. 6-35, fit valid 50–250 kpsi)."""
    S = Sut_mpa / 6.894757
    ok = 50 <= S <= 250
    S = min(max(S, 50), 250)
    if torsion:
        sa = 0.190 - 2.51e-3 * S + 1.35e-5 * S ** 2 - 2.67e-8 * S ** 3
    else:
        sa = 0.246 - 3.08e-3 * S + 1.51e-5 * S ** 2 - 2.67e-8 * S ** 3
    return sa * math.sqrt(25.4), ok


GEOMETRIES = {
    "stepped": "Stepped round bar, shoulder fillet",
    "groove": "Round bar with U-groove",
    "plate_hole": "Plate with central hole (tension)",
}


def _compute_scf(x: Dict[str, Any]) -> Dict[str, Any]:
    geo = x["geometry"]
    mat = resolve_material(x)
    load = "tension" if geo == "plate_hole" else x["load"]
    checks = []
    if geo == "plate_hole":
        W, dh = x["W"], x["dh"]
        if W <= 0 or dh <= 0 or dh >= W:
            raise CalcError("Plate needs 0 < hole diameter < width.")
        kt = kt_plate_hole(dh, W)
        r = dh / 2
        ratio_label, ratio = "d/W", dh / W
        in_range = ratio <= 0.65
        xs = linspace(0.01, 0.65, 50)
        ys = [kt_plate_hole(v * W, W) for v in xs]
        sweep = series("kt_curve", "Kt vs d/W", xs, ys, x_label="d/W", y_label="Kt",
                       markers=[{"x": ratio, "label": "current"}])
        extra = {"hr": None, "Dd": None}
    else:
        D, d, r = x["D"], x["d"], x["r"]
        if d <= 0 or D <= d or r <= 0:
            raise CalcError("Need D > d > 0 and a positive radius.")
        kt, in_range = kt_round(geo, load, D, d, r)
        ratio_label, ratio = "r/d", r / d
        rs = linspace(max(0.01, 0.2 * r / d), max(0.3, 2 * r / d), 50)
        ys = [kt_round(geo, load, D, d, v * d)[0] for v in rs]
        sweep = series("kt_curve", f"Kt vs r/d (D/d = {fmt(D / d, 3)})", rs, ys,
                       x_label="r/d", y_label="Kt", markers=[{"x": ratio, "label": "current"}])
        extra = {"hr": (D - d) / 2 / r, "Dd": D / d}
    sqa, sut_ok = neuber_sqrt_a(mat["Sut"] / 1e6, load == "torsion")
    q = 1 / (1 + sqa / math.sqrt(r * 1000))
    kf = 1 + q * (kt - 1)

    if not in_range:
        checks.append(check("Curve-fit range", False,
                            "Geometry is outside the fitted range of the Kt curve; value is "
                            "extrapolated — confirm with Peterson's charts or FEA.", warn=True))
    if not sut_ok:
        checks.append(check("Neuber constant range", False,
                            "Material strength outside 345–1720 MPa; notch sensitivity extrapolated.",
                            warn=True))
    checks.append(check("Notch severity", kf < 2.5,
                        f"Kf = {fmt(kf, 3)}. A larger radius is the cheapest way to cut Kf.",
                        warn=True, value=kf, limit=2.5))

    values = {"kt": kt, "kf": kf, "q": q, "sqrt_a": sqa / 1000 ** 0.5, "ratio": ratio}
    if extra["hr"] is not None:
        values.update({"hr": extra["hr"], "Dd": extra["Dd"]})

    nominal = {
        "tension": r"\sigma_0 = \frac{4F}{\pi d^2}", "bending": r"\sigma_0 = \frac{32M}{\pi d^3}",
        "torsion": r"\tau_0 = \frac{16T}{\pi d^3}",
    }[load] if geo != "plate_hole" else r"\sigma_0 = \frac{F}{(W-d)t}"
    return {
        "values": values,
        "checks": checks,
        "steps": [
            step("Nominal stress basis", nominal),
            step("Theoretical SCF", r"K_t = C_1 + C_2\frac{2h}{D} + C_3\left(\frac{2h}{D}\right)^2 + C_4\left(\frac{2h}{D}\right)^3"
                 if geo != "plate_hole" else r"K_t = 3 - 3.13\frac{d}{W} + 3.66\left(\frac{d}{W}\right)^2 - 1.53\left(\frac{d}{W}\right)^3",
                 kt),
            step("Neuber constant", r"\sqrt{a}", sqa / 1000 ** 0.5, "dimensionless"),
            step("Notch sensitivity", r"q = \frac{1}{1 + \sqrt{a}/\sqrt{r}}", q),
            step("Fatigue SCF", r"K_f = 1 + q(K_t - 1)", kf),
        ],
        "series": [sweep],
        "diagram": {
            "geometry": geo, "load": load,
            "D": fmt(x["D"] * 1e3, 3), "d": fmt(x["d"] * 1e3, 3), "r": fmt(x["r"] * 1e3, 3),
            "W": fmt(x["W"] * 1e3, 3), "dh": fmt(x["dh"] * 1e3, 3),
            "kt": fmt(kt, 3), "kf": fmt(kf, 3), "ok": kf < 2.5,
        },
        "notes": ["Kt applies to the nominal stress on the smaller section. Use Kf in fatigue "
                  "(feed it into the fatigue calculator); for static loading of ductile parts Kt "
                  "is usually not applied."],
    }


STRESS_CONCENTRATION = Calculator(
    id="stress_concentration",
    title="Stress concentration Kt and Kf",
    category="Fatigue",
    summary="Kt for shoulder fillets, U-grooves and plate holes from Peterson curve fits, plus notch sensitivity and fatigue Kf.",
    description=(
        "Theoretical stress-concentration factors from Peterson's data as polynomial fits "
        "(Roark Table 17.1), and the Neuber/Kuhn–Hardrath notch sensitivity of Shigley Eq. 6-35 "
        "to turn Kt into the fatigue factor Kf."
    ),
    params=[
        Param("geometry", "Feature", kind="select", default="stepped",
              options=[{"value": k, "label": v} for k, v in GEOMETRIES.items()], group="Geometry"),
        Param("load", "Load", kind="select", default="bending",
              options=[{"value": "tension", "label": "Tension"}, {"value": "bending", "label": "Bending"},
                       {"value": "torsion", "label": "Torsion"}], group="Geometry",
              show_if={"geometry": ["stepped", "groove"]}),
        Param("D", "Large / outer diameter D", dim="length", default=38, unit="mm", min=0, group="Geometry",
              show_if={"geometry": ["stepped", "groove"]}),
        Param("d", "Small / root diameter d", dim="length", default=32, unit="mm", min=0, group="Geometry",
              show_if={"geometry": ["stepped", "groove"]}),
        Param("r", "Fillet / groove radius r", dim="length", default=3, unit="mm", min=0, group="Geometry",
              show_if={"geometry": ["stepped", "groove"]}),
        Param("W", "Plate width W", dim="length", default=60, unit="mm", min=0, group="Geometry",
              show_if={"geometry": ["plate_hole"]}),
        Param("dh", "Hole diameter", dim="length", default=15, unit="mm", min=0, group="Geometry",
              show_if={"geometry": ["plate_hole"]}),
        *material_params(default="steel_1045_cd", need_E=False),
    ],
    outputs=[
        Output("kt", "Theoretical Kt", primary=True, sig=3),
        Output("kf", "Fatigue Kf", primary=True, sig=3),
        Output("q", "Notch sensitivity q", primary=True, sig=3),
        Output("ratio", "Radius / width ratio", sig=3),
        Output("hr", "h/r", sig=3),
        Output("Dd", "D/d", sig=3),
        Output("sqrt_a", "Neuber √a (√m)", sig=3),
    ],
    compute=_compute_scf,
    diagram="stress_concentration",
    formulas=[r"K_f = 1 + q(K_t - 1)", r"q = \frac{1}{1 + \sqrt{a}/\sqrt{r}}"],
    references=["Pilkey & Pilkey, Peterson's Stress Concentration Factors, 3rd ed.",
                "Roark's Formulas for Stress and Strain, Table 17.1 (curve fits)",
                "Shigley's Mechanical Engineering Design, 10th ed., §6-10, Fig. A-15, Eq. 6-35"],
    keywords=["stress concentration", "kt", "kf", "notch sensitivity", "fillet", "shoulder",
              "groove", "hole", "peterson"],
    presets=[
        {"label": "Shigley Ex. 6-6 shoulder (38/32, r = 3)", "values": {
            "geometry": "stepped", "load": "bending", "D": {"value": 38, "unit": "mm"},
            "d": {"value": 32, "unit": "mm"}, "r": {"value": 3, "unit": "mm"},
            "material": "custom", "material_Sy": {"value": 580, "unit": "MPa"},
            "material_Sut": {"value": 690, "unit": "MPa"}}},
        {"label": "Retaining-ring groove", "values": {
            "geometry": "groove", "load": "bending", "D": {"value": 30, "unit": "mm"},
            "d": {"value": 28.6, "unit": "mm"}, "r": {"value": 0.2, "unit": "mm"}}},
    ],
)


CALCULATORS: List[Calculator] = [FATIGUE, STRESS_CONCENTRATION]
