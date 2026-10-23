"""Bearing calculators: rating life (ISO 281), bearing finder, required load rating."""
import math
from typing import Any, Dict, List, Optional

from ..core import (Calculator, CalcError, Output, Param, check, fmt, from_canonical,
                    series, step, table)
from . import data
from .data import TYPES, by_type, designation_options, fmt_env, limiting_speed, skf_links, \
    variant_designation
from .theory import (A1, CONTAMINATION, VG_NU100, LoadError, life_set, nu_at_temperature,
                     rated_viscosity)

CATEGORY = "Bearings"
REFERENCES = [
    "ISO 281:2007 — Rolling bearings: dynamic load ratings and rating life",
    "ISO 76:2006 — Rolling bearings: static load ratings",
    "ISO 15 / ISO 355 — boundary dimensions (radial / tapered roller bearings)",
    "SKF Rolling bearings catalogue — selection methodology (data here are typical values, not SKF's)",
]
DATA_NOTE = ("Load ratings and speeds are typical multi-manufacturer values — confirm the certified "
             "values on the manufacturer's product page before release.")

DEFAULT_DES = {"dgbb": "6205", "acbb": "7205 BE", "crb": "NU 205", "trb": "30205",
               "sabb": "1205", "srb": "22205", "tbb": "51105"}

TYPE_OPTIONS = [{"value": k, "label": v["label"]} for k, v in TYPES.items()]

RELIABILITY_OPTIONS = [{"value": k, "label": f"{k} %  (a1 = {v:g})"} for k, v in A1.items()]

LOAD_FACTOR_OPTIONS = [
    {"value": "1.0", "label": "Steady, no shocks (fd = 1.0)"},
    {"value": "1.2", "label": "Light shocks — electric motors, fans (fd = 1.2)"},
    {"value": "1.5", "label": "Moderate shocks — gearboxes, pumps (fd = 1.5)"},
    {"value": "2.0", "label": "Heavy shocks — crushers, vibrating screens (fd = 2.0)"},
]

CONTAMINATION_OPTIONS = [{"value": k, "label": v[0]} for k, v in CONTAMINATION.items()]

VG_OPTIONS = [{"value": k, "label": f"ISO VG {k}"} for k in VG_NU100]

SEAL_OPTIONS = [
    {"value": "open", "label": "Open"},
    {"value": "2z", "label": "Shielded both sides (-2Z)"},
    {"value": "2rsh", "label": "Contact seals both sides (-2RSH)"},
]

APPLICATIONS = [
    ("household", "Household appliances, hand tools (300–3 000 h)", 2000),
    ("intermittent", "Intermittent use, power tools (3 000–8 000 h)", 5000),
    ("intermittent_hr", "Intermittent, high reliability: conveyors, cranes (8 000–12 000 h)", 10000),
    ("8h_partial", "8 h/day, not fully utilised: gearboxes, motors (10 000–25 000 h)", 20000),
    ("8h_full", "8 h/day, fully utilised: machine tools, fans (20 000–30 000 h)", 25000),
    ("24h", "24 h continuous: pumps, compressors, mills (40 000–50 000 h)", 45000),
    ("24h_hr", "24 h, high reliability: power stations, mines (60 000–100 000 h)", 80000),
    ("custom", "Custom life…", None),
]
APPLICATION_OPTIONS = [{"value": k, "label": lbl} for k, lbl, _ in APPLICATIONS]
APPLICATION_LIFE = {k: h for k, _, h in APPLICATIONS}

PAIRED_NOTE = ("Angular contact and tapered roller bearings are normally mounted in pairs; the "
               "induced axial load from the opposite bearing is not included here.")


def _kN(v: float) -> str:
    return f"{fmt(v / 1000.0, 3)} kN"


def _h(v: Optional[float]) -> str:
    if v is None or not math.isfinite(v):
        return "∞"
    return f"{fmt(v, 3)} h"


def _lubrication(x: Dict[str, Any]) -> Dict[str, Any]:
    if x["lube_mode"] == "iso_vg":
        nu = nu_at_temperature(x["vg"], x["temp"])
        return {"nu": nu, "desc": f"ISO VG {x['vg']} at {fmt(x['temp'], 3)} °C → ν = {fmt(nu, 3)} mm²/s"}
    if x["nu"] <= 0:
        raise CalcError("Operating viscosity must be positive.")
    return {"nu": x["nu"], "desc": f"ν = {fmt(x['nu'], 3)} mm²/s at operating temperature"}


def _lube_params(group: str = "Lubrication", advanced: bool = False) -> List[Param]:
    return [
        Param("lube_mode", "Lubricant viscosity from", kind="select", default="direct",
              options=[{"value": "direct", "label": "Viscosity at operating temperature"},
                       {"value": "iso_vg", "label": "ISO VG grade + temperature"}],
              group=group, advanced=advanced),
        Param("nu", "Operating viscosity ν", dim="kin_viscosity", default=20, min=0, group=group,
              advanced=advanced, show_if={"lube_mode": ["direct"]},
              help="Typical grease base oils: 15–100 mm²/s at operating temperature."),
        Param("vg", "Oil grade", kind="select", default="68", options=VG_OPTIONS, group=group,
              advanced=advanced, show_if={"lube_mode": ["iso_vg"]}),
        Param("temp", "Operating temperature", dim="temperature", default=70, unit="degC",
              group=group, advanced=advanced, show_if={"lube_mode": ["iso_vg"]}),
        Param("contamination", "Cleanliness", kind="select", default="normal",
              options=CONTAMINATION_OPTIONS, group=group, advanced=advanced,
              help="Contamination factor eC, ISO 281 Table 13."),
    ]


# --------------------------------------------------------------------------
# 1. Bearing rating life
# --------------------------------------------------------------------------

def _selected_bearing(x: Dict[str, Any]):
    t = x["btype"]
    if t == "custom":
        if x["c_D"] <= x["c_d"] or x["c_d"] <= 0:
            raise CalcError("Custom bearing: outer diameter D must exceed bore d > 0.")
        if x["c_C"] <= 0 or x["c_C0"] <= 0:
            raise CalcError("Custom bearing: C and C0 must be positive.")
        b = {"base": "custom", "type": "custom", "series": "custom",
             "d": from_canonical(x["c_d"], "length"), "D": from_canonical(x["c_D"], "length"),
             "B": from_canonical(x["c_B"], "length"), "C": x["c_C"], "C0": x["c_C0"],
             "Pu": x["c_Pu"], "n_ref": math.inf, "n_lim": x["c_nlim"] or math.inf,
             "skf": "Custom bearing", "source": "user"}
        custom = {"X": x["c_X"], "Y": x["c_Y"], "element": x["c_elem"]}
        return b, custom, "open"
    b = data.get(x[f"des_{t}"])
    if b is None:
        raise CalcError("Unknown bearing designation.")
    seal = x["seal"] if t == "dgbb" else "open"
    return b, None, seal


def _compute_life(x: Dict[str, Any]) -> Dict[str, Any]:
    b, custom, seal = _selected_bearing(x)
    Fr, Fa, n = x["Fr"], x["Fa"], x["n"]
    if n <= 0:
        raise CalcError("Rotational speed must be positive.")
    fd = float(x["fd"])
    a1 = A1[x["reliability"]]
    lube = _lubrication(x)
    try:
        r = life_set(b, Fr, Fa, n, fd=fd, a1=a1, nu=lube["nu"], contamination=x["contamination"],
                     custom=custom)
    except LoadError as e:
        raise CalcError(str(e))

    L_req = x["L_req"]
    n_lim = limiting_speed(b, seal) if custom is None else b["n_lim"]
    designation = variant_designation(b, seal) if custom is None else b["skf"]
    shock = fd >= 1.5
    s0_min = 2.0 if shock else 1.0

    checks = [
        check("Modified rating life", r["Lnmh"] >= L_req,
              f"Lnmh = {_h(r['Lnmh'])} against the required {_h(L_req)}.",
              value=r["Lnmh"], limit=L_req),
    ]
    if r["L10h"] < L_req <= r["Lnmh"]:
        checks.append(check("Basic life below target", False,
                            f"L10h = {_h(r['L10h'])} only meets the target thanks to aISO = "
                            f"{fmt(r['aISO'], 3)}; keep lubrication and sealing as assumed.", warn=True))
    checks.append(check("Static safety", r["s0"] >= s0_min,
                        f"s0 = C0/P0 = {fmt(r['s0'], 3)} (need ≥ {fmt(s0_min, 2)}"
                        f"{' with shock loads' if shock else ''}).",
                        warn=r["s0"] >= 1.0, value=r["s0"], limit=s0_min))
    if math.isfinite(n_lim):
        checks.append(check("Speed", n <= n_lim,
                            f"n = {fmt(n, 4)} rpm vs limiting speed {fmt(n_lim, 3)} rpm"
                            f"{' (contact seals)' if seal == '2rsh' else ''}.",
                            value=n, limit=n_lim))
    if r["kappa"] < 1.0:
        msg = ("κ < 0.1 is outside the ISO 281 method (aISO evaluated at κ = 0.1). "
               if r["kappa"] < 0.1 else "")
        checks.append(check("Lubrication", False,
                            f"{msg}κ = {fmt(r['kappa'], 3)} < 1: mixed lubrication. A higher viscosity "
                            f"grade (κ ≥ 1, ideally 1–4) markedly extends life.", warn=True))
    element = custom["element"] if custom else TYPES[b["type"]]["element"]
    min_ratio = 0.01 if element == "ball" else 0.02
    if r["P"] < min_ratio * b["C"]:
        checks.append(check("Minimum load", False,
                            f"P is below ~{min_ratio:g}·C: rolling elements may skid. Ensure a minimum "
                            f"load or choose a smaller bearing.", warn=True))

    notes = [DATA_NOTE, f"Lubrication: {lube['desc']}."]
    if custom is None and b["type"] in ("acbb", "trb"):
        notes.append(PAIRED_NOTE)
    if fd != 1.0:
        notes.append(f"Loads multiplied by load factor fd = {fd:g} before computing P.")

    # Life vs load (scale both components together).
    x_is_axial = Fr == 0
    base_load = Fa if x_is_axial else Fr
    xs, l10s, lnms = [], [], []
    for i in range(40):
        s = 0.25 + (2.75 - 0.25) * i / 39
        try:
            ri = life_set(b, Fr * s, Fa * s, n, fd=fd, a1=a1, nu=lube["nu"],
                          contamination=x["contamination"], custom=custom)
        except LoadError:
            continue
        xs.append(base_load * s)
        l10s.append(ri["L10h"])
        lnms.append(ri["Lnmh"])
    plots = []
    if len(xs) >= 2:
        lbl = "Fa" if x_is_axial else "Fr"
        common = dict(x_label=lbl, y_label="life", x_dim="force", y_dim="duration_h",
                      x_unit="kN", group="Rating life vs load (load ratio kept)", y_scale="log",
                      markers=[{"x": base_load, "label": "current"}],
                      ref_lines=[{"y": L_req, "label": f"required {fmt(L_req, 3)} h"}])
        plots = [series("lnmh", "Lnmh (modified)", xs, lnms, **common),
                 series("l10h", "L10h (basic)", xs, l10s, **{**common, "markers": [], "ref_lines": []})]

    # Same-bore alternatives.
    tables = []
    if custom is None:
        rows = []
        for alt in data.BEARINGS:
            if abs(alt["d"] - b["d"]) > 1e-9:
                continue
            try:
                ra = life_set(alt, Fr, Fa, n, fd=fd, a1=a1, nu=lube["nu"],
                              contamination=x["contamination"])
            except LoadError:
                continue
            alt_seal = seal if alt["type"] == "dgbb" else "open"
            nl = limiting_speed(alt, alt_seal)
            ok = ra["Lnmh"] >= L_req and ra["s0"] >= 1.0 and n <= nl
            rows.append({
                "designation": variant_designation(alt, alt_seal), "type": TYPES[alt["type"]]["label"],
                "env": fmt_env(alt), "C": fmt(alt["C"] / 1000, 3), "L10h": fmt(ra["L10h"], 3),
                "Lnmh": fmt(ra["Lnmh"], 3), "s0": fmt(ra["s0"], 3), "n_lim": fmt(nl, 3),
                "_links": skf_links(alt, alt_seal), "_status": "ok" if ok else "fail",
                "_sort": ra["Lnmh"], "_base": alt["base"],
            })
        rows.sort(key=lambda r_: -r_["_sort"])
        for r_ in rows:
            r_.pop("_sort")
        tables.append(table(
            f"Bearings with the same {fmt(b['d'], 3)} mm bore under this load",
            [{"key": "designation", "label": "Designation"}, {"key": "type", "label": "Type"},
             {"key": "env", "label": "d×D×B"}, {"key": "C", "label": "C", "unit": "kN"},
             {"key": "L10h", "label": "L10h", "unit": "h"}, {"key": "Lnmh", "label": "Lnmh", "unit": "h"},
             {"key": "s0", "label": "s0"}, {"key": "n_lim", "label": "n lim", "unit": "rpm"}],
            rows[:16], highlight={"_base": b["base"]}, note=DATA_NOTE))

    steps = [
        step("Load ratio vs e", r"F_a/F_r \text{ vs } e" + (f" = {fmt(r['e'], 3)}" if r["e"] else ""),
             Fa / Fr if Fr > 0 else None),
        step("Equivalent dynamic load", r["rule"] + r",\; X=" + fmt(r["X"], 3) + r",\; Y=" + fmt(r["Y"], 3),
             r["P"], "force", "kN"),
        step("Basic rating life", r"L_{10} = (C/P)^{p},\; p = " + ("3" if r["p"] == 3 else r"10/3")
             + r"\;[10^6\,\text{rev}]", r["L10"]),
        step("Basic rating life in hours", r"L_{10h} = \frac{10^6}{60\,n} L_{10}", r["L10h"], "duration_h"),
        step("Mean diameter", r"d_m = (d + D)/2", r["dm"] / 1000.0, "length"),
        step("Rated viscosity", (r"\nu_1 = 4500\,n^{-0.5} d_m^{-0.5}" if n >= 1000
                                 else r"\nu_1 = 45000\,n^{-0.83} d_m^{-0.5}"), r["nu1"], "kin_viscosity"),
        step("Viscosity ratio", r"\kappa = \nu / \nu_1", r["kappa"]),
        step("Life modification factor", r"a_{ISO} = f\left(\frac{e_C C_u}{P}, \kappa\right),\; e_C = "
             + fmt(r["ec"], 2), r["aISO"]),
        step("Modified rating life", r"L_{nmh} = a_1\, a_{ISO}\, L_{10h},\; a_1 = " + fmt(a1, 3),
             r["Lnmh"], "duration_h"),
        step("Static safety", r"s_0 = C_0 / P_0", r["s0"]),
    ]

    values = {
        "designation": designation, "Lnmh": r["Lnmh"], "L10h": r["L10h"], "s0": r["s0"],
        "P": r["P"], "P0": r["P0"], "L10": r["L10"], "aISO": r["aISO"], "kappa": r["kappa"],
        "nu": lube["nu"], "nu1": r["nu1"], "X": r["X"], "Y": r["Y"], "e": r["e"],
        "n_lim": n_lim if math.isfinite(n_lim) else None,
    }
    element_kind = {"dgbb": "ball", "acbb": "angular", "sabb": "ball", "crb": "roller",
                    "srb": "barrel", "trb": "taper", "tbb": "thrust"}.get(b["type"], element)
    ok = all(c["status"] == "ok" for c in checks)
    return {
        "values": values,
        "checks": checks,
        "steps": steps,
        "series": plots,
        "tables": tables,
        "links": skf_links(b, seal) if custom is None else [],
        "notes": notes,
        "diagram": {
            "mode": "life", "kind": element_kind, "designation": designation,
            "type": TYPES[b["type"]]["label"] if custom is None else "Custom",
            "d": b["d"], "D": b["D"], "B": b["B"],
            "Fr": _kN(Fr) if Fr > 0 else None, "Fa": _kN(Fa) if Fa > 0 else None,
            "L10h": _h(r["L10h"]), "Lnmh": _h(r["Lnmh"]), "s0": fmt(r["s0"], 3),
            "n": f"{fmt(n, 4)} rpm", "ok": ok, "life_ok": r["Lnmh"] >= L_req,
        },
    }


def _designation_params() -> List[Param]:
    params = []
    for t in TYPES:
        params.append(Param(f"des_{t}", "Designation", kind="select", default=DEFAULT_DES[t],
                            options=designation_options(t), group="Bearing",
                            show_if={"btype": [t]}))
    return params


_custom_show = {"btype": ["custom"]}

BEARING_LIFE = Calculator(
    id="bearing_life",
    title="Bearing rating life (ISO 281)",
    category=CATEGORY,
    summary="Basic and modified rating life, static safety and speed check for a chosen bearing, "
            "with same-bore alternatives and SKF part links.",
    description=(
        "Computes the equivalent dynamic load P from the radial and axial load using the "
        "type-specific X/Y rules, the basic rating life L10 = (C/P)^p, and the ISO 281 modified "
        "rating life Lnm = a1·aISO·L10, where aISO accounts for lubrication (viscosity ratio κ), "
        "contamination (eC) and the fatigue load limit Cu. Also checks static safety s0 = C0/P0 "
        "and the limiting speed."
    ),
    params=[
        Param("btype", "Bearing type", kind="select", default="dgbb",
              options=TYPE_OPTIONS + [{"value": "custom", "label": "Custom (enter ratings)…"}],
              group="Bearing"),
        *_designation_params(),
        Param("seal", "Sealing", kind="select", default="open", options=SEAL_OPTIONS, group="Bearing",
              show_if={"btype": ["dgbb"]}),
        Param("c_elem", "Rolling elements", kind="select", default="ball",
              options=[{"value": "ball", "label": "Balls (p = 3)"},
                       {"value": "roller", "label": "Rollers (p = 10/3)"}],
              group="Bearing", show_if=_custom_show),
        Param("c_d", "Bore d", dim="length", default=25, unit="mm", group="Bearing", show_if=_custom_show),
        Param("c_D", "Outer diameter D", dim="length", default=52, unit="mm", group="Bearing",
              show_if=_custom_show),
        Param("c_B", "Width B", dim="length", default=15, unit="mm", group="Bearing", show_if=_custom_show),
        Param("c_C", "Dynamic load rating C", dim="force", default=14.8, unit="kN", group="Bearing",
              show_if=_custom_show),
        Param("c_C0", "Static load rating C0", dim="force", default=7.8, unit="kN", group="Bearing",
              show_if=_custom_show),
        Param("c_Pu", "Fatigue load limit Pu", dim="force", default=0.335, unit="kN", group="Bearing",
              show_if=_custom_show),
        Param("c_X", "Radial factor X", default=1.0, group="Bearing", show_if=_custom_show),
        Param("c_Y", "Axial factor Y", default=0.0, group="Bearing", show_if=_custom_show),
        Param("c_nlim", "Limiting speed (0 = not checked)", dim="speed", default=0, group="Bearing",
              show_if=_custom_show),
        Param("Fr", "Radial load Fr", dim="force", default=1.2, unit="kN", min=0, group="Loads"),
        Param("Fa", "Axial load Fa", dim="force", default=0.2, unit="kN", min=0, group="Loads"),
        Param("n", "Rotational speed n", dim="speed", default=1500, unit="rpm", min=0, group="Loads"),
        Param("fd", "Operating conditions", kind="select", default="1.0", options=LOAD_FACTOR_OPTIONS,
              group="Loads"),
        *_lube_params(),
        Param("L_req", "Required life", dim="duration_h", default=20000, unit="hour", group="Design"),
        Param("reliability", "Reliability", kind="select", default="90", options=RELIABILITY_OPTIONS,
              group="Design", advanced=True),
    ],
    outputs=[
        Output("designation", "Bearing", primary=True),
        Output("Lnmh", "Modified rating life Lnmh", "duration_h", primary=True, sig=3),
        Output("L10h", "Basic rating life L10h", "duration_h", primary=True, sig=3),
        Output("s0", "Static safety s0", primary=True, sig=3),
        Output("P", "Equivalent dynamic load P", "force", unit="kN"),
        Output("P0", "Equivalent static load P0", "force", unit="kN"),
        Output("L10", "L10 (million revolutions)", sig=4),
        Output("aISO", "Life modification factor aISO", sig=3),
        Output("kappa", "Viscosity ratio κ", sig=3),
        Output("nu", "Operating viscosity ν", "kin_viscosity", sig=3),
        Output("nu1", "Rated viscosity ν1", "kin_viscosity", sig=3),
        Output("X", "Radial factor X", sig=3),
        Output("Y", "Axial factor Y", sig=3),
        Output("e", "Limit e", sig=3),
        Output("n_lim", "Limiting speed", "speed", sig=3),
    ],
    compute=_compute_life,
    diagram="bearing_section",
    formulas=[r"P = X F_r + Y F_a", r"L_{10} = \left(\frac{C}{P}\right)^{p}",
              r"L_{10h} = \frac{10^6}{60 n} L_{10}", r"L_{nm} = a_1\, a_{ISO}\, L_{10}",
              r"s_0 = \frac{C_0}{P_0}"],
    references=REFERENCES,
    keywords=["bearing", "bearing life", "L10", "L10h", "ISO 281", "rating life", "aISO",
              "rolling bearing", "ball bearing", "roller bearing", "SKF", "static safety",
              "deep groove", "tapered roller", "spherical roller"],
    presets=[
        {"label": "Electric motor 6205 @ 3000 rpm",
         "values": {"btype": "dgbb", "des_dgbb": "6205", "Fr": {"value": 0.8, "unit": "kN"},
                    "Fa": {"value": 0.1, "unit": "kN"}, "n": {"value": 3000, "unit": "rpm"},
                    "fd": "1.2", "seal": "2z"}},
        {"label": "Gearbox output, tapered 30208",
         "values": {"btype": "trb", "des_trb": "30208", "Fr": {"value": 6, "unit": "kN"},
                    "Fa": {"value": 2.5, "unit": "kN"}, "n": {"value": 300, "unit": "rpm"},
                    "fd": "1.5", "lube_mode": "iso_vg", "vg": "220", "temp": {"value": 70, "unit": "degC"},
                    "L_req": {"value": 25000, "unit": "hour"}}},
        {"label": "Conveyor pulley, spherical 22208",
         "values": {"btype": "srb", "des_srb": "22208", "Fr": {"value": 12, "unit": "kN"},
                    "Fa": {"value": 1, "unit": "kN"}, "n": {"value": 120, "unit": "rpm"},
                    "contamination": "typical", "nu": {"value": 100, "unit": "mm**2/s"}}},
    ],
)


# --------------------------------------------------------------------------
# 2. Bearing selector
# --------------------------------------------------------------------------

def _compute_selector(x: Dict[str, Any]) -> Dict[str, Any]:
    Fr, Fa, n = x["Fr"], x["Fa"], x["n"]
    if n <= 0:
        raise CalcError("Rotational speed must be positive.")
    if Fr <= 0 and Fa <= 0:
        raise CalcError("Apply a radial and/or axial load.")
    L_req = x["L_req"] if x["application"] == "custom" else APPLICATION_LIFE[x["application"]]
    if L_req <= 0:
        raise CalcError("Required life must be positive.")
    bmin = from_canonical(x["bore_min"], "length")
    bmax = from_canonical(x["bore_max"], "length")
    if bmax < bmin:
        raise CalcError("Maximum bore must not be smaller than minimum bore.")
    od_max = from_canonical(x["od_max"], "length")
    w_max = from_canonical(x["width_max"], "length")
    seal = x["seal"]
    fd = float(x["fd"])
    a1 = A1[x["reliability"]]
    basis = x["basis"]
    s0_min = x["s0_min"]

    want = x["btype"]
    types = list(TYPES) if want == "any" else [want]
    if seal in ("2z", "2rsh"):
        types = [t for t in types if t == "dgbb"]

    cands = []
    skipped_load = set()
    for b in data.BEARINGS:
        if b["type"] not in types:
            continue
        if not (bmin - 1e-9 <= b["d"] <= bmax + 1e-9):
            continue
        if od_max > 0 and b["D"] > od_max + 1e-9:
            continue
        if w_max > 0 and b["B"] > w_max + 1e-9:
            continue
        try:
            r = life_set(b, Fr, Fa, n, fd=fd, a1=a1, nu=x["nu"], contamination=x["contamination"])
        except LoadError:
            skipped_load.add(TYPES[b["type"]]["label"])
            continue
        s = seal if (seal in ("2z", "2rsh") and b["type"] == "dgbb") else "open"
        nl = limiting_speed(b, s)
        life = r["Lnmh"] if basis == "Lnmh" else a1 * r["L10h"]
        meets_life, s0_ok, speed_ok = life >= L_req, r["s0"] >= s0_min, n <= nl
        cands.append({"b": b, "r": r, "seal": s, "n_lim": nl, "life": life,
                      "ok": meets_life and s0_ok and speed_ok,
                      "why": [w for w, flag in (("life", meets_life), ("s0", s0_ok), ("speed", speed_ok))
                              if not flag]})

    good = sorted([c for c in cands if c["ok"]], key=lambda c: (c["b"]["D"], c["b"]["B"], -c["life"]))
    bad = sorted([c for c in cands if not c["ok"]], key=lambda c: -c["life"])
    ranked = good + bad
    best = good[0] if good else None

    rows = []
    for c in ranked[:24]:
        b = c["b"]
        rows.append({
            "designation": variant_designation(b, c["seal"]), "type": TYPES[b["type"]]["label"],
            "env": fmt_env(b), "C": fmt(b["C"] / 1000, 3), "life": fmt(c["life"], 3),
            "s0": fmt(c["r"]["s0"], 3), "n_lim": fmt(c["n_lim"], 3),
            "variants": "-2Z, -2RSH" if b["type"] == "dgbb" and c["seal"] == "open" and b["source"] != "user" else "",
            "issue": "" if c["ok"] else "fails " + ", ".join(c["why"]),
            "_links": skf_links(b, c["seal"]), "_status": "ok" if c["ok"] else "fail", "_base": b["base"],
        })
    life_lbl = "Lnmh" if basis == "Lnmh" else "L10h·a1"

    checks = []
    if best:
        checks.append(check("Suitable bearing found", True,
                            f"{len(good)} of {len(cands)} candidates meet life ≥ {_h(L_req)}, "
                            f"s0 ≥ {fmt(s0_min, 2)} and the speed limit. Smallest envelope: "
                            f"{variant_designation(best['b'], best['seal'])} ({fmt_env(best['b'])})."))
    else:
        checks.append(check("Suitable bearing found", False,
                            f"None of {len(cands)} candidates meets the requirements. Widen the bore range, "
                            f"allow other bearing types or a larger series, or reduce the required life."))
    notes = [DATA_NOTE,
             f"Life basis: {'modified rating life Lnmh (ISO 281)' if basis == 'Lnmh' else 'basic rating life L10h × a1'}."]
    if skipped_load:
        notes.append("Skipped (cannot carry this load combination): " + ", ".join(sorted(skipped_load)) + ".")
    if best and best["b"]["type"] in ("acbb", "trb"):
        notes.append(PAIRED_NOTE)

    # Scatter: life vs outer diameter.
    plots = []
    for key, grp, title in (("ok", good, "meets requirements"), ("no", bad, "does not")):
        pts = [(c["b"]["D"] / 1000.0, c["life"]) for c in grp if c["life"] > 0 and math.isfinite(c["life"])]
        if len(pts) >= 1:
            plots.append(series(f"cand_{key}", title, [p[0] for p in pts], [p[1] for p in pts],
                                x_label="D", y_label=life_lbl, x_dim="length", y_dim="duration_h",
                                kind="scatter", group="Candidates: life vs outer diameter", y_scale="log",
                                ref_lines=[{"y": L_req, "label": f"required {fmt(L_req, 3)} h"}]
                                if key == "ok" or not good else []))
    plots = [p for p in plots if len(p["x"]) >= 2]   # a lone point is not a useful plot

    values = {"n_ok": float(len(good)), "L_req": L_req}
    diagram = {"mode": "envelope", "bore_min": bmin, "bore_max": bmax,
               "od_max": od_max or None, "width_max": w_max or None, "ok": bool(best)}
    links = []
    if best:
        b = best["b"]
        values.update({"best": variant_designation(b, best["seal"]), "best_env": fmt_env(b),
                       "best_life": best["life"], "best_s0": best["r"]["s0"],
                       "best_C": b["C"]})
        links = skf_links(b, best["seal"])
        diagram.update({"kind": {"dgbb": "ball", "acbb": "angular", "sabb": "ball", "crb": "roller",
                                 "srb": "barrel", "trb": "taper", "tbb": "thrust"}[b["type"]],
                        "designation": variant_designation(b, best["seal"]), "type": TYPES[b["type"]]["label"],
                        "d": b["d"], "D": b["D"], "B": b["B"], "Fr": _kN(Fr) if Fr > 0 else None,
                        "Fa": _kN(Fa) if Fa > 0 else None, "Lnmh": _h(best["life"]),
                        "s0": fmt(best["r"]["s0"], 3)})
    else:
        values["best"] = "none found"

    return {
        "values": values, "checks": checks, "series": plots, "links": links, "notes": notes,
        "tables": [table("Candidates (meeting requirements first, smallest envelope first)",
                         [{"key": "designation", "label": "Designation"}, {"key": "type", "label": "Type"},
                          {"key": "env", "label": "d×D×B"}, {"key": "C", "label": "C", "unit": "kN"},
                          {"key": "life", "label": life_lbl, "unit": "h"}, {"key": "s0", "label": "s0"},
                          {"key": "n_lim", "label": "n lim", "unit": "rpm"},
                          {"key": "variants", "label": "Sealed variants"}, {"key": "issue", "label": "Issue"}],
                         rows, highlight={"_base": best["b"]["base"]} if best else None, note=DATA_NOTE)],
        "steps": [
            step("Required life", r"L_{req}", L_req, "duration_h"),
            step("Equivalent load per candidate", r"P = X F_r + Y F_a \;(\text{type rules})", None),
            step("Life per candidate", r"L_{10h} = \frac{10^6}{60 n}\left(\frac{C}{P}\right)^p"
                 + (r",\; L_{nmh} = a_1 a_{ISO} L_{10h}" if basis == "Lnmh" else ""), None),
            step("Ranking", r"\text{meets } (L, s_0, n_{lim}) \rightarrow \min D \rightarrow \min B", None),
        ],
        "diagram": diagram,
    }


BEARING_SELECTOR = Calculator(
    id="bearing_selector",
    title="Bearing finder",
    category=CATEGORY,
    summary="Enter loads, speed, required life and the space available — get ranked standard bearings "
            "with part numbers and SKF links.",
    description=(
        "Evaluates every bearing in the database whose bore and envelope fit, using the ISO 281 "
        "equivalent-load rules for its type. Candidates that meet the required life, static safety "
        "and limiting speed are ranked by smallest outer diameter, then width — the most compact "
        "standard bearing first."
    ),
    params=[
        Param("btype", "Bearing type", kind="select", default="dgbb",
              options=[{"value": "any", "label": "Any type"}] + TYPE_OPTIONS, group="Requirements"),
        Param("Fr", "Radial load Fr", dim="force", default=2, unit="kN", min=0, group="Requirements"),
        Param("Fa", "Axial load Fa", dim="force", default=0.3, unit="kN", min=0, group="Requirements"),
        Param("n", "Rotational speed n", dim="speed", default=1500, unit="rpm", min=0, group="Requirements"),
        Param("application", "Application / life target", kind="select", default="8h_partial",
              options=APPLICATION_OPTIONS, group="Requirements"),
        Param("L_req", "Required life", dim="duration_h", default=20000, unit="hour", group="Requirements",
              show_if={"application": ["custom"]}),
        Param("bore_min", "Bore from", dim="length", default=20, unit="mm", group="Space available"),
        Param("bore_max", "Bore to", dim="length", default=40, unit="mm", group="Space available"),
        Param("od_max", "Max outer diameter (0 = any)", dim="length", default=0, unit="mm",
              group="Space available", advanced=True),
        Param("width_max", "Max width (0 = any)", dim="length", default=0, unit="mm",
              group="Space available", advanced=True),
        Param("seal", "Sealing", kind="select", default="any",
              options=[{"value": "any", "label": "Any (open listed)"}] + SEAL_OPTIONS[1:],
              group="Space available"),
        Param("basis", "Life basis", kind="select", default="L10h",
              options=[{"value": "L10h", "label": "Basic life L10h (conservative)"},
                       {"value": "Lnmh", "label": "Modified life Lnmh (ISO 281, lubrication)"}],
              group="Design", advanced=True),
        Param("fd", "Operating conditions", kind="select", default="1.0", options=LOAD_FACTOR_OPTIONS,
              group="Design", advanced=True),
        Param("reliability", "Reliability", kind="select", default="90", options=RELIABILITY_OPTIONS,
              group="Design", advanced=True),
        Param("nu", "Operating viscosity ν", dim="kin_viscosity", default=20, group="Design", advanced=True),
        Param("contamination", "Cleanliness", kind="select", default="normal",
              options=CONTAMINATION_OPTIONS, group="Design", advanced=True),
        Param("s0_min", "Minimum static safety s0", default=1.0, min=0, group="Design", advanced=True),
    ],
    outputs=[
        Output("best", "Recommended bearing", primary=True),
        Output("best_life", "Life of recommendation", "duration_h", primary=True, sig=3),
        Output("best_s0", "Static safety s0", primary=True, sig=3),
        Output("best_env", "Envelope d×D×B"),
        Output("best_C", "Dynamic load rating C", "force", unit="kN", sig=3),
        Output("L_req", "Required life", "duration_h", sig=3),
        Output("n_ok", "Candidates meeting requirements", sig=3),
    ],
    compute=_compute_selector,
    diagram="bearing_envelope",
    formulas=[r"P = X F_r + Y F_a", r"L_{10h} = \frac{10^6}{60 n}\left(\frac{C}{P}\right)^{p}",
              r"s_0 = \frac{C_0}{P_0}"],
    references=REFERENCES,
    keywords=["bearing selection", "select bearing", "find bearing", "which bearing", "bearing finder",
              "part number", "SKF", "bearing catalogue", "bearing size", "shaft bearing"],
    presets=[
        {"label": "Pump shaft, 24 h", "values": {"btype": "any", "Fr": {"value": 4, "unit": "kN"},
                                                 "Fa": {"value": 0.8, "unit": "kN"},
                                                 "n": {"value": 2900, "unit": "rpm"}, "application": "24h",
                                                 "bore_min": {"value": 30, "unit": "mm"},
                                                 "bore_max": {"value": 50, "unit": "mm"}}},
        {"label": "Sealed bearing for a wheel hub", "values": {"btype": "dgbb", "seal": "2rsh",
                                                               "Fr": {"value": 1.5, "unit": "kN"},
                                                               "Fa": {"value": 0.4, "unit": "kN"},
                                                               "n": {"value": 600, "unit": "rpm"},
                                                               "application": "intermittent_hr"}},
    ],
)


# --------------------------------------------------------------------------
# 3. Required dynamic load rating
# --------------------------------------------------------------------------

def _compute_required_c(x: Dict[str, Any]) -> Dict[str, Any]:
    P, n, Lh = x["P"], x["n"], x["L_req"]
    if P <= 0 or n <= 0 or Lh <= 0:
        raise CalcError("Load, speed and life must all be positive.")
    element = x["element"]
    p = 3.0 if element == "ball" else 10 / 3
    a1 = A1[x["reliability"]]
    L10 = 60.0 * n * Lh / 1e6                 # million revolutions at a1 = 1
    L10_needed = L10 / a1
    C_req = P * L10_needed ** (1 / p)
    bmin = from_canonical(x["bore_min"], "length")

    thrust_wanted = x["direction"] == "axial"
    rows = []
    best = None
    for t, meta in TYPES.items():
        if meta["element"] != element or meta["thrust"] != thrust_wanted:
            continue
        series_names = sorted({b["series"] for b in by_type(t)})
        for s in series_names:
            pick = next((b for b in sorted(by_type(t), key=lambda b: (b["d"], b["D"]))
                         if b["series"] == s and b["C"] >= C_req and b["d"] >= bmin - 1e-9), None)
            if not pick:
                rows.append({"series": f"{meta['label']} {s}", "designation": "— none in range",
                             "env": "", "C": "", "margin": "", "_status": "fail"})
                continue
            margin = pick["C"] / C_req - 1
            rows.append({"series": f"{meta['label']} {s}", "designation": pick["skf"],
                         "env": fmt_env(pick), "C": fmt(pick["C"] / 1000, 3),
                         "margin": f"+{fmt(100 * margin, 3)} %", "_links": skf_links(pick),
                         "_status": "ok", "_base": pick["base"]})
            if best is None or (pick["D"], pick["B"]) < (best["D"], best["B"]):
                best = pick

    hours_axis = [1000 * (200 ** (i / 39)) for i in range(40)]   # 1 000 … 200 000 h
    c_axis = [P * ((60.0 * n * h / 1e6) / a1) ** (1 / p) for h in hours_axis]
    values = {"C_req": C_req, "L10": L10_needed, "a1": a1}
    links = []
    diagram = {"mode": "envelope", "bore_min": bmin, "ok": best is not None}
    if best:
        values["best"] = best["skf"]
        values["best_C"] = best["C"]
        links = skf_links(best)
        diagram.update({"kind": {"dgbb": "ball", "acbb": "angular", "sabb": "ball", "crb": "roller",
                                 "srb": "barrel", "trb": "taper", "tbb": "thrust"}[best["type"]],
                        "designation": best["skf"], "type": TYPES[best["type"]]["label"],
                        "d": best["d"], "D": best["D"], "B": best["B"],
                        "Lnmh": None, "s0": None})
    else:
        values["best"] = "none in database"

    return {
        "values": values,
        "checks": [check("Bearing available", best is not None,
                         (f"Smallest-envelope bearing with C ≥ {_kN(C_req)}: {best['skf']} ({fmt_env(best)})."
                          if best else f"No {'thrust ' if thrust_wanted else 'radial '}{element} bearing in "
                                       f"the database reaches C = {_kN(C_req)}."))],
        "steps": [
            step("Required life in revolutions", r"L_{10} = \frac{60\,n\,L_{h}}{10^6}\;[10^6\,\text{rev}]", L10),
            step("Correct for reliability", r"L_{10}' = L_{10}/a_1,\; a_1 = " + fmt(a1, 3), L10_needed),
            step("Required dynamic load rating", r"C = P\,(L_{10}')^{1/p},\; p = "
                 + ("3" if p == 3 else r"10/3"), C_req, "force", "kN"),
        ],
        "series": [series("creq", "Required C vs life", hours_axis, c_axis, x_label="L10h", y_label="C",
                          x_dim="duration_h", y_dim="force", y_unit="kN", x_scale="log",
                          markers=[{"x": Lh, "label": "target"}])],
        "tables": [table("Smallest bearing per series with C ≥ required",
                         [{"key": "series", "label": "Series"}, {"key": "designation", "label": "SKF designation"},
                          {"key": "env", "label": "d×D×B"}, {"key": "C", "label": "C", "unit": "kN"},
                          {"key": "margin", "label": "Margin"}],
                         rows, highlight={"_base": best["base"]} if best else None, note=DATA_NOTE)],
        "links": links,
        "notes": [DATA_NOTE, "P is the equivalent dynamic load; for combined loads use the bearing-life "
                             "calculator to get the type-specific X and Y factors."],
        "diagram": diagram,
    }


BEARING_REQUIRED_C = Calculator(
    id="bearing_required_c",
    title="Required load rating C",
    category=CATEGORY,
    summary="Dynamic load rating needed for a target life, and the smallest bearing in every series that has it.",
    description="Inverts the basic rating life equation: C = P·(L10/a1)^(1/p), with L10 from the "
                "target hours and speed. Then lists the smallest standard bearing per series that meets it.",
    params=[
        Param("element", "Rolling elements", kind="select", default="ball",
              options=[{"value": "ball", "label": "Ball bearings (p = 3)"},
                       {"value": "roller", "label": "Roller bearings (p = 10/3)"}], group="Requirements"),
        Param("direction", "Main load direction", kind="select", default="radial",
              options=[{"value": "radial", "label": "Radial (radial bearings)"},
                       {"value": "axial", "label": "Axial only (thrust bearings)"}], group="Requirements"),
        Param("P", "Equivalent dynamic load P", dim="force", default=2, unit="kN", min=0, group="Requirements"),
        Param("n", "Rotational speed n", dim="speed", default=1500, unit="rpm", min=0, group="Requirements"),
        Param("L_req", "Target life", dim="duration_h", default=20000, unit="hour", group="Requirements"),
        Param("reliability", "Reliability", kind="select", default="90", options=RELIABILITY_OPTIONS,
              group="Requirements"),
        Param("bore_min", "Minimum bore (0 = any)", dim="length", default=0, unit="mm",
              group="Requirements", advanced=True),
    ],
    outputs=[
        Output("C_req", "Required dynamic load rating C", "force", unit="kN", primary=True, sig=3),
        Output("best", "Most compact bearing", primary=True),
        Output("best_C", "Its rating C", "force", unit="kN", sig=3),
        Output("L10", "Required L10 (million rev)", sig=4),
        Output("a1", "Reliability factor a1", sig=3),
    ],
    compute=_compute_required_c,
    diagram="bearing_envelope",
    formulas=[r"L_{10} = \frac{60\,n\,L_{10h}}{10^6}", r"C = P\left(\frac{L_{10}}{a_1}\right)^{1/p}"],
    references=REFERENCES,
    keywords=["required load rating", "dynamic load rating", "bearing size", "C required",
              "bearing sizing", "basic rating life"],
    presets=[
        {"label": "Roller bearing, 50 000 h", "values": {"element": "roller", "P": {"value": 15, "unit": "kN"},
                                                        "n": {"value": 500, "unit": "rpm"},
                                                        "L_req": {"value": 50000, "unit": "hour"}}},
    ],
)


CALCULATORS: List[Calculator] = [BEARING_SELECTOR, BEARING_LIFE, BEARING_REQUIRED_C]
