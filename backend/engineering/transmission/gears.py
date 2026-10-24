"""Spur gears: geometry, Lewis bending and Hertz contact stress (Shigley ch. 13–14)."""
import math
from typing import Any, Dict, List

from ..core import (Calculator, CalcError, Output, Param, check, fmt, from_canonical,
                    linspace, series, step, table)

# Lewis form factor Y, 20° full-depth teeth (Shigley Table 14-2). Last entry ~ rack.
LEWIS_Y = [(12, 0.245), (13, 0.261), (14, 0.277), (15, 0.290), (16, 0.296), (17, 0.303),
           (18, 0.309), (19, 0.314), (20, 0.322), (21, 0.328), (22, 0.331), (24, 0.337),
           (26, 0.346), (28, 0.353), (30, 0.359), (34, 0.371), (38, 0.384), (43, 0.397),
           (50, 0.409), (60, 0.422), (75, 0.435), (100, 0.447), (150, 0.460), (300, 0.472),
           (400, 0.480), (10000, 0.485)]

# Typical AGMA grade-1 allowables (MPa) and elastic constants.
GEAR_MATERIALS = {
    "steel_200hb": ("Through-hardened steel, 200 HB", 194.9, 644.0, 207e9, 0.30),
    "steel_300hb": ("Through-hardened steel, 300 HB", 248.2, 866.0, 207e9, 0.30),
    "steel_nitrided": ("Nitrided through-hardened steel (≈4140)", 260.0, 1000.0, 207e9, 0.30),
    "steel_carburized": ("Carburized & hardened steel, 58–64 HRC", 380.0, 1240.0, 207e9, 0.30),
    "ductile_iron": ("Ductile iron 80-55-06", 150.0, 580.0, 169e9, 0.28),
    "cast_iron_30": ("Grey cast iron, class 30", 59.0, 480.0, 100e9, 0.26),
}

KV = {
    "cast": ("Cast profile", lambda V: (3.05 + V) / 3.05),
    "cut": ("Cut or milled profile", lambda V: (6.1 + V) / 6.1),
    "hobbed": ("Hobbed or shaped", lambda V: (3.56 + math.sqrt(V)) / 3.56),
    "ground": ("Shaved or ground", lambda V: (5.56 + math.sqrt(V)) / 5.56),
}


def lewis_y(z: float) -> float:
    if z < LEWIS_Y[0][0]:
        return LEWIS_Y[0][1]
    for (z0, y0), (z1, y1) in zip(LEWIS_Y, LEWIS_Y[1:]):
        if z0 <= z <= z1:
            return y0 + (y1 - y0) * (z - z0) / (z1 - z0)
    return LEWIS_Y[-1][1]


def min_pinion_teeth(phi: float, mG: float, k: float = 1.0) -> float:
    """Smallest pinion without undercut (Shigley eq. 13-11)."""
    s2 = math.sin(phi) ** 2
    return 2 * k / ((1 + 2 * mG) * s2) * (mG + math.sqrt(mG ** 2 + (1 + 2 * mG) * s2))


def gear_stresses(Wt: float, b: float, m: float, z1: float, z2: float, phi: float, Kv: float,
                  E1: float, nu1: float, E2: float, nu2: float) -> Dict[str, float]:
    d1, d2 = m * z1, m * z2
    Y1, Y2 = lewis_y(z1), lewis_y(z2)
    sb1 = Kv * Wt / (b * m * Y1)
    sb2 = Kv * Wt / (b * m * Y2)
    Cp = math.sqrt(1 / (math.pi * ((1 - nu1 ** 2) / E1 + (1 - nu2 ** 2) / E2)))
    r1, r2 = d1 * math.sin(phi) / 2, d2 * math.sin(phi) / 2
    sc = Cp * math.sqrt(Kv * Wt / (b * math.cos(phi)) * (1 / r1 + 1 / r2))
    return {"sb1": sb1, "sb2": sb2, "sc": sc, "Cp": Cp, "Y1": Y1, "Y2": Y2}


def _compute_spur(x: Dict[str, Any]) -> Dict[str, Any]:
    m, b = x["m"], x["b"]
    z1, z2 = x["z1"], x["z2"]
    if m <= 0 or b <= 0:
        raise CalcError("Module and face width must be positive.")
    if z1 < 8 or z2 < 8 or z1 != int(z1) or z2 != int(z2):
        raise CalcError("Tooth counts must be whole numbers of at least 8.")
    phi = math.radians(float(x["phi"]))
    n1 = x["n1"]
    if n1 <= 0:
        raise CalcError("Pinion speed must be positive.")
    w1 = n1 * 2 * math.pi / 60
    if x["input"] == "power":
        P = x["P"]
        T1 = P / w1
    else:
        T1 = abs(x["T1"])
        P = T1 * w1
    if T1 <= 0:
        raise CalcError("Transmitted power or torque must be positive.")

    p1 = GEAR_MATERIALS[x["mat1"]]
    p2 = GEAR_MATERIALS[x["mat2"]]
    nb_t, nc_t = x["n_bend"], x["n_contact"]

    d1, d2 = m * z1, m * z2
    a = (d1 + d2) / 2
    u = z2 / z1
    Wt = 2 * T1 / d1
    V = math.pi * d1 * n1 / 60
    Kv = KV[x["finish"]][1](V)
    s = gear_stresses(Wt, b, m, z1, z2, phi, Kv, p1[3], p1[4], p2[3], p2[4])

    ra1, ra2 = d1 / 2 + m, d2 / 2 + m
    rb1, rb2 = d1 / 2 * math.cos(phi), d2 / 2 * math.cos(phi)
    eps = (math.sqrt(ra1 ** 2 - rb1 ** 2) + math.sqrt(ra2 ** 2 - rb2 ** 2) - a * math.sin(phi)) \
        / (math.pi * m * math.cos(phi))

    St1, St2 = p1[1] * 1e6, p2[1] * 1e6
    Sc = min(p1[2], p2[2]) * 1e6
    SF1, SF2 = St1 / s["sb1"], St2 / s["sb2"]
    SF = min(SF1, SF2)
    SH = Sc / s["sc"]

    z_min = min_pinion_teeth(phi, u)
    checks = [
        check("Tooth bending", SF >= nb_t,
              f"pinion n = {fmt(SF1, 3)}, gear n = {fmt(SF2, 3)} (Lewis with velocity factor)",
              value=SF, limit=nb_t),
        check("Surface contact (pitting)", SH >= nc_t,
              f"n = {fmt(SH, 3)} on contact stress {fmt(s['sc'] / 1e6, 4)} MPa", value=SH, limit=nc_t),
    ]
    if z1 < math.ceil(z_min - 1e-9):
        checks.append(check("Undercut", False,
                            f"Pinion has {int(z1)} teeth; at least {math.ceil(z_min)} are needed to "
                            "avoid undercut. Use profile shift or more teeth.", warn=True))
    if not (3 * math.pi * m <= b <= 5 * math.pi * m):
        checks.append(check("Face width", False,
                            f"Face width outside the usual 3p–5p range "
                            f"({fmt(3 * math.pi * m * 1000, 3)}–{fmt(5 * math.pi * m * 1000, 3)} mm).",
                            warn=True))
    if eps < 1.2:
        checks.append(check("Contact ratio", False, f"εα = {fmt(eps, 3)} < 1.2: rough running.",
                            warn=True))

    bs = linspace(0.5 * b, 2 * b, 40)
    sb_l, sc_l = [], []
    for bi in bs:
        si = gear_stresses(Wt, bi, m, z1, z2, phi, Kv, p1[3], p1[4], p2[3], p2[4])
        sb_l.append(si["sb1"])
        sc_l.append(si["sc"])
    grp = "Stress vs face width"

    return {
        "values": {"SF": SF, "SH": SH, "sc": s["sc"], "sb1": s["sb1"], "sb2": s["sb2"],
                   "Wt": Wt, "T1": T1, "T2": T1 * u, "n2": n1 / u, "P": P, "V": V, "Kv": Kv,
                   "d1": d1, "d2": d2, "a": a, "eps": eps, "u": u},
        "checks": checks,
        "steps": [
            step("Pitch diameters", r"d = m z", d1, "length"),
            step("Pinion torque", r"T_1 = P/\omega_1", T1, "torque"),
            step("Transmitted (tangential) load", r"W_t = 2T_1/d_1", Wt, "force"),
            step("Pitch-line velocity", r"V = \pi d_1 n_1/60", V, "velocity"),
            step("Velocity factor", r"K_v", Kv),
            step("Lewis form factor (pinion)", r"Y_1", s["Y1"]),
            step("Pinion bending stress", r"\sigma = \frac{K_v W_t}{b\,m\,Y}", s["sb1"], "stress"),
            step("Elastic coefficient (√MPa)", r"C_p = \left[\pi\left(\frac{1-\nu_1^2}{E_1}+\frac{1-\nu_2^2}{E_2}\right)\right]^{-1/2}",
                 s["Cp"] / 1000),
            step("Contact stress", r"\sigma_c = C_p\sqrt{\frac{K_v W_t}{b\cos\phi}\left(\frac{1}{r_1}+\frac{1}{r_2}\right)}",
                 s["sc"], "stress"),
            step("Contact ratio", r"\varepsilon_\alpha = \frac{\sqrt{r_{a1}^2-r_{b1}^2}+\sqrt{r_{a2}^2-r_{b2}^2}-a\sin\phi}{\pi m\cos\phi}",
                 eps),
        ],
        "series": [
            series("sb_b", "Pinion bending stress", bs, sb_l, x_label="b", y_label="σ",
                   x_dim="length", y_dim="stress", group=grp,
                   markers=[{"x": b, "label": "current"}],
                   ref_lines=[{"y": St1 / nb_t, "label": "bending allow."}]),
            series("sc_b", "Contact stress", bs, sc_l, x_label="b", y_label="σc", x_dim="length",
                   y_dim="stress", group=grp,
                   ref_lines=[{"y": Sc / nc_t, "label": "contact allow."}]),
        ],
        "tables": [table("Gear geometry", [
            {"key": "q", "label": "Quantity"}, {"key": "p", "label": "Pinion"},
            {"key": "g", "label": "Gear"}], [
            {"q": "Teeth z", "p": int(z1), "g": int(z2)},
            {"q": "Pitch diameter (mm)", "p": fmt(d1 * 1000, 4), "g": fmt(d2 * 1000, 4)},
            {"q": "Tip diameter (mm)", "p": fmt((d1 + 2 * m) * 1000, 4), "g": fmt((d2 + 2 * m) * 1000, 4)},
            {"q": "Root diameter (mm)", "p": fmt((d1 - 2.5 * m) * 1000, 4), "g": fmt((d2 - 2.5 * m) * 1000, 4)},
            {"q": "Base diameter (mm)", "p": fmt(2 * rb1 * 1000, 4), "g": fmt(2 * rb2 * 1000, 4)},
            {"q": "Speed (rpm)", "p": fmt(n1, 4), "g": fmt(n1 / u, 4)},
            {"q": "Torque (N·m)", "p": fmt(T1, 4), "g": fmt(T1 * u, 4)},
            {"q": "Bending safety factor", "p": fmt(SF1, 3), "g": fmt(SF2, 3)},
        ])],
        "diagram": {"z1": int(z1), "z2": int(z2), "m": fmt(m * 1000, 3),
                    "d1": fmt(d1 * 1000, 4), "d2": fmt(d2 * 1000, 4), "a": fmt(a * 1000, 4),
                    "n1": f"{fmt(n1, 4)} rpm", "n2": f"{fmt(n1 / u, 4)} rpm",
                    "Wt": f"{fmt(Wt, 4)} N", "SF": fmt(SF, 3), "SH": fmt(SH, 3),
                    "ok": SF >= nb_t and SH >= nc_t},
        "notes": [
            "Lewis + Barth velocity factor and the Hertz contact equation (Shigley §14-1, 14-5) give a "
            "preliminary sizing. Final design should follow AGMA 2001 or ISO 6336 with load "
            "distribution, overload and reliability factors.",
            "Lewis Y values are tabulated for 20° full-depth teeth and are used as an approximation "
            "for other pressure angles.",
        ],
    }


SPUR_GEAR = Calculator(
    id="spur_gear",
    governing=["P", "T1", "n1", "m", "z1", "z2", "b"],
    title="Spur gear pair",
    category="Gears",
    summary="Gear geometry, tooth bending (Lewis) and surface contact (Hertz) stresses with safety "
            "factors for a spur gear pair.",
    description=(
        "Computes pitch geometry, contact ratio and the transmitted load, then the Lewis tooth "
        "bending stress with a Barth velocity factor and the Hertz contact stress at the pitch "
        "point. Safety factors use typical AGMA grade-1 allowables for the chosen materials."
    ),
    params=[
        Param("m", "Module m", dim="length", default=2, unit="mm", min=0, group="Geometry"),
        Param("z1", "Pinion teeth z1", default=20, min=8, group="Geometry"),
        Param("z2", "Gear teeth z2", default=50, min=8, group="Geometry"),
        Param("b", "Face width b", dim="length", default=25, unit="mm", min=0, group="Geometry"),
        Param("phi", "Pressure angle", kind="select", default="20",
              options=[{"value": "20", "label": "20°"}, {"value": "25", "label": "25°"},
                       {"value": "14.5", "label": "14.5°"}], group="Geometry"),
        Param("input", "Load given as", kind="select", default="power",
              options=[{"value": "power", "label": "Power + speed"},
                       {"value": "torque", "label": "Pinion torque + speed"}], group="Load"),
        Param("P", "Power P", dim="power", default=3, unit="kW", min=0, group="Load",
              show_if={"input": ["power"]}),
        Param("T1", "Pinion torque T1", dim="torque", default=20, unit="N*m", group="Load",
              show_if={"input": ["torque"]}),
        Param("n1", "Pinion speed n1", dim="speed", default=1450, unit="rpm", min=0, group="Load"),
        Param("finish", "Tooth manufacture", kind="select", default="cut",
              options=[{"value": k, "label": v[0]} for k, v in KV.items()], group="Quality"),
        Param("mat1", "Pinion material", kind="select", default="steel_300hb",
              options=[{"value": k, "label": v[0]} for k, v in GEAR_MATERIALS.items()],
              group="Materials"),
        Param("mat2", "Gear material", kind="select", default="steel_300hb",
              options=[{"value": k, "label": v[0]} for k, v in GEAR_MATERIALS.items()],
              group="Materials"),
        Param("n_bend", "Target bending safety factor", default=1.5, min=1, group="Design"),
        Param("n_contact", "Target contact safety factor", default=1.2, min=1, group="Design"),
    ],
    outputs=[
        Output("SF", "Bending safety factor (min)", primary=True, sig=3),
        Output("SH", "Contact safety factor", primary=True, sig=3),
        Output("sc", "Contact stress σc", "stress", primary=True),
        Output("sb1", "Pinion bending stress", "stress"),
        Output("sb2", "Gear bending stress", "stress"),
        Output("Wt", "Tangential load Wt", "force"),
        Output("T1", "Pinion torque", "torque"),
        Output("T2", "Gear torque", "torque"),
        Output("n2", "Gear speed", "speed"),
        Output("P", "Power", "power", unit="kW"),
        Output("V", "Pitch-line velocity", "velocity"),
        Output("Kv", "Velocity factor Kv", sig=3),
        Output("d1", "Pinion pitch diameter", "length"),
        Output("d2", "Gear pitch diameter", "length"),
        Output("a", "Centre distance", "length"),
        Output("eps", "Contact ratio εα", sig=3),
        Output("u", "Gear ratio", sig=4),
    ],
    compute=_compute_spur,
    diagram="spur_gear",
    formulas=[r"\sigma = \frac{K_v W_t}{b\,m\,Y}",
              r"\sigma_c = C_p\sqrt{\frac{K_v W_t}{b\cos\phi}\left(\frac{1}{r_1}+\frac{1}{r_2}\right)}",
              r"W_t = \frac{2T_1}{d_1},\quad d = m z,\quad a = \frac{m(z_1+z_2)}{2}"],
    references=["Shigley's Mechanical Engineering Design, 10th ed., ch. 13 (geometry) and §14-1, §14-5",
                "AGMA 2001-D04 (allowable stress numbers)", "ISO 6336 (detailed rating)"],
    keywords=["gear", "spur gear", "lewis", "tooth bending", "contact stress", "pitting", "module",
              "gear ratio", "center distance", "hertz", "gearbox"],
    presets=[
        {"label": "Small gearbox, 3 kW @ 1450 rpm", "values": {"m": {"value": 2, "unit": "mm"},
         "z1": 20, "z2": 50, "b": {"value": 25, "unit": "mm"}, "P": {"value": 3, "unit": "kW"}}},
        {"label": "Heavy duty, carburized", "values": {"m": {"value": 4, "unit": "mm"},
         "z1": 22, "z2": 66, "b": {"value": 50, "unit": "mm"}, "P": {"value": 45, "unit": "kW"},
         "n1": {"value": 1000, "unit": "rpm"}, "finish": "ground",
         "mat1": "steel_carburized", "mat2": "steel_carburized"}},
    ],
)

CALCULATORS: List[Calculator] = [SPUR_GEAR]
