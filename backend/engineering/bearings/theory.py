"""
Rolling-bearing life theory (ISO 281:2007, ISO 76).

Units: loads N, speeds rpm, dimensions mm, viscosity mm²/s, life in 10^6 rev / hours.

Sources
-------
* Basic rating life L10 = (C/P)^p, p = 3 ball / 10/3 roller — ISO 281:2007 §6–7.
* Equivalent dynamic load X/Y for single-row radial ball bearings (f0·Fa/C0 table) —
  ISO 281:2007 Table 3.
* Reliability factor a1 — ISO 281:2007 Table 12.
* Rated (reference) viscosity ν1 — ISO 281:2007 §9.3.3.2:
      n <  1000 rpm: ν1 = 45000 · n^-0.83 · dm^-0.5
      n >= 1000 rpm: ν1 =  4500 · n^-0.5  · dm^-0.5
  (confirmed against NTN Europe, "Lifetime calculation", bearingwizard.com).
* Life modification factor aISO — ISO 281:2007 eqs. (31)–(42), constants verified
  against the standard text (pdfcoffee.com mirror of ISO 281:2007, clause 9.3) and by
  checking continuity of the branches at κ = 0.4 and κ = 1:
      radial ball:   aISO = 0.1 [1 − (2.5671 − c1/κ^c2)^0.83 · (eC·Cu/P)^(1/3)]^−9.3
                     κ in [0.1,0.4): c1 = 2.2649, c2 = 0.054381
                     κ in [0.4,1):   c1 = 1.9987, c2 = 0.19087
                     κ in [1,4]:     c1 = 1.9987, c2 = 0.071739
      radial roller: aISO = 0.1 [1 − (1.5859 − c1/κ^c2) · (eC·Cu/P)^0.4]^−9.185
                     κ in [0.1,0.4): c1 = 1.3993, c2 = 0.054381
                     κ in [0.4,1):   c1 = 1.2348, c2 = 0.19087
                     κ in [1,4]:     c1 = 1.2348, c2 = 0.071739
      thrust ball / thrust roller: same with eC·Cu/(3P) and eC·Cu/(2.5P).
  κ > 4 → κ = 4; κ < 0.1 is outside the method (clamped, flagged); aISO ≤ 50.
* Contamination factor eC — ISO 281:2007 Table 13 (midpoints used here).
"""
import math
from typing import Any, Dict, Tuple

from .data import TYPES

# ISO 281 Table 3 — single row radial ball bearings, normal clearance.
_F0FA_C0 = [0.172, 0.345, 0.689, 1.03, 1.38, 2.07, 3.45, 5.17, 6.89]
_E = [0.19, 0.22, 0.26, 0.28, 0.30, 0.34, 0.38, 0.42, 0.44]
_Y = [2.30, 1.99, 1.71, 1.55, 1.45, 1.31, 1.15, 1.04, 1.00]

# ISO 281:2007 Table 12
A1: Dict[str, float] = {"90": 1.0, "95": 0.64, "96": 0.55, "97": 0.47, "98": 0.37, "99": 0.25,
                        "99.2": 0.22, "99.4": 0.19, "99.6": 0.16, "99.8": 0.12, "99.9": 0.093,
                        "99.95": 0.077}

# eC midpoints of ISO 281 Table 13, (dm < 100 mm, dm >= 100 mm)
CONTAMINATION: Dict[str, Tuple[str, float, float]] = {
    "extreme": ("Extreme cleanliness (lab conditions)", 1.0, 1.0),
    "high": ("High cleanliness (fine filtration, sealed & greased for life)", 0.7, 0.85),
    "normal": ("Normal cleanliness (shielded/greased for life, filtered oil)", 0.55, 0.7),
    "slight": ("Slight contamination", 0.4, 0.5),
    "typical": ("Typical contamination (no integral seals, coarse filter)", 0.2, 0.3),
    "severe": ("Severe contamination (poor sealing)", 0.05, 0.05),
}

# Kinematic viscosity at 100 °C for mineral oils of VI ≈ 95–100, per ISO VG grade.
VG_NU100: Dict[str, float] = {"10": 2.6, "15": 3.3, "22": 4.3, "32": 5.4, "46": 6.8, "68": 8.7,
                              "100": 11.1, "150": 14.5, "220": 18.8, "320": 23.8, "460": 30.0,
                              "680": 38.0}


def _interp(x: float, xs, ys) -> float:
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


def dgbb_factors(Fr: float, Fa: float, C0: float, f0: float) -> Dict[str, float]:
    """e, X, Y for a single-row deep groove ball bearing (ISO 281 Table 3)."""
    ratio = f0 * Fa / C0 if C0 > 0 else 0.0
    e = _interp(ratio, _F0FA_C0, _E)
    if Fa <= 0 or (Fr > 0 and Fa / Fr <= e):
        return {"e": e, "X": 1.0, "Y": 0.0, "f0FaC0": ratio}
    return {"e": e, "X": 0.56, "Y": _interp(ratio, _F0FA_C0, _Y), "f0FaC0": ratio}


class LoadError(ValueError):
    """The bearing type cannot carry this load combination."""


def equivalent_loads(b: Dict[str, Any], Fr: float, Fa: float) -> Dict[str, Any]:
    """Equivalent dynamic load P and static load P0 for bearing row `b`.

    Returns dict with P, P0, X, Y, e and `rule` (LaTeX of the rule applied).
    Raises LoadError when the type cannot carry the combination.
    """
    t = b["type"]
    if Fr < 0 or Fa < 0:
        raise LoadError("Loads must be positive magnitudes.")
    if Fr == 0 and Fa == 0:
        raise LoadError("Apply a radial and/or axial load.")
    ratio = Fa / Fr if Fr > 0 else math.inf

    if t == "dgbb":
        f = dgbb_factors(Fr, Fa, b["C0"], b.get("f0") or 13.5)
        P = f["X"] * Fr + f["Y"] * Fa
        P0 = max(0.6 * Fr + 0.5 * Fa, Fr)
        return {"P": P, "P0": P0, "X": f["X"], "Y": f["Y"], "e": f["e"],
                "rule": r"P = X F_r + Y F_a,\; e \text{ from } f_0 F_a / C_0"}
    if t == "acbb":
        e = 1.14
        X, Y = (1.0, 0.0) if ratio <= e else (0.35, 0.57)
        return {"P": X * Fr + Y * Fa, "P0": max(0.5 * Fr + 0.26 * Fa, Fr), "X": X, "Y": Y, "e": e,
                "rule": r"F_a/F_r \le 1.14:\; P = F_r;\; \text{else } P = 0.35F_r + 0.57F_a"}
    if t == "crb":
        if Fa > 0:
            raise LoadError("NU cylindrical roller bearings carry no axial load (use NJ/NUP or add a locating bearing).")
        return {"P": Fr, "P0": Fr, "X": 1.0, "Y": 0.0, "e": None, "rule": r"P = F_r"}
    if t == "trb":
        if Fr == 0:
            raise LoadError("Tapered roller bearings need a radial load; for pure axial load use a thrust bearing.")
        e, Y, Y0 = b["e"], b["Y"], b["Y0"]
        X, Yd = (1.0, 0.0) if ratio <= e else (0.4, Y)
        return {"P": X * Fr + Yd * Fa, "P0": max(0.5 * Fr + Y0 * Fa, Fr), "X": X, "Y": Yd, "e": e,
                "rule": r"F_a/F_r \le e:\; P = F_r;\; \text{else } P = 0.4F_r + Y F_a"}
    if t in ("sabb", "srb"):
        e, Y1, Y2, Y0 = b["e"], b["Y1"], b["Y2"], b["Y0"]
        x2 = 0.65 if t == "sabb" else 0.67
        if ratio <= e:
            X, Y = 1.0, Y1
        else:
            X, Y = x2, Y2
        return {"P": X * Fr + Y * Fa, "P0": Fr + Y0 * Fa, "X": X, "Y": Y, "e": e,
                "rule": (r"F_a/F_r \le e:\; P = F_r + Y_1 F_a;\; \text{else } P = "
                         + str(x2) + r"F_r + Y_2 F_a")}
    if t == "tbb":
        if Fr > 0:
            raise LoadError("Single-direction thrust ball bearings carry axial load only.")
        return {"P": Fa, "P0": Fa, "X": 0.0, "Y": 1.0, "e": None, "rule": r"P = F_a"}
    raise LoadError(f"Unknown bearing type '{t}'.")


def life_exponent(t: str) -> float:
    return TYPES[t]["p"]


def basic_life(C: float, P: float, p: float) -> float:
    """L10 in millions of revolutions."""
    return (C / P) ** p


def hours(L_mrev: float, n: float) -> float:
    return L_mrev * 1e6 / (60.0 * n) if n > 0 else math.inf


def nu_at_temperature(vg: str, temp_c: float) -> float:
    """Kinematic viscosity (mm²/s) of an ISO VG mineral oil at temperature (Walther/ASTM D341)."""
    nu40 = float(vg)
    nu100 = VG_NU100[vg]
    T1, T2 = math.log10(313.15), math.log10(373.15)
    w = lambda nu: math.log10(math.log10(nu + 0.7))
    B = (w(nu40) - w(nu100)) / (T2 - T1)
    A = w(nu40) + B * T1
    T = math.log10(temp_c + 273.15)
    return 10 ** (10 ** (A - B * T)) - 0.7


def rated_viscosity(n: float, dm: float) -> float:
    """ν1 (mm²/s), ISO 281:2007 §9.3.3.2."""
    if n <= 0:
        return math.nan
    if n < 1000:
        return 45000.0 * n ** -0.83 * dm ** -0.5
    return 4500.0 * n ** -0.5 * dm ** -0.5


def contamination_factor(level: str, dm: float) -> float:
    _, small, large = CONTAMINATION[level]
    return small if dm < 100 else large


def a_iso(kappa: float, ec: float, Cu: float, P: float, element: str, thrust: bool) -> float:
    """Life modification factor aISO (ISO 281:2007 eqs. 31–42). κ clamped to [0.1, 4]."""
    k = min(max(kappa, 0.1), 4.0)
    if thrust:
        ratio = ec * Cu / ((3.0 if element == "ball" else 2.5) * P)
    else:
        ratio = ec * Cu / P
    ratio = max(ratio, 0.0)
    if element == "ball":
        if k < 0.4:
            base = 2.5671 - 2.2649 / k ** 0.054381
        elif k < 1.0:
            base = 2.5671 - 1.9987 / k ** 0.19087
        else:
            base = 2.5671 - 1.9987 / k ** 0.071739
        inner = 1.0 - max(base, 0.0) ** 0.83 * ratio ** (1.0 / 3.0)
        expo = -9.3
    else:
        if k < 0.4:
            base = 1.5859 - 1.3993 / k ** 0.054381
        elif k < 1.0:
            base = 1.5859 - 1.2348 / k ** 0.19087
        else:
            base = 1.5859 - 1.2348 / k ** 0.071739
        inner = 1.0 - max(base, 0.0) * ratio ** 0.4
        expo = -9.185
    if inner <= 0:
        return 50.0
    return min(0.1 * inner ** expo, 50.0)


def custom_loads(Fr: float, Fa: float, X: float, Y: float) -> Dict[str, Any]:
    """User-defined X/Y factors (custom bearing). P0 conservatively taken as max(P, Fr)."""
    if Fr < 0 or Fa < 0:
        raise LoadError("Loads must be positive magnitudes.")
    if Fr == 0 and Fa == 0:
        raise LoadError("Apply a radial and/or axial load.")
    P = X * Fr + Y * Fa
    if P <= 0:
        raise LoadError("X·Fr + Y·Fa must be positive.")
    return {"P": P, "P0": max(P, Fr), "X": X, "Y": Y, "e": None, "rule": r"P = X F_r + Y F_a"}


def life_set(b: Dict[str, Any], Fr: float, Fa: float, n: float, *, fd: float = 1.0,
             a1: float = 1.0, nu: float = None, contamination: str = "normal",
             custom: Dict[str, Any] = None) -> Dict[str, Any]:
    """Everything needed to judge one bearing under one load case.

    `custom` = {"X", "Y", "element"} evaluates a user-defined bearing row `b`
    (which then needs only d, D, C, C0, Pu).
    """
    if custom:
        eq = custom_loads(Fr * fd, Fa * fd, custom["X"], custom["Y"])
        element, thrust = custom["element"], False
        p = 3.0 if element == "ball" else 10 / 3
    else:
        eq = equivalent_loads(b, Fr * fd, Fa * fd)
        t = b["type"]
        element, thrust, p = TYPES[t]["element"], TYPES[t]["thrust"], life_exponent(t)
    P = eq["P"]
    L10 = basic_life(b["C"], P, p)
    dm = 0.5 * (b["d"] + b["D"])
    out = {**eq, "p": p, "L10": L10, "L10h": hours(L10, n), "dm": dm,
           "s0": b["C0"] / eq["P0"] if eq["P0"] > 0 else math.inf}
    if nu is not None and nu > 0 and n > 0:
        nu1 = rated_viscosity(n, dm)
        kappa = nu / nu1
        ec = contamination_factor(contamination, dm)
        a = a_iso(kappa, ec, b["Pu"], P, element, thrust)
        out.update({"nu1": nu1, "kappa": kappa, "ec": ec, "aISO": a,
                    "Lnm": a1 * a * L10, "Lnmh": hours(a1 * a * L10, n)})
    return out
