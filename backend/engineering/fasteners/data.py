"""
ISO metric fastener data. Values are nominal/typical figures from the cited
standards (dimensions in mm, strengths in MPa). Verify critical designs against
the current edition of each standard and the supplier's certificate.

  ISO 261 / 262 / 724  metric thread geometry      ISO 898-1  carbon/alloy steel classes
  ISO 3506-1           stainless steel classes      ISO 4762   socket head cap screws
  ISO 4017 / 4014      hex head bolts/screws        ISO 10642  countersunk socket screws
  ISO 4032             hex nuts                     ISO 7089   plain washers
  ISO 273              clearance holes
"""
import math
from typing import Any, Dict, List, Optional

# Nominal diameter -> coarse pitch (ISO 261, first & second choice sizes M2–M48).
COARSE_PITCH: Dict[str, float] = {
    "M2": 0.4, "M2.5": 0.45, "M3": 0.5, "M4": 0.7, "M5": 0.8, "M6": 1.0, "M8": 1.25,
    "M10": 1.5, "M12": 1.75, "M14": 2.0, "M16": 2.0, "M18": 2.5, "M20": 2.5, "M22": 2.5,
    "M24": 3.0, "M27": 3.0, "M30": 3.5, "M33": 3.5, "M36": 4.0, "M39": 4.0, "M42": 4.5,
    "M45": 4.5, "M48": 5.0,
}

# Common fine-pitch threads (ISO 261).
FINE_THREADS: Dict[str, float] = {
    "M8x1": 1.0, "M10x1.25": 1.25, "M10x1": 1.0, "M12x1.5": 1.5, "M12x1.25": 1.25,
    "M14x1.5": 1.5, "M16x1.5": 1.5, "M18x1.5": 1.5, "M20x1.5": 1.5, "M22x1.5": 1.5,
    "M24x2": 2.0, "M27x2": 2.0, "M30x2": 2.0, "M36x3": 3.0,
}

# Tap drill for coarse threads (common workshop values, ≈ d − P).
TAP_DRILL: Dict[str, float] = {
    "M2": 1.6, "M2.5": 2.05, "M3": 2.5, "M4": 3.3, "M5": 4.2, "M6": 5.0, "M8": 6.8,
    "M10": 8.5, "M12": 10.2, "M14": 12.0, "M16": 14.0, "M18": 15.5, "M20": 17.5,
    "M22": 19.5, "M24": 21.0, "M27": 24.0, "M30": 26.5, "M33": 29.5, "M36": 32.0,
    "M39": 35.0, "M42": 37.5, "M45": 40.5, "M48": 43.0,
}

SIZES: List[str] = list(COARSE_PITCH.keys())


def nominal(designation: str) -> str:
    """'M10x1.25' -> 'M10'."""
    return designation.split("x")[0]


def thread(designation: str) -> Dict[str, float]:
    """Basic thread geometry (mm) for a coarse ('M10') or fine ('M10x1.25') designation."""
    if designation in COARSE_PITCH:
        P, coarse = COARSE_PITCH[designation], True
    elif designation in FINE_THREADS:
        P, coarse = FINE_THREADS[designation], False
    else:
        raise KeyError(designation)
    d = float(nominal(designation)[1:])
    d2 = d - 0.649519 * P          # pitch diameter
    d3 = d - 1.226869 * P          # external minor diameter
    D1 = d - 1.082532 * P          # internal (nut) minor diameter
    ds = (d2 + d3) / 2             # stress diameter
    As = math.pi / 4 * ds ** 2     # tensile stress area
    tap = TAP_DRILL[designation] if coarse else round(d - P, 2)
    return {"d": d, "P": P, "d2": d2, "d3": d3, "D1": D1, "ds": ds, "As": As,
            "Ad3": math.pi / 4 * d3 ** 2, "AN": math.pi / 4 * d ** 2,
            "tap": tap, "coarse": coarse, "designation": designation,
            "nominal": nominal(designation)}


THREAD_OPTIONS = [{"value": s, "label": f"{s} (coarse {COARSE_PITCH[s]})"} for s in SIZES] + \
                 [{"value": f, "label": f"{f.replace('x', ' × ')} (fine)"} for f in FINE_THREADS]


# --------------------------------------------------------------------------
# Property classes: Rm (min tensile), Rp (min yield / 0.2% proof), Sp (proof stress)
# --------------------------------------------------------------------------

PROPERTY_CLASSES: Dict[str, Dict[str, Any]] = {
    "4.6":   {"Rm": 400,  "Rp": 240,  "Sp": 225, "std": "ISO 898-1"},
    "4.8":   {"Rm": 420,  "Rp": 340,  "Sp": 310, "std": "ISO 898-1"},
    "5.6":   {"Rm": 500,  "Rp": 300,  "Sp": 280, "std": "ISO 898-1"},
    "5.8":   {"Rm": 520,  "Rp": 420,  "Sp": 380, "std": "ISO 898-1"},
    "6.8":   {"Rm": 600,  "Rp": 480,  "Sp": 440, "std": "ISO 898-1"},
    "8.8":   {"Rm": 800,  "Rp": 640,  "Sp": 580, "std": "ISO 898-1",
              "large": {"Rm": 830, "Rp": 660, "Sp": 600}},   # d > 16 mm
    "9.8":   {"Rm": 900,  "Rp": 720,  "Sp": 650, "std": "ISO 898-1", "max_d": 16},
    "10.9":  {"Rm": 1040, "Rp": 940,  "Sp": 830, "std": "ISO 898-1"},
    "12.9":  {"Rm": 1220, "Rp": 1100, "Sp": 970, "std": "ISO 898-1"},
    "A2-50": {"Rm": 500,  "Rp": 210,  "Sp": 210, "std": "ISO 3506-1", "stainless": True},
    "A2-70": {"Rm": 700,  "Rp": 450,  "Sp": 450, "std": "ISO 3506-1", "stainless": True},
    "A4-70": {"Rm": 700,  "Rp": 450,  "Sp": 450, "std": "ISO 3506-1", "stainless": True},
    "A4-80": {"Rm": 800,  "Rp": 600,  "Sp": 600, "std": "ISO 3506-1", "stainless": True},
}

CLASS_OPTIONS = [{"value": k, "label": f"{k} ({v['std']})"} for k, v in PROPERTY_CLASSES.items()]


def strength(cls: str, d: float) -> Dict[str, Any]:
    """Strength values (MPa) for a class at nominal diameter d (mm)."""
    pc = PROPERTY_CLASSES[cls]
    if pc.get("max_d") and d > pc["max_d"]:
        raise ValueError(f"Class {cls} is only defined up to M{pc['max_d']}.")
    vals = dict(pc.get("large") if (pc.get("large") and d > 16) else pc)
    return {"Rm": vals["Rm"], "Rp": vals["Rp"], "Sp": vals["Sp"],
            "stainless": bool(pc.get("stainless")), "std": pc["std"]}


# --------------------------------------------------------------------------
# Head, nut, washer and hole dimensions (mm)
# --------------------------------------------------------------------------

# ISO 4762 socket head cap screw: dk (head dia), k (head height), s (hex key)
SHCS: Dict[str, Dict[str, float]] = {
    "M2": {"dk": 3.8, "k": 2, "s": 1.5}, "M2.5": {"dk": 4.5, "k": 2.5, "s": 2},
    "M3": {"dk": 5.5, "k": 3, "s": 2.5}, "M4": {"dk": 7, "k": 4, "s": 3},
    "M5": {"dk": 8.5, "k": 5, "s": 4}, "M6": {"dk": 10, "k": 6, "s": 5},
    "M8": {"dk": 13, "k": 8, "s": 6}, "M10": {"dk": 16, "k": 10, "s": 8},
    "M12": {"dk": 18, "k": 12, "s": 10}, "M14": {"dk": 21, "k": 14, "s": 12},
    "M16": {"dk": 24, "k": 16, "s": 14}, "M18": {"dk": 27, "k": 18, "s": 14},
    "M20": {"dk": 30, "k": 20, "s": 17}, "M22": {"dk": 33, "k": 22, "s": 17},
    "M24": {"dk": 36, "k": 24, "s": 19}, "M27": {"dk": 40, "k": 27, "s": 19},
    "M30": {"dk": 45, "k": 30, "s": 22}, "M33": {"dk": 50, "k": 33, "s": 24},
    "M36": {"dk": 54, "k": 36, "s": 27}, "M42": {"dk": 63, "k": 42, "s": 32},
    "M48": {"dk": 72, "k": 48, "s": 36},
}

# ISO 4017 / 4014 hex head: s (across flats), k (head height), e (across corners, min)
HEX: Dict[str, Dict[str, float]] = {
    "M2": {"s": 4, "k": 1.4, "e": 4.32}, "M2.5": {"s": 5, "k": 1.7, "e": 5.45},
    "M3": {"s": 5.5, "k": 2, "e": 6.01}, "M4": {"s": 7, "k": 2.8, "e": 7.66},
    "M5": {"s": 8, "k": 3.5, "e": 8.79}, "M6": {"s": 10, "k": 4, "e": 11.05},
    "M8": {"s": 13, "k": 5.3, "e": 14.38}, "M10": {"s": 16, "k": 6.4, "e": 17.77},
    "M12": {"s": 18, "k": 7.5, "e": 20.03}, "M14": {"s": 21, "k": 8.8, "e": 23.36},
    "M16": {"s": 24, "k": 10, "e": 26.75}, "M18": {"s": 27, "k": 11.5, "e": 30.14},
    "M20": {"s": 30, "k": 12.5, "e": 33.53}, "M22": {"s": 34, "k": 14, "e": 37.72},
    "M24": {"s": 36, "k": 15, "e": 39.98}, "M27": {"s": 41, "k": 17, "e": 45.2},
    "M30": {"s": 46, "k": 18.7, "e": 50.85}, "M33": {"s": 50, "k": 21, "e": 55.37},
    "M36": {"s": 55, "k": 22.5, "e": 60.79}, "M39": {"s": 60, "k": 25, "e": 66.44},
    "M42": {"s": 65, "k": 26, "e": 71.3}, "M45": {"s": 70, "k": 28, "e": 76.95},
    "M48": {"s": 75, "k": 30, "e": 82.6},
}

# ISO 10642 countersunk socket screw: dk (theoretical head dia), k, s (hex key)
COUNTERSUNK: Dict[str, Dict[str, float]] = {
    "M3": {"dk": 6.72, "k": 1.86, "s": 2}, "M4": {"dk": 8.96, "k": 2.48, "s": 2.5},
    "M5": {"dk": 11.2, "k": 3.1, "s": 3}, "M6": {"dk": 13.44, "k": 3.72, "s": 4},
    "M8": {"dk": 17.92, "k": 4.96, "s": 5}, "M10": {"dk": 22.4, "k": 6.2, "s": 6},
    "M12": {"dk": 26.88, "k": 7.44, "s": 8}, "M16": {"dk": 33.6, "k": 8.8, "s": 10},
    "M20": {"dk": 40.32, "k": 10.16, "s": 12},
}

# ISO 4032 hex nut: s, m (height)
NUT: Dict[str, Dict[str, float]] = {
    "M2": {"s": 4, "m": 1.6}, "M2.5": {"s": 5, "m": 2}, "M3": {"s": 5.5, "m": 2.4},
    "M4": {"s": 7, "m": 3.2}, "M5": {"s": 8, "m": 4.7}, "M6": {"s": 10, "m": 5.2},
    "M8": {"s": 13, "m": 6.8}, "M10": {"s": 16, "m": 8.4}, "M12": {"s": 18, "m": 10.8},
    "M14": {"s": 21, "m": 12.8}, "M16": {"s": 24, "m": 14.8}, "M18": {"s": 27, "m": 15.8},
    "M20": {"s": 30, "m": 18}, "M22": {"s": 34, "m": 19.4}, "M24": {"s": 36, "m": 21.5},
    "M27": {"s": 41, "m": 23.8}, "M30": {"s": 46, "m": 25.6}, "M33": {"s": 50, "m": 28.7},
    "M36": {"s": 55, "m": 31}, "M39": {"s": 60, "m": 33.4}, "M42": {"s": 65, "m": 34},
    "M45": {"s": 70, "m": 36}, "M48": {"s": 75, "m": 38},
}

# ISO 7089 plain washer: d1 (inner), d2 (outer), h (thickness)
WASHER: Dict[str, Dict[str, float]] = {
    "M2": {"d1": 2.2, "d2": 5, "h": 0.3}, "M2.5": {"d1": 2.7, "d2": 6, "h": 0.5},
    "M3": {"d1": 3.2, "d2": 7, "h": 0.5}, "M4": {"d1": 4.3, "d2": 9, "h": 0.8},
    "M5": {"d1": 5.3, "d2": 10, "h": 1}, "M6": {"d1": 6.4, "d2": 12, "h": 1.6},
    "M8": {"d1": 8.4, "d2": 16, "h": 1.6}, "M10": {"d1": 10.5, "d2": 20, "h": 2},
    "M12": {"d1": 13, "d2": 24, "h": 2.5}, "M14": {"d1": 15, "d2": 28, "h": 2.5},
    "M16": {"d1": 17, "d2": 30, "h": 3}, "M18": {"d1": 19, "d2": 34, "h": 3},
    "M20": {"d1": 21, "d2": 37, "h": 3}, "M22": {"d1": 23, "d2": 39, "h": 3},
    "M24": {"d1": 25, "d2": 44, "h": 4}, "M27": {"d1": 28, "d2": 50, "h": 4},
    "M30": {"d1": 31, "d2": 56, "h": 4}, "M33": {"d1": 34, "d2": 60, "h": 5},
    "M36": {"d1": 37, "d2": 66, "h": 5}, "M39": {"d1": 42, "d2": 72, "h": 6},
    "M42": {"d1": 45, "d2": 78, "h": 8}, "M45": {"d1": 48, "d2": 85, "h": 8},
    "M48": {"d1": 50, "d2": 92, "h": 8},
}

# ISO 273 clearance holes: fine, medium, coarse
CLEARANCE: Dict[str, Dict[str, float]] = {
    "M2": {"fine": 2.2, "medium": 2.4, "coarse": 2.6},
    "M2.5": {"fine": 2.7, "medium": 2.9, "coarse": 3.1},
    "M3": {"fine": 3.2, "medium": 3.4, "coarse": 3.6},
    "M4": {"fine": 4.3, "medium": 4.5, "coarse": 4.8},
    "M5": {"fine": 5.3, "medium": 5.5, "coarse": 5.8},
    "M6": {"fine": 6.4, "medium": 6.6, "coarse": 7},
    "M8": {"fine": 8.4, "medium": 9, "coarse": 10},
    "M10": {"fine": 10.5, "medium": 11, "coarse": 12},
    "M12": {"fine": 13, "medium": 13.5, "coarse": 14.5},
    "M14": {"fine": 15, "medium": 15.5, "coarse": 16.5},
    "M16": {"fine": 17, "medium": 17.5, "coarse": 18.5},
    "M18": {"fine": 19, "medium": 20, "coarse": 21},
    "M20": {"fine": 21, "medium": 22, "coarse": 24},
    "M22": {"fine": 23, "medium": 24, "coarse": 26},
    "M24": {"fine": 25, "medium": 26, "coarse": 28},
    "M27": {"fine": 28, "medium": 30, "coarse": 32},
    "M30": {"fine": 31, "medium": 33, "coarse": 35},
    "M33": {"fine": 34, "medium": 36, "coarse": 38},
    "M36": {"fine": 37, "medium": 39, "coarse": 42},
    "M39": {"fine": 40, "medium": 42, "coarse": 45},
    "M42": {"fine": 43, "medium": 45, "coarse": 48},
    "M45": {"fine": 46, "medium": 48, "coarse": 52},
    "M48": {"fine": 50, "medium": 52, "coarse": 56},
}

# Preferred stock lengths for ISO 4762 / ISO 4017 (mm).
STOCK_LENGTHS: List[int] = [5, 6, 8, 10, 12, 14, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70,
                            75, 80, 90, 100, 110, 120, 130, 140, 150, 160, 180, 200, 220, 240,
                            260, 280, 300]

HEAD_TYPES = [
    {"value": "shcs", "label": "Socket head cap screw (ISO 4762)"},
    {"value": "hex", "label": "Hex head bolt/screw (ISO 4017/4014)"},
    {"value": "countersunk", "label": "Countersunk socket (ISO 10642)"},
]
HEAD_STD = {"shcs": "ISO 4762", "hex": "ISO 4017", "countersunk": "ISO 10642"}


def head(head_type: str, size: str) -> Optional[Dict[str, float]]:
    table = {"shcs": SHCS, "hex": HEX, "countersunk": COUNTERSUNK}[head_type]
    return table.get(size)


def bearing_diameter(head_type: str, size: str) -> float:
    """Outer diameter of the head bearing face dW (mm), approx. min values."""
    h = head(head_type, size)
    if h is None:
        raise KeyError(size)
    if head_type == "hex":
        return 0.92 * h["s"]
    if head_type == "shcs":
        return 0.92 * h["dk"]
    # countersunk: conical seat, use mean of head and shank diameter
    return (h["dk"] + float(size[1:])) / 2


def stock_length(required: float) -> Optional[int]:
    for L in STOCK_LENGTHS:
        if L >= required - 1e-9:
            return L
    return None


# --------------------------------------------------------------------------
# Friction and tightening (VDI 2230-1:2015 Tables A5, A8 — typical values)
# --------------------------------------------------------------------------

FRICTION: Dict[str, Dict[str, Any]] = {
    "oiled":        {"label": "Steel, oiled / phosphated + oil (μ ≈ 0.12)", "muG": 0.12, "muK": 0.12},
    "dry":          {"label": "Steel, bright / black oxide, dry (μ ≈ 0.16)", "muG": 0.16, "muK": 0.16},
    "zinc_dry":     {"label": "Zinc-plated, dry (μ ≈ 0.14)", "muG": 0.14, "muK": 0.14},
    "zinc_flake":   {"label": "Zinc-flake coated with top-coat lubricant (μ ≈ 0.10)", "muG": 0.10, "muK": 0.10},
    "mos2":         {"label": "MoS₂ paste / grease (μ ≈ 0.08)", "muG": 0.08, "muK": 0.08},
    "stainless_dry": {"label": "Stainless, dry (μ ≈ 0.20, galling risk)", "muG": 0.20, "muK": 0.20},
    "custom":       {"label": "Custom μG / μK…", "muG": None, "muK": None},
}
FRICTION_OPTIONS = [{"value": k, "label": v["label"]} for k, v in FRICTION.items()]

TIGHTENING: Dict[str, Dict[str, Any]] = {
    "torque_estimated": {"label": "Torque wrench, friction estimated (αA 1.7)", "alpha": 1.7},
    "torque_measured":  {"label": "Calibrated torque wrench, friction measured (αA 1.4)", "alpha": 1.4},
    "angle":            {"label": "Angle- or yield-controlled (αA 1.2)", "alpha": 1.2},
    "impact":           {"label": "Impact wrench (αA 2.5)", "alpha": 2.5},
    "hand":             {"label": "By hand / uncontrolled (αA 4.0)", "alpha": 4.0},
}
TIGHTENING_OPTIONS = [{"value": k, "label": v["label"]} for k, v in TIGHTENING.items()]


# Clamped-part materials: E (MPa), limiting surface pressure pG (MPa) — VDI 2230 Table A9 (approx.)
PLATE_MATERIALS: Dict[str, Dict[str, Any]] = {
    "s235":      {"label": "Steel S235", "E": 205000, "pG": 490},
    "s355":      {"label": "Steel S355", "E": 205000, "pG": 760},
    "c45":       {"label": "Steel C45 (+N)", "E": 205000, "pG": 700},
    "42crmo4":   {"label": "42CrMo4 Q&T", "E": 205000, "pG": 1080},
    "gjl250":    {"label": "Grey cast iron EN-GJL-250", "E": 110000, "pG": 850},
    "gjs500":    {"label": "Ductile iron EN-GJS-500-7", "E": 169000, "pG": 750},
    "al6082":    {"label": "Aluminium 6082-T6 / AlMgSi1", "E": 70000, "pG": 360},
    "al7075":    {"label": "Aluminium 7075-T6", "E": 71000, "pG": 410},
    "al_cast":   {"label": "Cast aluminium AlSi9Cu3", "E": 75000, "pG": 290},
}
PLATE_OPTIONS = [{"value": k, "label": v["label"]} for k, v in PLATE_MATERIALS.items()]

# Internal-thread (tapped hole) materials: Rm and shear strength τB (MPa), typical.
TAPPED_MATERIALS: Dict[str, Dict[str, Any]] = {
    "s355":     {"label": "Steel S355", "Rm": 510, "tau": 0.6 * 510, "rule": "0.8–1.0 d"},
    "c45":      {"label": "Steel C45 (+N)", "Rm": 620, "tau": 0.6 * 620, "rule": "0.8–1.0 d"},
    "42crmo4":  {"label": "42CrMo4 Q&T", "Rm": 1000, "tau": 0.6 * 1000, "rule": "0.8 d"},
    "gjl250":   {"label": "Grey cast iron EN-GJL-250", "Rm": 250, "tau": 250, "rule": "1.25–1.5 d"},
    "gjs500":   {"label": "Ductile iron EN-GJS-500-7", "Rm": 500, "tau": 0.9 * 500, "rule": "1.0–1.25 d"},
    "al6082":   {"label": "Aluminium 6082-T6", "Rm": 310, "tau": 0.62 * 310, "rule": "1.5–2.0 d"},
    "al7075":   {"label": "Aluminium 7075-T6", "Rm": 572, "tau": 0.6 * 572, "rule": "1.25–1.5 d"},
    "al_cast":  {"label": "Cast aluminium AlSi9Cu3", "Rm": 240, "tau": 0.6 * 240, "rule": "2.0–2.5 d"},
    "brass":    {"label": "Brass CW614N", "Rm": 385, "tau": 0.6 * 385, "rule": "1.5–2.0 d"},
}
TAPPED_OPTIONS = [{"value": k, "label": v["label"]} for k, v in TAPPED_MATERIALS.items()]


# --------------------------------------------------------------------------
# VDI 2230 core relations (mm, N, MPa)
# --------------------------------------------------------------------------

def assembly_preload(th: Dict[str, float], Rp: float, muG: float, nu: float = 0.9) -> float:
    """Permissible assembly preload FM,zul (N) — VDI 2230-1 eq. (R2): von Mises
    utilisation `nu` of Rp0.2 under tension plus thread torsion, full-thread bolt."""
    d0, d2, P = th["ds"], th["d2"], th["P"]
    A0 = math.pi / 4 * d0 ** 2
    k = 1.5 * d2 / d0 * (P / (math.pi * d2) + 1.155 * muG)
    return A0 * nu * Rp / math.sqrt(1 + 3 * k ** 2)


def thread_torque_factor(th: Dict[str, float], muG: float) -> float:
    """MG / FM (mm): thread friction + pitch part of the torque."""
    return th["d2"] / 2 * (th["P"] / (math.pi * th["d2"]) + 1.155 * muG)


def tightening_torque(FM: float, th: Dict[str, float], muG: float, muK: float, DKm: float) -> float:
    """MA (N·mm) = FM (0.16 P + 0.58 d2 μG + μK DKm/2)."""
    return FM * (0.16 * th["P"] + 0.58 * th["d2"] * muG + muK * DKm / 2)


def preload_from_torque(MA: float, th: Dict[str, float], muG: float, muK: float, DKm: float) -> float:
    return MA / (0.16 * th["P"] + 0.58 * th["d2"] * muG + muK * DKm / 2)


def endurance_limit_rolled(d: float) -> float:
    """σASV (MPa) for threads rolled before heat treatment, VDI 2230-1 (R? ) eq."""
    return 0.85 * (150.0 / d + 45.0)
