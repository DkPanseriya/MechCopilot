"""Helical compression and torsion springs (Shigley 10th ed., ch. 10)."""
import math
from typing import Any, Dict, List

from ..core import (Calculator, CalcError, Output, Param, check, fmt, from_canonical,
                    linspace, series, step)

# Spring wire, Shigley Table 10-4 (Sut = A / d^m, A in MPa·mm^m, d in mm) and
# Table 10-5 (G, E). `kind` drives the allowable-stress fractions of Table 10-6.
WIRES: Dict[str, Dict[str, Any]] = {
    "a228": {"label": "Music wire ASTM A228", "kind": "cold_drawn", "E": 203.4e9,
             "ranges": [(0.10, 6.5, 0.145, 2211.0)], "rho": 7850.0},
    "a227": {"label": "Hard-drawn ASTM A227", "kind": "cold_drawn", "E": 197.0e9, "G": 79.3e9,
             "ranges": [(0.7, 12.7, 0.190, 1783.0)], "rho": 7850.0},
    "a229": {"label": "Oil-tempered ASTM A229", "kind": "ht", "E": 196.5e9, "G": 77.2e9,
             "ranges": [(0.5, 12.7, 0.187, 1855.0)], "rho": 7850.0},
    "a232": {"label": "Chrome-vanadium ASTM A232", "kind": "ht", "E": 203.4e9, "G": 77.2e9,
             "ranges": [(0.8, 11.1, 0.168, 2005.0)], "rho": 7850.0},
    "a401": {"label": "Chrome-silicon ASTM A401", "kind": "ht", "E": 203.4e9, "G": 77.2e9,
             "ranges": [(1.6, 9.5, 0.108, 1974.0)], "rho": 7850.0},
    "a313": {"label": "Stainless 302 ASTM A313", "kind": "ss", "E": 193.0e9, "G": 69.0e9,
             "ranges": [(0.3, 2.5, 0.146, 1867.0), (2.5, 5.0, 0.263, 2065.0),
                        (5.0, 10.0, 0.478, 2911.0)], "rho": 7900.0},
}
WIRE_OPTIONS = [{"value": k, "label": v["label"]} for k, v in WIRES.items()]

# Table 10-6: max allowable torsional stress (fraction of Sut), compression springs.
FRAC_COMP = {"cold_drawn": (0.45, 0.60), "ht": (0.50, 0.65), "ss": (0.35, 0.55)}
# Table 10-6: max allowable bending stress (fraction of Sut), torsion springs.
FRAC_BEND = {"cold_drawn": 0.80, "ht": 0.85, "ss": 0.60}


def wire_props(key: str, d: float) -> Dict[str, Any]:
    """Wire properties for wire diameter d (m). Sut in Pa."""
    w = WIRES.get(key)
    if w is None:
        raise CalcError(f"Unknown spring wire '{key}'.")
    d_mm = d * 1000
    ranges = w["ranges"]
    lo_all, hi_all = ranges[0][0], ranges[-1][1]
    rng = next((r for r in ranges if r[0] <= d_mm <= r[1]), None)
    in_range = rng is not None
    if rng is None:
        rng = ranges[0] if d_mm < lo_all else ranges[-1]
    _, _, m, A = rng
    Sut = A / d_mm ** m * 1e6
    if key == "a228":  # music-wire G depends on wire size (Table 10-5)
        G = 82.7e9 if d_mm <= 0.8 else 81.7e9 if d_mm <= 1.6 else 81.0e9 if d_mm <= 3.2 else 80.0e9
    else:
        G = w["G"]
    return {"label": w["label"], "kind": w["kind"], "Sut": Sut, "G": G, "E": w["E"],
            "rho": w["rho"], "in_range": in_range, "range_mm": (lo_all, hi_all), "A": A, "m": m}


END_TYPES = {
    "plain": "Plain",
    "plain_ground": "Plain and ground",
    "squared": "Squared (closed)",
    "squared_ground": "Squared and ground",
}

BUCKLING_ALPHA = {  # Shigley Table 10-2 end-condition constant
    "fixed_fixed": 0.5, "fixed_hinged": 0.707, "hinged_hinged": 1.0, "fixed_free": 2.0,
}


def end_geometry(ends: str, Na: float, d: float, L0: float) -> Dict[str, float]:
    """Shigley Table 10-1: total coils, solid length, pitch."""
    if ends == "plain":
        Nt, Ls, p = Na, d * (Na + 1), (L0 - d) / Na
    elif ends == "plain_ground":
        Nt, Ls, p = Na + 1, d * (Na + 1), L0 / (Na + 1)
    elif ends == "squared":
        Nt, Ls, p = Na + 2, d * (Na + 3), (L0 - 3 * d) / Na
    else:  # squared_ground
        Nt, Ls, p = Na + 2, d * (Na + 2), (L0 - 2 * d) / Na
    return {"Nt": Nt, "Ls": Ls, "p": p}


def _bergstrasser(C: float) -> float:
    return (4 * C + 2) / (4 * C - 3)


# --------------------------------------------------------------------------
# Compression spring
# --------------------------------------------------------------------------

def _compute_compression(x: Dict[str, Any]) -> Dict[str, Any]:
    d, D_in, Na, L0 = x["d"], x["D"], x["Na"], x["L0"]
    if d <= 0 or D_in <= 0 or L0 <= 0:
        raise CalcError("Wire diameter, coil diameter and free length must be positive.")
    if Na < 1:
        raise CalcError("Active coils must be at least 1.")
    D = D_in if x["D_basis"] == "mean" else D_in - d
    if D <= d:
        raise CalcError("Mean coil diameter must be larger than the wire diameter.")
    w = wire_props(x["wire"], d)
    G, E, Sut = w["G"], w["E"], w["Sut"]
    frac = FRAC_COMP[w["kind"]][1 if x["set_removed"] else 0]
    Ssy = frac * Sut

    C = D / d
    KB = _bergstrasser(C)
    k = d ** 4 * G / (8 * D ** 3 * Na)
    geo = end_geometry(x["ends"], Na, d, L0)
    Ls = geo["Ls"]
    y_s = L0 - Ls
    if y_s <= 0:
        raise CalcError("Free length is at or below the solid length — increase L0 or reduce coils.")

    if x["load_mode"] == "force":
        F = x["F"]
        y = F / k
    else:
        y = x["y"]
        F = k * y
    if F < 0 or y < 0:
        raise CalcError("Working force/deflection must be positive (compression).")

    stress = lambda force: KB * 8 * force * D / (math.pi * d ** 3)
    tau = stress(F)
    Fs = k * y_s
    tau_s = stress(Fs)
    ns = Ssy / tau if tau > 0 else float("inf")
    ns_solid = Ssy / tau_s
    F_yield = Ssy * math.pi * d ** 3 / (8 * KB * D)
    n_t = x["n_target"]

    alpha = BUCKLING_ALPHA[x["support"]]
    L0_crit = math.pi * D / alpha * math.sqrt(2 * (E - G) / (2 * G + E))
    m_active = w["rho"] * math.pi ** 2 * d ** 2 * D * Na / 4
    fn = 0.5 * math.sqrt(k / m_active)  # ends against flat parallel plates

    checks = [
        check("Working stress", ns >= n_t,
              f"τ = {fmt(tau / 1e6, 3)} MPa, n = {fmt(ns, 3)} against Ssy = {fmt(Ssy / 1e6, 3)} MPa "
              f"(target {fmt(n_t, 3)})", value=ns, limit=n_t),
        check("Goes solid safely", ns_solid >= 1.0,
              f"At solid length the stress is {fmt(tau_s / 1e6, 3)} MPa (n = {fmt(ns_solid, 3)}). "
              + ("Compressing it solid will not take a permanent set." if ns_solid >= 1
                 else "Compressing it solid will cause permanent set — add a stop or reduce L0."),
              value=ns_solid, limit=1.0),
        check("Travel to solid", y <= y_s,
              f"Working deflection {fmt(y * 1e3, 3)} mm of {fmt(y_s * 1e3, 3)} mm available."
              if y <= y_s else
              f"Working deflection {fmt(y * 1e3, 3)} mm exceeds the {fmt(y_s * 1e3, 3)} mm available before solid.",
              value=y, limit=y_s),
    ]
    if y <= y_s and y > 0:
        xi = (y_s - y) / y
        checks.append(check("Clash allowance", xi >= 0.15,
                            f"Fractional overrun to solid ξ = {fmt(xi, 2)} (Shigley recommends ≥ 0.15).",
                            warn=True, value=xi, limit=0.15))
    checks.append(check("Buckling", L0 < L0_crit,
                        f"Free length {fmt(L0 * 1e3, 3)} mm vs critical {fmt(L0_crit * 1e3, 3)} mm "
                        f"for these end conditions (α = {alpha}).",
                        warn=True, value=L0, limit=L0_crit))
    checks.append(check("Spring index", 4 <= C <= 12,
                        f"C = {fmt(C, 3)}. 4–12 is easy to manufacture; outside that range "
                        "coiling and tolerances get difficult.", warn=True, value=C))
    if not w["in_range"]:
        lo, hi = w["range_mm"]
        checks.append(check("Wire size range", False,
                            f"{w['label']} data covers {lo}–{hi} mm wire; Sut is extrapolated.",
                            warn=True))

    values = {"k": k, "tau": tau, "ns": ns, "F": F, "y": y, "C": C, "KB": KB, "Sut": Sut,
              "Ssy": Ssy, "Ls": Ls, "L_work": L0 - y, "y_s": y_s, "Fs": Fs, "tau_s": tau_s,
              "ns_solid": ns_solid, "F_yield": F_yield, "OD": D + d, "ID": D - d,
              "pitch": geo["p"], "Nt": geo["Nt"], "L0_crit": L0_crit, "fn": fn}

    notes = []
    Fmin = x["Fmin"]
    fatigue_steps = []
    if x["cyclic"] and Fmin < 0:
        raise CalcError("Minimum force must be ≥ 0 for a compression spring.")
    if x["cyclic"] and Fmin >= F:
        raise CalcError("For cyclic loading the minimum force must be below the working force.")
    if x["cyclic"]:
        Fa, Fm = (F - Fmin) / 2, (F + Fmin) / 2
        ta, tm = stress(Fa), stress(Fm)
        Ssa, Ssm = (398e6, 534e6) if x["peened"] else (241e6, 379e6)  # Zimmerli
        Ssu = 0.67 * Sut
        Sse_gerber = Ssa / (1 - (Ssm / Ssu) ** 2)
        r = ta / tm
        Ssa_load = r ** 2 * Ssu ** 2 / (2 * Sse_gerber) * (
            -1 + math.sqrt(1 + (2 * Sse_gerber / (r * Ssu)) ** 2))
        nf = Ssa_load / ta
        Sse_goodman = Ssa / (1 - Ssm / Ssu)
        nf_goodman = 1 / (ta / Sse_goodman + tm / Ssu)
        values.update({"tau_a": ta, "tau_m": tm, "nf": nf, "nf_goodman": nf_goodman})
        checks.append(check("Fatigue (Gerber–Zimmerli)", nf >= 1.5,
                            f"nf = {fmt(nf, 3)} for {fmt(Fmin, 3)}–{fmt(F, 3)} N cycling "
                            "(infinite life target ≥ 1.5).", value=nf, limit=1.5))
        fatigue_steps = [
            step("Alternating / mean shear", r"\tau_a = K_B\frac{8F_aD}{\pi d^3},\ \tau_m = K_B\frac{8F_mD}{\pi d^3}",
                 ta, "stress"),
            step("Gerber fatigue factor (Zimmerli data)",
                 r"n_f = \frac{r^2S_{su}^2}{2S_{se}\tau_a}\left[-1+\sqrt{1+\left(\frac{2S_{se}}{rS_{su}}\right)^2}\right]",
                 nf),
        ]
    else:
        notes.append("Static load. Switch on cyclic loading to get a fatigue check.")

    ys = linspace(0, y_s, 40)
    return {
        "values": values,
        "checks": checks,
        "steps": [
            step("Mean coil diameter", r"D", D, "length"),
            step("Spring index", r"C = D/d", C),
            step("Ultimate strength (wire)", r"S_{ut} = A/d^m", Sut, "stress"),
            step("Allowable torsional yield", r"S_{sy} = %.2f\,S_{ut}" % frac, Ssy, "stress"),
            step("Bergsträsser factor", r"K_B = \frac{4C+2}{4C-3}", KB),
            step("Spring rate", r"k = \frac{d^4 G}{8 D^3 N_a}", k, "stiffness"),
            step("Shear stress at working load", r"\tau = K_B\frac{8FD}{\pi d^3}", tau, "stress"),
            step("Solid length", r"L_s", Ls, "length"),
            step("Stress at solid", r"\tau_s = K_B\frac{8kD(L_0-L_s)}{\pi d^3}", tau_s, "stress"),
            step("Critical free length (buckling)",
                 r"L_{0,cr} = \frac{\pi D}{\alpha}\sqrt{\frac{2(E-G)}{2G+E}}", L0_crit, "length"),
            step("Natural frequency (ends on plates)", r"f_n = \tfrac12\sqrt{k/m_a}", fn, "frequency"),
            *fatigue_steps,
        ],
        "series": [series("F_vs_y", "Force vs deflection", ys, [k * v for v in ys],
                          x_label="y", y_label="F", x_dim="length", y_dim="force",
                          markers=[{"x": y, "label": "working"}, {"x": y_s, "label": "solid"}],
                          ref_lines=[{"y": F_yield, "label": "yield (Ssy)"}])],
        "diagram": {
            "d": fmt(from_canonical(d, "length"), 3), "D": fmt(from_canonical(D, "length"), 3),
            "OD": fmt(from_canonical(D + d, "length"), 3),
            "L0": fmt(from_canonical(L0, "length"), 3),
            "L": fmt(from_canonical(L0 - y, "length"), 3),
            "Ls": fmt(from_canonical(Ls, "length"), 3),
            "Na": fmt(Na, 3), "ends": x["ends"],
            "F": f"{fmt(F, 3)} N", "k": f"{fmt(from_canonical(k, 'stiffness'), 3)} N/mm",
            "tau": f"{fmt(tau / 1e6, 3)} MPa", "n": fmt(ns, 3), "ok": ns >= n_t,
            "ratio": max(0.0, min(1.0, (L0 - y) / L0)),
        },
        "notes": notes + ["Spring constants per Shigley Tables 10-4/10-5; verify against your wire "
                          "supplier's certificate."],
    }


COMPRESSION_SPRING = Calculator(
    id="compression_spring",
    governing=["F", "y", "d", "D", "Na", "L0"],
    title="Helical compression spring",
    category="Springs",
    summary="Rate, stress, solid length, buckling, surge frequency and Gerber–Zimmerli fatigue for a round-wire compression spring.",
    description=(
        "Round-wire helical compression spring per Shigley ch. 10. Wire strength follows "
        "Sut = A/d^m; static allowable torsional stress uses Table 10-6 (set removed or not). "
        "Checks working stress, whether it can go solid without set, travel, buckling of the "
        "free length and fatigue for a force range."
    ),
    params=[
        Param("d", "Wire diameter d", dim="length", default=2.5, unit="mm", min=0, group="Geometry"),
        Param("D_basis", "Coil diameter given as", kind="select", default="mean",
              options=[{"value": "mean", "label": "Mean diameter D"},
                       {"value": "outer", "label": "Outer diameter OD"}], group="Geometry"),
        Param("D", "Coil diameter", dim="length", default=20, unit="mm", min=0, group="Geometry"),
        Param("Na", "Active coils Na", default=8, min=1, group="Geometry"),
        Param("ends", "End type", kind="select", default="squared_ground",
              options=[{"value": k, "label": v} for k, v in END_TYPES.items()], group="Geometry"),
        Param("L0", "Free length L0", dim="length", default=60, unit="mm", min=0, group="Geometry"),
        Param("wire", "Spring wire", kind="select", default="a228", options=WIRE_OPTIONS, group="Material"),
        Param("set_removed", "Set removed (pre-set)", kind="bool", default=False, group="Material",
              help="Pre-setting raises the static allowable stress (Shigley Table 10-6)."),
        Param("load_mode", "Specify", kind="select", default="force",
              options=[{"value": "force", "label": "Working force"},
                       {"value": "deflection", "label": "Working deflection"}], group="Load"),
        Param("F", "Working (max) force F", dim="force", default=100, unit="N", min=0, group="Load",
              show_if={"load_mode": ["force"]}),
        Param("y", "Working deflection y", dim="length", default=10, unit="mm", min=0, group="Load",
              show_if={"load_mode": ["deflection"]}),
        Param("cyclic", "Cyclic loading (fatigue check)", kind="bool", default=False, group="Load"),
        Param("Fmin", "Minimum force of the cycle", dim="force", default=0, unit="N", min=0, group="Load",
              show_if={"cyclic": [True]}, help="Lower force of the load cycle (0 for 0→F cycling)."),
        Param("support", "End support (buckling)", kind="select", default="fixed_fixed",
              options=[{"value": "fixed_fixed", "label": "Both ends on flat parallel plates (α=0.5)"},
                       {"value": "fixed_hinged", "label": "One flat, one pivoted (α=0.707)"},
                       {"value": "hinged_hinged", "label": "Both ends pivoted (α=1)"},
                       {"value": "fixed_free", "label": "One clamped, one free (α=2)"}],
              group="Installation", advanced=True),
        Param("peened", "Shot peened", kind="bool", default=False, group="Load",
              show_if={"cyclic": [True]}),
        Param("n_target", "Target static safety factor", default=1.2, min=1, group="Design"),
    ],
    outputs=[
        Output("k", "Spring rate k", "stiffness", primary=True),
        Output("tau", "Shear stress τ", "stress", primary=True),
        Output("ns", "Static safety factor", primary=True, sig=3),
        Output("F", "Working force", "force"),
        Output("y", "Working deflection", "length"),
        Output("L_work", "Working length", "length"),
        Output("Ls", "Solid length", "length"),
        Output("y_s", "Deflection to solid", "length"),
        Output("Fs", "Force at solid", "force"),
        Output("ns_solid", "Safety factor at solid", sig=3),
        Output("F_yield", "Force at yield", "force"),
        Output("C", "Spring index C", sig=3),
        Output("KB", "Bergsträsser factor KB", sig=4),
        Output("Sut", "Wire Sut", "stress"),
        Output("Ssy", "Allowable Ssy", "stress"),
        Output("OD", "Outer diameter", "length"),
        Output("ID", "Inner diameter", "length"),
        Output("pitch", "Pitch", "length"),
        Output("Nt", "Total coils", sig=3),
        Output("L0_crit", "Critical free length (buckling)", "length"),
        Output("fn", "Natural (surge) frequency", "frequency"),
        Output("nf", "Fatigue factor (Gerber)", sig=3),
        Output("nf_goodman", "Fatigue factor (Goodman)", sig=3),
    ],
    compute=_compute_compression,
    diagram="compression_spring",
    formulas=[r"k = \frac{d^4G}{8D^3N_a}", r"\tau = K_B\frac{8FD}{\pi d^3},\quad K_B = \frac{4C+2}{4C-3}",
              r"S_{ut} = \frac{A}{d^m}", r"L_{0,cr} = \frac{\pi D}{\alpha}\sqrt{\frac{2(E-G)}{2G+E}}"],
    references=["Shigley's Mechanical Engineering Design, 10th ed., ch. 10 (Tables 10-1, 10-2, 10-4, 10-5, 10-6)",
                "EN 13906-1:2013 Cylindrical helical springs — compression springs"],
    keywords=["compression spring", "helical spring", "spring rate", "coil spring", "spring stress",
              "solid length", "spring buckling", "spring fatigue", "music wire"],
    presets=[
        {"label": "Shigley Ex. 10-1 (music wire)", "values": {
            "d": {"value": 0.94, "unit": "mm"}, "D_basis": "outer", "D": {"value": 11.11, "unit": "mm"},
            "Na": 10.5, "ends": "squared", "L0": {"value": 52.3, "unit": "mm"}, "wire": "a228",
            "F": {"value": 20, "unit": "N"}}},
        {"label": "Valve spring (Cr-Si, cycling)", "values": {
            "d": {"value": 4, "unit": "mm"}, "D": {"value": 28, "unit": "mm"}, "Na": 6,
            "L0": {"value": 60, "unit": "mm"}, "wire": "a401", "F": {"value": 350, "unit": "N"},
            "cyclic": True, "Fmin": {"value": 150, "unit": "N"}}},
    ],
)


# --------------------------------------------------------------------------
# Torsion spring
# --------------------------------------------------------------------------

def _compute_torsion(x: Dict[str, Any]) -> Dict[str, Any]:
    d, D, Nb, l1, l2, M = x["d"], x["D"], x["Nb"], x["l1"], x["l2"], x["M"]
    if d <= 0 or D <= d:
        raise CalcError("Mean coil diameter must exceed the wire diameter, both positive.")
    if Nb < 1:
        raise CalcError("Body turns must be at least 1.")
    if M < 0:
        raise CalcError("Moment must be positive (spring wound in the closing direction).")
    w = wire_props(x["wire"], d)
    E, Sut = w["E"], w["Sut"]
    Sy = FRAC_BEND[w["kind"]] * Sut

    C = D / d
    Ki = (4 * C ** 2 - C - 1) / (4 * C * (C - 1))
    sigma = Ki * 32 * M / (math.pi * d ** 3)
    n = Sy / sigma if sigma > 0 else float("inf")
    Na = Nb + (l1 + l2) / (3 * math.pi * D)
    k_turn = d ** 4 * E / (10.8 * D * Na)          # N·m per turn (empirical, incl. friction)
    k_rad = d ** 4 * E / (64 * D * Na)             # N·m per rad (theoretical)
    turns = M / k_turn
    angle = turns * 2 * math.pi
    D_load = Nb * D / (Nb + turns)
    ID_load = D_load - d
    M_yield = Sy * math.pi * d ** 3 / (32 * Ki)
    arbor = x["arbor"]
    n_t = x["n_target"]

    checks = [check("Bending stress", n >= n_t,
                    f"σ = {fmt(sigma / 1e6, 3)} MPa vs allowable Sy = {fmt(Sy / 1e6, 3)} MPa, "
                    f"n = {fmt(n, 3)} (target {fmt(n_t, 3)})", value=n, limit=n_t)]
    if arbor > 0:
        clearance = ID_load / arbor
        checks.append(check("Arbor clearance", clearance >= 1.1,
                            f"Coils wind down to ID {fmt(ID_load * 1e3, 3)} mm on a "
                            f"{fmt(arbor * 1e3, 3)} mm arbor (keep ≥ 10 % clearance).",
                            value=clearance, limit=1.1))
    checks.append(check("Spring index", 4 <= C <= 12, f"C = {fmt(C, 3)} (4–12 recommended).",
                        warn=True, value=C))

    ms = linspace(0, M_yield, 40)
    return {
        "values": {"sigma": sigma, "n": n, "angle": angle, "k_turn": k_turn, "k_rad": k_rad,
                   "C": C, "Ki": Ki, "Na": Na, "Sy": Sy, "Sut": Sut, "D_load": D_load,
                   "ID_load": ID_load, "M_yield": M_yield},
        "checks": checks,
        "steps": [
            step("Spring index", r"C = D/d", C),
            step("Inner-fibre correction", r"K_i = \frac{4C^2 - C - 1}{4C(C-1)}", Ki),
            step("Bending stress", r"\sigma = K_i\frac{32M}{\pi d^3}", sigma, "stress"),
            step("Allowable bending stress", r"S_y = %.2f\,S_{ut}" % FRAC_BEND[w["kind"]], Sy, "stress"),
            step("Active turns incl. legs", r"N_a = N_b + \frac{l_1 + l_2}{3\pi D}", Na),
            step("Rate per turn", r"k' = \frac{d^4E}{10.8\,D\,N_a}", k_turn, "torque", "N*mm"),
            step("Angular deflection", r"\theta = 2\pi\,M/k'", angle, "angle"),
            step("Loaded mean diameter", r"D' = \frac{N_b D}{N_b + \theta'}", D_load, "length"),
        ],
        "series": [series("M_vs_theta", "Moment vs angle", [m / k_turn * 2 * math.pi for m in ms], ms,
                          x_label="θ", y_label="M", x_dim="angle", y_dim="torque", y_unit="N*mm",
                          markers=[{"x": angle, "label": "working"}],
                          ref_lines=[{"y": M_yield, "label": "yield"}])],
        "diagram": {
            "d": fmt(d * 1e3, 3), "D": fmt(D * 1e3, 3), "Nb": fmt(Nb, 3),
            "l1": fmt(l1 * 1e3, 3), "l2": fmt(l2 * 1e3, 3),
            "M": f"{fmt(M * 1e3, 3)} N·mm", "angle": f"{fmt(math.degrees(angle), 3)}°",
            "sigma": f"{fmt(sigma / 1e6, 3)} MPa", "n": fmt(n, 3), "ok": n >= n_t,
            "angle_deg": math.degrees(angle),
        },
        "notes": ["Load the spring so it winds up (closes); unwinding raises the outer-fibre stress.",
                  "Rate uses Shigley's empirical 10.8 constant, which accounts for coil friction."],
    }


TORSION_SPRING = Calculator(
    id="torsion_spring",
    governing=["M", "d", "D", "Nb"],
    title="Helical torsion spring",
    category="Springs",
    summary="Bending stress, angular rate, wind-up angle and arbor clearance for a helical torsion spring.",
    description=(
        "Helical torsion spring per Shigley §10-12: inner-fibre bending stress with the Ki curvature "
        "factor, angular rate including leg contribution, and the coil diameter reduction under "
        "load so you can check the arbor clearance."
    ),
    params=[
        Param("d", "Wire diameter d", dim="length", default=2, unit="mm", min=0, group="Geometry"),
        Param("D", "Mean coil diameter D", dim="length", default=20, unit="mm", min=0, group="Geometry"),
        Param("Nb", "Body turns Nb", default=6, min=1, group="Geometry"),
        Param("l1", "Leg length l1", dim="length", default=25, unit="mm", min=0, group="Geometry"),
        Param("l2", "Leg length l2", dim="length", default=25, unit="mm", min=0, group="Geometry"),
        Param("wire", "Spring wire", kind="select", default="a228", options=WIRE_OPTIONS, group="Material"),
        Param("M", "Applied moment M", dim="torque", default=500, unit="N*mm", min=0, group="Load"),
        Param("arbor", "Arbor diameter (0 = none)", dim="length", default=14, unit="mm", min=0, group="Installation"),
        Param("n_target", "Target safety factor", default=1.2, min=1, group="Design"),
    ],
    outputs=[
        Output("sigma", "Bending stress σ", "stress", primary=True),
        Output("n", "Safety factor", primary=True, sig=3),
        Output("angle", "Wind-up angle", "angle", primary=True, sig=3),
        Output("k_turn", "Rate (per turn)", "torque", unit="N*mm"),
        Output("k_rad", "Theoretical rate (per rad)", "torque", unit="N*mm"),
        Output("M_yield", "Moment at yield", "torque", unit="N*mm"),
        Output("D_load", "Loaded mean diameter", "length"),
        Output("ID_load", "Loaded inner diameter", "length"),
        Output("Na", "Active turns incl. legs", sig=3),
        Output("C", "Spring index", sig=3),
        Output("Ki", "Curvature factor Ki", sig=4),
        Output("Sut", "Wire Sut", "stress"),
        Output("Sy", "Allowable bending stress", "stress"),
    ],
    compute=_compute_torsion,
    diagram="torsion_spring",
    formulas=[r"\sigma = K_i\frac{32M}{\pi d^3}", r"k' = \frac{d^4E}{10.8\,D\,N_a}",
              r"N_a = N_b + \frac{l_1+l_2}{3\pi D}"],
    references=["Shigley's Mechanical Engineering Design, 10th ed., §10-12 and Table 10-6"],
    keywords=["torsion spring", "helical torsion spring", "spring torque", "wind-up angle", "arbor"],
    presets=[{"label": "Clip / hinge spring", "values": {
        "d": {"value": 1.5, "unit": "mm"}, "D": {"value": 12, "unit": "mm"}, "Nb": 4,
        "M": {"value": 150, "unit": "N*mm"}, "arbor": {"value": 8, "unit": "mm"}}}],
)


CALCULATORS: List[Calculator] = [COMPRESSION_SPRING, TORSION_SPRING]
