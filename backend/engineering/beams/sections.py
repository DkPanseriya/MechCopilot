"""
Cross-section properties: shape formulas and standard steel profile tables.

All functions take/return SI (m, m^2, m^3, m^4). Axis convention (EN 1993):
    y-y = strong (horizontal) axis, bending in the plane of the web
    z-z = weak (vertical) axis
Every property dict carries: A, Iy, Iz, Wy, Wz, iy, iz, J, yc, zc, h, b,
Avy (shear area for load along z, i.e. vertical), Avz (for horizontal load),
plus a `draw` dict (mm) for the frontend cross-section diagram.
"""
import math
from typing import Any, Dict, List, Optional

from ..core import CalcError

STEEL_RHO = 7850.0


def _finish(A, Iy, Iz, h, b, yc, zc, J, Avy, Avz, draw, mass=None, Wy=None, Wz=None):
    Wy = Wy if Wy is not None else Iy / max(yc, h - yc)
    Wz = Wz if Wz is not None else Iz / max(zc, b - zc)
    return {
        "A": A, "Iy": Iy, "Iz": Iz, "Wy": Wy, "Wz": Wz,
        "iy": math.sqrt(Iy / A), "iz": math.sqrt(Iz / A), "J": J,
        "yc": yc, "zc": zc, "h": h, "b": b, "Avy": Avy, "Avz": Avz,
        "mass": mass if mass is not None else A * STEEL_RHO, "draw": draw,
    }


def _mm(v: float) -> float:
    return round(v * 1000, 3)


# --------------------------------------------------------------------------
# Shape formulas
# --------------------------------------------------------------------------

def rectangle(b: float, h: float) -> Dict[str, Any]:
    if b <= 0 or h <= 0:
        raise CalcError("Rectangle width and height must be positive.")
    A = b * h
    a, c = max(b, h), min(b, h)
    J = a * c ** 3 * (1 / 3 - 0.21 * (c / a) * (1 - c ** 4 / (12 * a ** 4)))
    return _finish(A, b * h ** 3 / 12, h * b ** 3 / 12, h, b, h / 2, b / 2, J, A / 1.5, A / 1.5,
                   {"shape": "rect", "b": _mm(b), "h": _mm(h)})


def _rounded_rect(b: float, h: float, r: float):
    """Area and second moments of a solid rectangle with corner radius r."""
    A = b * h - (4 - math.pi) * r ** 2

    def I(bb, hh):
        sq = r ** 4 / 12 + r ** 2 * (hh / 2 - r / 2) ** 2
        d = hh / 2 - r + 4 * r / (3 * math.pi)
        qc = (math.pi / 16 - 4 / (9 * math.pi)) * r ** 4 + (math.pi * r ** 2 / 4) * d ** 2
        return bb * hh ** 3 / 12 - 4 * sq + 4 * qc

    return A, I(b, h), I(h, b)


def en10219_radii(t: float):
    """Outer/inner corner radii used for EN 10219 cold-formed hollow sections."""
    ro = 2.0 * t if t <= 0.006 + 1e-12 else (2.5 * t if t <= 0.010 + 1e-12 else 3.0 * t)
    return ro, ro - t


def rhs(b: float, h: float, t: float, ro: Optional[float] = None) -> Dict[str, Any]:
    if t <= 0 or 2 * t >= min(b, h):
        raise CalcError("Hollow section wall thickness must be positive and less than half the width/height.")
    if ro is None:
        ro, ri = en10219_radii(t)
    else:
        ri = max(ro - t, 0.0)
    Ao, Iyo, Izo = _rounded_rect(b, h, ro)
    Ai, Iyi, Izi = _rounded_rect(b - 2 * t, h - 2 * t, ri)
    A = Ao - Ai
    rm = (ro + ri) / 2
    Ap = (b - t) * (h - t) - (4 - math.pi) * rm ** 2
    p = 2 * ((b - t) + (h - t)) - 2 * rm * (4 - math.pi)
    J = t ** 3 * p / 3 + 4 * Ap ** 2 * t / p
    return _finish(A, Iyo - Iyi, Izo - Izi, h, b, h / 2, b / 2, J,
                   2 * t * (h - 2 * t), 2 * t * (b - 2 * t),
                   {"shape": "rhs", "b": _mm(b), "h": _mm(h), "t": _mm(t), "r": _mm(ro)})


def round_bar(D: float) -> Dict[str, Any]:
    if D <= 0:
        raise CalcError("Diameter must be positive.")
    A = math.pi * D ** 2 / 4
    I = math.pi * D ** 4 / 64
    return _finish(A, I, I, D, D, D / 2, D / 2, 2 * I, 0.75 * A, 0.75 * A,
                   {"shape": "round", "D": _mm(D)})


def chs(D: float, t: float) -> Dict[str, Any]:
    if t <= 0 or 2 * t >= D:
        raise CalcError("Tube wall thickness must be positive and less than half the diameter.")
    d = D - 2 * t
    A = math.pi / 4 * (D ** 2 - d ** 2)
    I = math.pi / 64 * (D ** 4 - d ** 4)
    return _finish(A, I, I, D, D, D / 2, D / 2, 2 * I, A / 2, A / 2,
                   {"shape": "chs", "D": _mm(D), "t": _mm(t)})


def i_section(b: float, h: float, tw: float, tf: float, r: float = 0.0) -> Dict[str, Any]:
    if min(b, h, tw, tf) <= 0 or 2 * tf >= h or tw >= b:
        raise CalcError("I-section: need 2·tf < h and tw < b, all dimensions positive.")
    hw = h - 2 * tf
    Af = (1 - math.pi / 4) * r ** 2          # one root-fillet spandrel
    e = r * (10 - 3 * math.pi) / (12 - 3 * math.pi)  # spandrel centroid offset from corner
    A = 2 * b * tf + hw * tw + 4 * Af
    Iy = (b * h ** 3 - (b - tw) * hw ** 3) / 12 + 4 * Af * (h / 2 - tf - e) ** 2
    Iz = (2 * tf * b ** 3 + hw * tw ** 3) / 12 + 4 * Af * (tw / 2 + e) ** 2
    J = (2 * b * tf ** 3 + (h - tf) * tw ** 3) / 3
    return _finish(A, Iy, Iz, h, b, h / 2, b / 2, J, hw * tw, 2 * b * tf / 1.5,
                   {"shape": "i", "b": _mm(b), "h": _mm(h), "tw": _mm(tw), "tf": _mm(tf), "r": _mm(r)})


def channel(b: float, h: float, tw: float, tf: float) -> Dict[str, Any]:
    """Channel with web on the left (back), flanges pointing right."""
    if min(b, h, tw, tf) <= 0 or 2 * tf >= h or tw >= b:
        raise CalcError("Channel: need 2·tf < h and tw < b, all dimensions positive.")
    hw = h - 2 * tf
    A = 2 * b * tf + hw * tw
    zc = (2 * b * tf * (b / 2) + hw * tw * (tw / 2)) / A
    Iy = (b * h ** 3 - (b - tw) * hw ** 3) / 12
    Iz = 2 * (tf * b ** 3 / 12 + b * tf * (b / 2 - zc) ** 2) + hw * tw ** 3 / 12 + hw * tw * (tw / 2 - zc) ** 2
    J = (2 * b * tf ** 3 + h * tw ** 3) / 3
    return _finish(A, Iy, Iz, h, b, h / 2, zc, J, hw * tw, 2 * b * tf / 1.5,
                   {"shape": "channel", "b": _mm(b), "h": _mm(h), "tw": _mm(tw), "tf": _mm(tf),
                    "zc": _mm(zc)})


def tee(b: float, h: float, tw: float, tf: float) -> Dict[str, Any]:
    """T-section: flange (b × tf) on top, stem (tw) below; h = total height."""
    if min(b, h, tw, tf) <= 0 or tf >= h or tw >= b:
        raise CalcError("T-section: need tf < h and tw < b, all dimensions positive.")
    hs = h - tf
    As, Af = hs * tw, b * tf
    A = As + Af
    yc = (As * hs / 2 + Af * (h - tf / 2)) / A          # from bottom of stem
    Iy = tw * hs ** 3 / 12 + As * (hs / 2 - yc) ** 2 + b * tf ** 3 / 12 + Af * (h - tf / 2 - yc) ** 2
    Iz = (tf * b ** 3 + hs * tw ** 3) / 12
    J = (b * tf ** 3 + hs * tw ** 3) / 3
    return _finish(A, Iy, Iz, h, b, yc, b / 2, J, h * tw, b * tf / 1.5,
                   {"shape": "tee", "b": _mm(b), "h": _mm(h), "tw": _mm(tw), "tf": _mm(tf),
                    "yc": _mm(yc)})


def angle(b: float, h: float, t: float) -> Dict[str, Any]:
    """L-angle: vertical leg h, horizontal leg b, thickness t. Properties about
    centroidal axes parallel to the legs (as in profile tables)."""
    if min(b, h, t) <= 0 or t >= min(b, h):
        raise CalcError("Angle: thickness must be positive and smaller than both legs.")
    A1, A2 = t * h, (b - t) * t                       # vertical leg, horizontal leg
    A = A1 + A2
    zc = (A1 * t / 2 + A2 * (t + (b - t) / 2)) / A
    yc = (A1 * h / 2 + A2 * t / 2) / A
    Iy = t * h ** 3 / 12 + A1 * (h / 2 - yc) ** 2 + (b - t) * t ** 3 / 12 + A2 * (t / 2 - yc) ** 2
    Iz = h * t ** 3 / 12 + A1 * (t / 2 - zc) ** 2 + t * (b - t) ** 3 / 12 + A2 * (t + (b - t) / 2 - zc) ** 2
    J = (h + b - t) * t ** 3 / 3
    return _finish(A, Iy, Iz, h, b, yc, zc, J, h * t / 1.5, b * t / 1.5,
                   {"shape": "angle", "b": _mm(b), "h": _mm(h), "t": _mm(t),
                    "yc": _mm(yc), "zc": _mm(zc)})


SHAPES = {
    "rectangle": "Solid rectangle",
    "rhs": "Hollow rectangle (RHS/SHS)",
    "round": "Solid round",
    "chs": "Round tube (CHS)",
    "i_section": "I / H section",
    "channel": "Channel (C/U)",
    "tee": "T-section",
    "angle": "Angle (L)",
}


def shape_props(shape: str, b: float, h: float, t: float, D: float, tw: float, tf: float,
                r: float = 0.0) -> Dict[str, Any]:
    if shape == "rectangle":
        return rectangle(b, h)
    if shape == "rhs":
        return rhs(b, h, t)
    if shape == "round":
        return round_bar(D)
    if shape == "chs":
        return chs(D, t)
    if shape == "i_section":
        return i_section(b, h, tw, tf, r)
    if shape == "channel":
        return channel(b, h, tw, tf)
    if shape == "tee":
        return tee(b, h, tw, tf)
    if shape == "angle":
        return angle(b, h, t)
    raise CalcError(f"Unknown shape '{shape}'.")


# --------------------------------------------------------------------------
# Standard profiles (EN 10365 / Euronorm values).
# I/H: (name, h, b, tw, tf, r [mm], mass [kg/m], A [cm2], Iy [cm4], Wel,y [cm3],
#       Iz [cm4], Wel,z [cm3], It [cm4])
# --------------------------------------------------------------------------

_IPE = [
    ("IPE 80", 80, 46, 3.8, 5.2, 5, 6.0, 7.64, 80.1, 20.0, 8.49, 3.69, 0.70),
    ("IPE 100", 100, 55, 4.1, 5.7, 7, 8.1, 10.3, 171, 34.2, 15.9, 5.79, 1.20),
    ("IPE 120", 120, 64, 4.4, 6.3, 7, 10.4, 13.2, 318, 53.0, 27.7, 8.65, 1.74),
    ("IPE 140", 140, 73, 4.7, 6.9, 7, 12.9, 16.4, 541, 77.3, 44.9, 12.3, 2.45),
    ("IPE 160", 160, 82, 5.0, 7.4, 9, 15.8, 20.1, 869, 109, 68.3, 16.7, 3.60),
    ("IPE 180", 180, 91, 5.3, 8.0, 9, 18.8, 23.9, 1317, 146, 101, 22.2, 4.79),
    ("IPE 200", 200, 100, 5.6, 8.5, 12, 22.4, 28.5, 1943, 194, 142, 28.5, 6.98),
    ("IPE 220", 220, 110, 5.9, 9.2, 12, 26.2, 33.4, 2772, 252, 205, 37.3, 9.07),
    ("IPE 240", 240, 120, 6.2, 9.8, 15, 30.7, 39.1, 3892, 324, 284, 47.3, 12.9),
    ("IPE 270", 270, 135, 6.6, 10.2, 15, 36.1, 45.9, 5790, 429, 420, 62.2, 15.9),
    ("IPE 300", 300, 150, 7.1, 10.7, 15, 42.2, 53.8, 8356, 557, 604, 80.5, 20.1),
    ("IPE 330", 330, 160, 7.5, 11.5, 18, 49.1, 62.6, 11770, 713, 788, 98.5, 28.2),
    ("IPE 360", 360, 170, 8.0, 12.7, 18, 57.1, 72.7, 16270, 904, 1043, 123, 37.3),
    ("IPE 400", 400, 180, 8.6, 13.5, 21, 66.3, 84.5, 23130, 1160, 1318, 146, 51.1),
    ("IPE 450", 450, 190, 9.4, 14.6, 21, 77.6, 98.8, 33740, 1500, 1676, 176, 66.9),
    ("IPE 500", 500, 200, 10.2, 16.0, 21, 90.7, 116, 48200, 1930, 2142, 214, 89.3),
    ("IPE 550", 550, 210, 11.1, 17.2, 24, 106, 134, 67120, 2440, 2668, 254, 123),
    ("IPE 600", 600, 220, 12.0, 19.0, 24, 122, 156, 92080, 3070, 3387, 308, 165),
]

_HEA = [
    ("HEA 100", 96, 100, 5.0, 8.0, 12, 16.7, 21.2, 349, 72.8, 134, 26.8, 5.24),
    ("HEA 120", 114, 120, 5.0, 8.0, 12, 19.9, 25.3, 606, 106, 231, 38.5, 5.99),
    ("HEA 140", 133, 140, 5.5, 8.5, 12, 24.7, 31.4, 1033, 155, 389, 55.6, 8.13),
    ("HEA 160", 152, 160, 6.0, 9.0, 15, 30.4, 38.8, 1673, 220, 616, 76.9, 12.2),
    ("HEA 180", 171, 180, 6.0, 9.5, 15, 35.5, 45.3, 2510, 294, 925, 103, 14.8),
    ("HEA 200", 190, 200, 6.5, 10.0, 18, 42.3, 53.8, 3692, 389, 1336, 134, 21.0),
    ("HEA 220", 210, 220, 7.0, 11.0, 18, 50.5, 64.3, 5410, 515, 1955, 178, 28.5),
    ("HEA 240", 230, 240, 7.5, 12.0, 21, 60.3, 76.8, 7763, 675, 2769, 231, 41.6),
    ("HEA 260", 250, 260, 7.5, 12.5, 24, 68.2, 86.8, 10450, 836, 3668, 282, 52.4),
    ("HEA 280", 270, 280, 8.0, 13.0, 24, 76.4, 97.3, 13670, 1013, 4763, 340, 62.1),
    ("HEA 300", 290, 300, 8.5, 14.0, 27, 88.3, 112.5, 18260, 1260, 6310, 421, 85.2),
    ("HEA 320", 310, 300, 9.0, 15.5, 27, 97.6, 124.4, 22930, 1479, 6985, 466, 108),
    ("HEA 340", 330, 300, 9.5, 16.5, 27, 105, 133.5, 27690, 1678, 7436, 496, 127),
    ("HEA 360", 350, 300, 10.0, 17.5, 27, 112, 142.8, 33090, 1891, 7887, 526, 149),
    ("HEA 400", 390, 300, 11.0, 19.0, 27, 125, 159.0, 45070, 2311, 8564, 571, 189),
    ("HEA 450", 440, 300, 11.5, 21.0, 27, 140, 178.0, 63720, 2896, 9465, 631, 244),
    ("HEA 500", 490, 300, 12.0, 23.0, 27, 155, 197.5, 86970, 3550, 10370, 691, 309),
]

_HEB = [
    ("HEB 100", 100, 100, 6.0, 10.0, 12, 20.4, 26.0, 450, 89.9, 167, 33.5, 9.25),
    ("HEB 120", 120, 120, 6.5, 11.0, 12, 26.7, 34.0, 864, 144, 318, 52.9, 13.8),
    ("HEB 140", 140, 140, 7.0, 12.0, 12, 33.7, 43.0, 1509, 216, 550, 78.5, 20.1),
    ("HEB 160", 160, 160, 8.0, 13.0, 15, 42.6, 54.3, 2492, 311, 889, 111, 31.2),
    ("HEB 180", 180, 180, 8.5, 14.0, 15, 51.2, 65.3, 3831, 426, 1363, 151, 42.2),
    ("HEB 200", 200, 200, 9.0, 15.0, 18, 61.3, 78.1, 5696, 570, 2003, 200, 59.3),
    ("HEB 220", 220, 220, 9.5, 16.0, 18, 71.5, 91.0, 8091, 736, 2843, 258, 76.6),
    ("HEB 240", 240, 240, 10.0, 17.0, 21, 83.2, 106, 11260, 938, 3923, 327, 103),
    ("HEB 260", 260, 260, 10.0, 17.5, 24, 93.0, 118.4, 14920, 1148, 5135, 395, 124),
    ("HEB 280", 280, 280, 10.5, 18.0, 24, 103, 131.4, 19270, 1376, 6595, 471, 144),
    ("HEB 300", 300, 300, 11.0, 19.0, 27, 117, 149.1, 25170, 1678, 8563, 571, 185),
    ("HEB 320", 320, 300, 11.5, 20.5, 27, 127, 161.3, 30820, 1926, 9239, 616, 225),
    ("HEB 340", 340, 300, 12.0, 21.5, 27, 134, 170.9, 36660, 2156, 9690, 646, 257),
    ("HEB 360", 360, 300, 12.5, 22.5, 27, 142, 180.6, 43190, 2400, 10140, 676, 292),
    ("HEB 400", 400, 300, 13.5, 24.0, 27, 155, 197.8, 57680, 2884, 10820, 721, 356),
    ("HEB 450", 450, 300, 14.0, 26.0, 27, 171, 218.0, 79890, 3551, 11720, 781, 440),
    ("HEB 500", 500, 300, 14.5, 28.0, 27, 187, 238.6, 107200, 4287, 12620, 842, 538),
]

# UPN: (name, h, b, tw, tf, r, mass, A, Iy, Wy, Iz, Wz, e = centroid from web back [cm])
_UPN = [
    ("UPN 80", 80, 45, 6.0, 8.0, 8.0, 8.64, 11.0, 106, 26.5, 19.4, 6.36, 1.45),
    ("UPN 100", 100, 50, 6.0, 8.5, 8.5, 10.6, 13.5, 206, 41.2, 29.3, 8.49, 1.55),
    ("UPN 120", 120, 55, 7.0, 9.0, 9.0, 13.4, 17.0, 364, 60.7, 43.2, 11.1, 1.60),
    ("UPN 140", 140, 60, 7.0, 10.0, 10.0, 16.0, 20.4, 605, 86.4, 62.7, 14.8, 1.75),
    ("UPN 160", 160, 65, 7.5, 10.5, 10.5, 18.8, 24.0, 925, 116, 85.3, 18.3, 1.84),
    ("UPN 180", 180, 70, 8.0, 11.0, 11.0, 22.0, 28.0, 1350, 150, 114, 22.4, 1.92),
    ("UPN 200", 200, 75, 8.5, 11.5, 11.5, 25.3, 32.2, 1910, 191, 148, 27.0, 2.01),
    ("UPN 220", 220, 80, 9.0, 12.5, 12.5, 29.4, 37.4, 2690, 245, 197, 33.6, 2.14),
    ("UPN 240", 240, 85, 9.5, 13.0, 13.0, 33.2, 42.3, 3600, 300, 248, 39.6, 2.23),
    ("UPN 260", 260, 90, 10.0, 14.0, 14.0, 37.9, 48.3, 4820, 371, 317, 47.7, 2.36),
    ("UPN 280", 280, 95, 10.0, 15.0, 15.0, 41.8, 53.3, 6280, 448, 399, 57.2, 2.53),
    ("UPN 300", 300, 100, 10.0, 16.0, 16.0, 46.2, 58.8, 8030, 535, 495, 67.8, 2.70),
    ("UPN 320", 320, 100, 14.0, 17.5, 17.5, 59.5, 75.8, 10870, 679, 597, 80.6, 2.60),
    ("UPN 350", 350, 100, 14.0, 16.0, 16.0, 60.6, 77.3, 12840, 734, 570, 75.0, 2.40),
    ("UPN 380", 380, 102, 13.5, 16.0, 16.0, 63.1, 80.4, 15760, 829, 615, 78.7, 2.38),
    ("UPN 400", 400, 110, 14.0, 18.0, 18.0, 71.8, 91.5, 20350, 1020, 846, 102, 2.65),
]

# Cold-formed hollow sections (EN 10219), properties computed with EN 10219 corner radii.
_SHS = [(40, 3), (50, 3), (50, 4), (60, 4), (70, 4), (80, 4), (80, 5), (90, 5), (100, 5),
        (100, 6), (120, 6), (140, 6), (150, 8), (160, 8), (200, 8), (200, 10), (250, 10)]
_RHS = [(60, 40, 3), (80, 40, 4), (100, 50, 4), (100, 60, 5), (120, 60, 5), (120, 80, 5),
        (150, 100, 6), (160, 80, 6), (200, 100, 6), (200, 100, 8), (250, 150, 8), (300, 200, 10)]
_CHS = [(33.7, 3.2), (42.4, 3.2), (48.3, 3.2), (48.3, 4.0), (60.3, 3.2), (60.3, 4.0),
        (76.1, 4.0), (88.9, 4.0), (88.9, 5.0), (114.3, 5.0), (139.7, 6.3), (168.3, 6.3),
        (168.3, 8.0), (219.1, 8.0), (273.0, 10.0)]

FAMILIES = ["IPE", "HEA", "HEB", "UPN", "SHS", "RHS", "CHS"]


def _from_table(row, family: str) -> Dict[str, Any]:
    name, h, b, tw, tf, r, mass, A, Iy, Wy, Iz, Wz, last = row
    mm, cm2, cm3, cm4 = 1e-3, 1e-4, 1e-6, 1e-8
    if family == "UPN":
        zc = last * 1e-2
        draw = {"shape": "channel", "b": b, "h": h, "tw": tw, "tf": tf, "zc": round(zc * 1000, 2)}
        J = (2 * b * tf ** 3 + h * tw ** 3) / 3 * 1e-12
    else:
        zc = b * mm / 2
        draw = {"shape": "i", "b": b, "h": h, "tw": tw, "tf": tf, "r": r}
        J = last * cm4
    p = _finish(A * cm2, Iy * cm4, Iz * cm4, h * mm, b * mm, h * mm / 2, zc, J,
                (h - 2 * tf) * tw * mm ** 2, 2 * b * tf * mm ** 2 / 1.5, draw,
                mass=mass, Wy=Wy * cm3, Wz=Wz * cm3)
    p.update({"name": name, "family": family})
    return p


def _build_profiles() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for fam, rows in (("IPE", _IPE), ("HEA", _HEA), ("HEB", _HEB), ("UPN", _UPN)):
        for row in rows:
            out[row[0]] = _from_table(row, fam)
    for a, t in _SHS:
        name = f"SHS {a}x{a}x{t:g}"
        p = rhs(a / 1000, a / 1000, t / 1000)
        p.update({"name": name, "family": "SHS"})
        out[name] = p
    for h, b, t in _RHS:
        name = f"RHS {h}x{b}x{t:g}"
        p = rhs(b / 1000, h / 1000, t / 1000)
        p.update({"name": name, "family": "RHS"})
        out[name] = p
    for D, t in _CHS:
        name = f"CHS {D:g}x{t:g}"
        p = chs(D / 1000, t / 1000)
        p.update({"name": name, "family": "CHS"})
        out[name] = p
    return out


PROFILES: Dict[str, Dict[str, Any]] = _build_profiles()


def profile_options() -> List[Dict[str, str]]:
    return [{"value": n, "label": f"{n}  ·  {p['mass']:.1f} kg/m"} for n, p in PROFILES.items()]


def get_profile(name: str) -> Dict[str, Any]:
    p = PROFILES.get(name)
    if p is None:
        raise CalcError(f"Unknown profile '{name}'.")
    return p
