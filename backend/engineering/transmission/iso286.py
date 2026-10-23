"""
ISO 286-1/-2 limits and fits (nominal sizes 0 < D <= 500 mm).

All deviations in micrometres. Shaft fundamental deviations are tabulated;
hole deviations follow the ISO 286-1 general and special rules:
  A..H   EI = -es (same letter shaft)
  JS/js  +/- IT/2 (grades 7..11 with odd IT rounded down to the even value)
  K,M,N  ES = -ei + Delta   for grades <= 8   (Delta = IT_n - IT_(n-1))
  P..ZC  ES = -ei + Delta   for grades <= 7
"""
from typing import Dict, List, Tuple

from ..core import CalcError

COARSE = [3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500]
FINE = [3, 6, 10, 14, 18, 24, 30, 40, 50, 65, 80, 100, 120, 140, 160, 180, 200, 225,
        250, 280, 315, 355, 400, 450, 500]

# Standard tolerance grades IT3..IT11 (µm), ISO 286-1 Table 1.
IT: Dict[int, List[float]] = {
    3: [2, 2.5, 2.5, 3, 4, 4, 5, 6, 8, 10, 12, 13, 15],
    4: [3, 4, 4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20],
    5: [4, 5, 6, 8, 9, 11, 13, 15, 18, 20, 23, 25, 27],
    6: [6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40],
    7: [10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63],
    8: [14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97],
    9: [25, 30, 36, 43, 52, 62, 74, 87, 100, 115, 130, 140, 155],
    10: [40, 48, 58, 70, 84, 100, 120, 140, 160, 185, 210, 230, 250],
    11: [60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400],
}

# Shaft upper deviation es (µm) for a..h letters, coarse ranges.
SHAFT_ES: Dict[str, List[int]] = {
    "d": [-20, -30, -40, -50, -65, -80, -100, -120, -145, -170, -190, -210, -230],
    "e": [-14, -20, -25, -32, -40, -50, -60, -72, -85, -100, -110, -125, -135],
    "f": [-6, -10, -13, -16, -20, -25, -30, -36, -43, -50, -56, -62, -68],
    "g": [-2, -4, -5, -6, -7, -9, -10, -12, -14, -15, -17, -18, -20],
    "h": [0] * 13,
}

# Shaft lower deviation ei (µm), coarse ranges. k applies to grades 4..7 only.
SHAFT_EI_COARSE: Dict[str, List[int]] = {
    "k": [0, 1, 1, 1, 2, 2, 2, 3, 3, 4, 4, 4, 5],
    "m": [2, 4, 6, 7, 8, 9, 11, 13, 15, 17, 20, 21, 23],
    "n": [4, 8, 10, 12, 15, 17, 20, 23, 27, 31, 34, 37, 40],
    "p": [6, 12, 15, 18, 22, 26, 32, 37, 43, 50, 56, 62, 68],
}

# Shaft lower deviation ei (µm), fine ranges.
SHAFT_EI_FINE: Dict[str, List[int]] = {
    "r": [10, 15, 19, 23, 23, 28, 28, 34, 34, 41, 43, 51, 54, 63, 65, 68, 77, 80, 84, 94,
          98, 108, 114, 126, 132],
    "s": [14, 19, 23, 28, 28, 35, 35, 43, 43, 53, 59, 71, 79, 92, 100, 108, 122, 130, 140,
          158, 170, 190, 208, 232, 252],
    "u": [18, 23, 28, 33, 33, 41, 48, 60, 70, 87, 102, 124, 144, 170, 190, 210, 236, 258,
          284, 315, 350, 390, 435, 490, 540],
}

HOLE_LETTERS = ["D", "E", "F", "G", "H", "JS", "K", "M", "N", "P", "R", "S"]
SHAFT_LETTERS = ["d", "e", "f", "g", "h", "js", "k", "m", "n", "p", "r", "s", "u"]
GRADES = [5, 6, 7, 8, 9, 10, 11]


def _index(size: float, bounds: List[int]) -> int:
    if not (0 < size <= 500):
        raise CalcError("ISO 286 tables cover nominal sizes above 0 up to 500 mm.")
    for i, b in enumerate(bounds):
        if size <= b:
            return i
    raise CalcError("Size out of range.")


def size_range(size: float) -> str:
    i = _index(size, FINE)
    lo = 0 if i == 0 else FINE[i - 1]
    return f"{lo}–{FINE[i]} mm"


def it_value(size: float, grade: int) -> float:
    if grade not in IT:
        raise CalcError(f"IT{grade} not tabulated (IT3–IT11 available).")
    return IT[grade][_index(size, COARSE)]


def _delta(size: float, grade: int) -> float:
    """Delta = IT_n - IT_(n-1); zero for sizes up to 3 mm."""
    if size <= 3:
        return 0.0
    return it_value(size, grade) - it_value(size, grade - 1)


def _js(size: float, grade: int) -> float:
    it = it_value(size, grade)
    if grade >= 7 and float(it).is_integer() and int(it) % 2 == 1:
        it -= 1
    return it / 2


def shaft_ei_fundamental(size: float, letter: str, grade: int) -> float:
    """Lower fundamental deviation ei for letters k..u."""
    if letter == "k":
        if grade < 4 or grade > 7:
            return 0.0
        return SHAFT_EI_COARSE["k"][_index(size, COARSE)]
    if letter in SHAFT_EI_COARSE:
        return SHAFT_EI_COARSE[letter][_index(size, COARSE)]
    if letter in SHAFT_EI_FINE:
        return SHAFT_EI_FINE[letter][_index(size, FINE)]
    raise CalcError(f"Shaft letter '{letter}' not supported.")


def shaft_deviations(size: float, letter: str, grade: int) -> Tuple[float, float]:
    """(es, ei) in µm."""
    it = it_value(size, grade)
    if letter in SHAFT_ES:
        es = SHAFT_ES[letter][_index(size, COARSE)]
        return float(es), es - it
    if letter == "js":
        h = _js(size, grade)
        return h, -h
    ei = shaft_ei_fundamental(size, letter, grade)
    return ei + it, float(ei)


def hole_deviations(size: float, letter: str, grade: int) -> Tuple[float, float]:
    """(ES, EI) in µm."""
    it = it_value(size, grade)
    if letter in ("D", "E", "F", "G", "H"):
        EI = -SHAFT_ES[letter.lower()][_index(size, COARSE)]
        return EI + it, float(EI)
    if letter == "JS":
        h = _js(size, grade)
        return h, -h
    if letter == "K":
        if grade > 8:
            ES = 0.0
        else:
            ES = -shaft_ei_fundamental(size, "k", 6) + _delta(size, grade)
        return ES, ES - it
    if letter == "M":
        base = -shaft_ei_fundamental(size, "m", grade)
        ES = base + _delta(size, grade) if grade <= 8 else base
        return ES, ES - it
    if letter == "N":
        base = -shaft_ei_fundamental(size, "n", grade)
        if size <= 3:
            ES = base
        elif grade <= 8:
            ES = base + _delta(size, grade)
        else:
            ES = 0.0
        return ES, ES - it
    if letter in ("P", "R", "S"):
        base = -shaft_ei_fundamental(size, letter.lower(), grade)
        ES = base + _delta(size, grade) if grade <= 7 else base
        return ES, ES - it
    raise CalcError(f"Hole letter '{letter}' not supported.")


def fit(size: float, hole: Tuple[str, int], shaft: Tuple[str, int]) -> Dict[str, float]:
    ES, EI = hole_deviations(size, *hole)
    es, ei = shaft_deviations(size, *shaft)
    c_max = ES - ei
    c_min = EI - es
    if c_min >= 0:
        kind = "Clearance fit"
    elif c_max <= 0:
        kind = "Interference fit"
    else:
        kind = "Transition fit"
    return {"ES": ES, "EI": EI, "es": es, "ei": ei, "c_max": c_max, "c_min": c_min,
            "type": kind}


def parse_class(code: str) -> Tuple[str, int]:
    """'H7' -> ('H', 7), 'js6' -> ('js', 6)."""
    letters = "".join(ch for ch in code if ch.isalpha())
    digits = "".join(ch for ch in code if ch.isdigit())
    return letters, int(digits)
