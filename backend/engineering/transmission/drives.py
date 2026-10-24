"""Drive loads: torque from power and speed, and the forces a chain, belt or gear puts on its shaft."""
import math
from typing import Any, Dict

from ..core import Calculator, CalcError, Output, Param, fmt, from_canonical, step

ELEMENTS = [
    {"value": "chain", "label": "Chain sprocket"},
    {"value": "v_belt", "label": "V-belt pulley"},
    {"value": "flat_belt", "label": "Flat belt pulley"},
    {"value": "timing_belt", "label": "Timing (toothed) belt pulley"},
    {"value": "spur", "label": "Spur gear"},
    {"value": "helical", "label": "Helical gear"},
    {"value": "coupling", "label": "Coupling (torque only)"},
]
LABEL = {e["value"]: e["label"] for e in ELEMENTS}

# Effective friction for belt slip (Euler–Eytelwein): a V-belt wedges in its groove, so its
# effective coefficient is several times the flat-belt value.
BELT_MU = {"v_belt": 0.5, "flat_belt": 0.3}
# A timing belt carries the slack side at installation tension only: shaft load ≈ 1.1–1.3 Ft.
TIMING_FACTOR = 1.2


def _compute_drive(x: Dict[str, Any]) -> Dict[str, Any]:
    n_rpm, el, KA = x["n"], x["element"], x["KA"]
    if n_rpm <= 0:
        raise CalcError("Speed must be positive.")
    if KA < 1:
        raise CalcError("The application factor KA is at least 1.")
    omega = n_rpm * 2 * math.pi / 60
    T = x["P"] / omega if x["input"] == "power" else x["T"]
    if T <= 0:
        raise CalcError("Power or torque must be positive.")
    P = T * omega
    Td = KA * T
    steps = [step("Angular speed (rad/s)", r"\omega = \frac{2\pi n}{60}", omega)]
    steps.append(step("Torque", r"T = \frac{P}{\omega}", T, "torque") if x["input"] == "power"
                 else step("Power", r"P = T\,\omega", P, "power", unit="kW"))
    if KA != 1:
        steps.append(step("Design torque", r"T_d = K_A\,T", Td, "torque"))
    values: Dict[str, Any] = {"T": T, "P": P, "Td": Td}
    notes = []
    diagram: Dict[str, Any] = {"element": el, "T": f"{fmt(T)} N·m"}

    if el == "coupling":
        values.update(Ft=None, Fs=0.0)
        notes.append("A flexible coupling transmits torque only; misalignment adds a small "
                     "restoring force, ignored here.")
        return {"values": values, "steps": steps, "checks": [], "notes": notes, "diagram": diagram}

    D = x["D"]
    if D <= 0:
        raise CalcError("Pitch diameter must be positive.")
    Ft = 2 * Td / D
    v = omega * D / 2
    values.update(Ft=Ft, v=v)
    steps.append(step("Tangential force", r"F_t = \frac{2\,T_d}{D}", Ft, "force"))
    steps.append(step("Pitch-line velocity", r"v = \omega \frac{D}{2}", v, "velocity"))
    kn = lambda f: f"{fmt(f / 1000, 3)} kN"
    diagram.update(Ft=kn(Ft), D=f"{fmt(from_canonical(D, 'length'), 3)}")

    if el in ("spur", "helical"):
        an = x["alpha"]
        beta = x["beta"] if el == "helical" else 0.0
        Fr = Ft * math.tan(an) / math.cos(beta)
        Fa = Ft * math.tan(beta)
        Fs = math.hypot(Ft, Fr)
        values.update(Fr=Fr, Fs=Fs)
        if el == "helical":
            values.update(Fa=Fa, Ma=Fa * D / 2)
        if el == "helical":
            steps += [step("Radial force", r"F_r = F_t \frac{\tan\alpha_n}{\cos\beta}", Fr, "force"),
                      step("Axial force", r"F_a = F_t \tan\beta", Fa, "force"),
                      step("Bending moment from Fa", r"M_a = F_a \frac{D}{2}", Fa * D / 2, "torque")]
        else:
            steps.append(step("Radial (separating) force", r"F_r = F_t \tan\alpha", Fr, "force"))
        steps.append(step("Resultant radial load on the shaft", r"F_s = \sqrt{F_t^2 + F_r^2}", Fs, "force"))
        diagram.update(Fr=kn(Fr), Fa=kn(Fa) if Fa else None, Fs=kn(Fs))
        notes.append("Forces act at the mesh point; their directions depend on which side the mating "
                     "gear sits and on the direction of rotation.")
    elif el in ("v_belt", "flat_belt"):
        theta = x["theta"]
        mu = x["mu"] or BELT_MU[el]
        e = math.exp(mu * theta)
        F2 = Ft / (e - 1)
        F1 = F2 + Ft
        Fs = math.sqrt(F1 ** 2 + F2 ** 2 - 2 * F1 * F2 * math.cos(theta))
        values.update(F1=F1, F2=F2, Fs=Fs)
        steps += [step("Tension ratio at slip", r"\frac{F_1}{F_2} = e^{\mu\theta}", e),
                  step("Slack-side tension", r"F_2 = \frac{F_t}{e^{\mu\theta} - 1}", F2, "force"),
                  step("Tight-side tension", r"F_1 = F_2 + F_t", F1, "force"),
                  step("Shaft load", r"F_s = \sqrt{F_1^2 + F_2^2 - 2F_1F_2\cos\theta}", Fs, "force")]
        diagram.update(F1=kn(F1), F2=kn(F2), Fs=kn(Fs), theta=round(math.degrees(theta)))
        notes.append(f"Tensions are the minimum that just transmit the load without slip (μ = {fmt(mu, 2)}). "
                     "Installed belts usually run 1.3–1.5× tighter, which raises the shaft load.")
    elif el == "timing_belt":
        Fs = TIMING_FACTOR * Ft
        values.update(Fs=Fs)
        steps.append(step("Shaft load (slack side at installation tension)", r"F_s \approx 1.2\,F_t", Fs, "force"))
        diagram.update(Fs=kn(Fs))
        notes.append("Timing belts need little pretension; the shaft load is about 1.1–1.3 × Ft. "
                     "Use the belt maker's installation tension when known.")
    else:  # chain
        Fs = Ft
        values.update(Fs=Fs)
        steps.append(step("Shaft load (slack strand carries no load)", r"F_s \approx F_t", Fs, "force"))
        diagram.update(Fs=kn(Fs))
        notes.append("Chain shaft load ≈ chain pull. Centrifugal tension and sag are neglected (fine "
                     "below about 10 m/s).")
    return {"values": values, "steps": steps, "checks": [], "notes": notes, "diagram": diagram}


DRIVE_LOADS = Calculator(
    id="drive_loads",
    governing=["P", "T", "n", "element", "D"],
    title="Drive loads: torque, chain, belt and gear forces",
    category="Shafts",
    summary="Torque from power and speed, and the force a sprocket, pulley or gear puts on its shaft "
            "(tangential, radial, axial and resultant).",
    description=(
        "Converts power and speed to torque and resolves the load the drive element applies to "
        "its shaft: chain pull, belt tight and slack side tensions (Euler–Eytelwein), timing belt "
        "shaft load, spur and helical gear tangential, radial and axial forces. The resultant "
        "shaft load feeds the beam (reactions), shaft fatigue and bearing calculators."
    ),
    params=[
        Param("input", "Load given as", kind="select", default="power",
              options=[{"value": "power", "label": "Power and speed"},
                       {"value": "torque", "label": "Torque and speed"}], group="Drive"),
        Param("P", "Power P", dim="power", default=5.5, unit="kW", min=0, group="Drive",
              show_if={"input": ["power"]}),
        Param("T", "Torque T", dim="torque", default=100, unit="N*m", min=0, group="Drive",
              show_if={"input": ["torque"]}),
        Param("n", "Speed n", dim="speed", default=90, unit="rpm", min=0, group="Drive"),
        Param("KA", "Application factor KA", default=1.0, min=1, group="Drive",
              help="1.0 uniform (electric motor, steady load), 1.25 light shock, 1.5 moderate, 1.75+ heavy."),
        Param("element", "Drive element on this shaft", kind="select", default="chain", options=ELEMENTS,
              group="Element"),
        Param("D", "Pitch diameter D", dim="length", default=200, unit="mm", min=0, group="Element",
              show_if={"element": [e["value"] for e in ELEMENTS if e["value"] != "coupling"]},
              help="Sprocket or gear pitch diameter, pulley pitch (datum) diameter."),
        Param("theta", "Wrap angle θ", dim="angle", default=180, unit="deg", min=0, max=360, group="Element",
              show_if={"element": ["v_belt", "flat_belt"]}),
        Param("mu", "Effective friction μ (0 = typical)", default=0, min=0, group="Element", advanced=True,
              show_if={"element": ["v_belt", "flat_belt"]},
              help="Typical: 0.5 for V-belts (groove wedging), 0.3 for flat belts."),
        Param("alpha", "Pressure angle αn", dim="angle", default=20, unit="deg", min=0, max=45, group="Element",
              show_if={"element": ["spur", "helical"]}),
        Param("beta", "Helix angle β", dim="angle", default=15, unit="deg", min=0, max=45, group="Element",
              show_if={"element": ["helical"]}),
    ],
    outputs=[
        Output("T", "Torque T", "torque", primary=True),
        Output("Fs", "Resultant radial load on shaft", "force", unit="kN", primary=True),
        Output("Ft", "Tangential force Ft", "force", unit="kN", primary=True),
        Output("Fr", "Radial (separating) force Fr", "force", unit="kN"),
        Output("Fa", "Axial force Fa", "force", unit="kN"),
        Output("Ma", "Bending moment from Fa", "torque"),
        Output("F1", "Tight-side tension F1", "force", unit="kN"),
        Output("F2", "Slack-side tension F2", "force", unit="kN"),
        Output("P", "Power P", "power", unit="kW"),
        Output("Td", "Design torque KA·T", "torque"),
        Output("v", "Pitch-line velocity", "velocity"),
    ],
    compute=_compute_drive,
    diagram="drive_loads",
    formulas=[r"T = \frac{P}{\omega}", r"F_t = \frac{2 K_A T}{D}", r"F_r = F_t \frac{\tan\alpha_n}{\cos\beta}",
              r"F_a = F_t \tan\beta", r"\frac{F_1}{F_2} = e^{\mu\theta}"],
    references=["Shigley's Mechanical Engineering Design, 10th ed., §13-14 (spur gear forces), "
                "§13-16 (helical gear forces), §17-2 and §17-3 (flat and V-belts), §17-5 (roller chain)"],
    keywords=["power", "torque", "rpm", "kw", "chain pull", "sprocket", "pulley", "belt tension", "v-belt",
              "timing belt", "gear forces", "tangential force", "radial force", "axial force", "drive",
              "conveyor", "motor"],
    presets=[
        {"label": "Conveyor: 5.5 kW, 90 rpm, sprocket Ø200", "values": {}},
        {"label": "V-belt: 7.5 kW, 1450 rpm, pulley Ø125", "values": {
            "P": {"value": 7.5, "unit": "kW"}, "n": {"value": 1450, "unit": "rpm"}, "element": "v_belt",
            "D": {"value": 125, "unit": "mm"}, "theta": {"value": 165, "unit": "deg"}, "KA": 1.2}},
        {"label": "Helical pinion: 15 kW, 1450 rpm, Ø60", "values": {
            "P": {"value": 15, "unit": "kW"}, "n": {"value": 1450, "unit": "rpm"}, "element": "helical",
            "D": {"value": 60, "unit": "mm"}}},
    ],
)

CALCULATORS = [DRIVE_LOADS]
