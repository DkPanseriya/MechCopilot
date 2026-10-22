"""
Calculation entry points — now backed entirely by the physics kernel.

Previously this module held its own hand-written physics (a second, parallel
engine) plus a fuzzy string-match dispatcher. That duplicated — and sometimes
contradicted — physics_kernel.py. It is now a thin adapter layer: all compute
goes through RELATIONS in physics_kernel. One engine, unit-correct.
"""
from typing import Dict, Any, Optional
from physics_kernel import RELATIONS


def calculate_relation(
    relation: str,
    solve_for: str,
    inputs: Dict[str, Any],
    output_unit: Optional[str] = None,
) -> Dict[str, Any]:
    """Primary entry point: solve a named kernel relation for `solve_for`.

    `inputs` maps relation variable names to values. A value may be a number
    (already in SI), a string like "10 mm", or {"value": 10, "unit": "mm"}.
    """
    if relation not in RELATIONS:
        return {"error": f"Unknown relation '{relation}'. See /api/workflow/manifest."}
    if solve_for not in RELATIONS[relation].variables:
        return {"error": f"'{solve_for}' is not a variable of '{relation}'."}
    try:
        res = RELATIONS[relation].solve(inputs, solve_for, output_unit)
        return {
            "value": f"{res['value']:.4f}" if isinstance(res["value"], float) else res["value"],
            "unit": res["unit"],
            "raw": res["value"],
            "si_value": res["si_value"],
            "si_unit": res["si_unit"],
        }
    except Exception as e:
        return {"error": str(e)}


def _q(value: Any, unit: str) -> Dict[str, Any]:
    return {"value": float(value), "unit": unit}


# --- Legacy friendly-input adapters (kept so older callers/tests keep working).
# These translate human-facing inputs (e.g. diameter) into kernel variables and
# delegate the actual math to the kernel.

def calc_axial_stress(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Axial stress from force + diameter (derives area via the kernel)."""
    f = _q(inputs.get("force", 0), inputs.get("force_unit", "N"))
    d = _q(inputs.get("diameter", 0), inputs.get("diameter_unit", "mm"))
    if d["value"] == 0:
        return {"error": "Diameter cannot be zero."}
    area = RELATIONS["circle_area"].solve({"d": d}, "A")["si_value"]
    return calculate_relation(
        "axial_stress", "sigma",
        {"F": f, "A": {"value": area, "unit": "m**2"}},
        "MPa",
    )


def calc_torsional_stress(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Max shear stress in a solid shaft from torque + diameter."""
    t = _q(inputs.get("torque", 0), inputs.get("torque_unit", "N*m"))
    d = _q(inputs.get("diameter", 0), inputs.get("diameter_unit", "mm"))
    if d["value"] == 0:
        return {"error": "Diameter cannot be zero."}
    return calculate_relation("torsional_stress_solid", "tau", {"T": t, "d": d}, "MPa")


def calc_thermal_expansion(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Free thermal expansion from length, delta-T and expansion coefficient."""
    length = _q(inputs.get("length", 0), inputs.get("length_unit", "m"))
    # Delta-T: a temperature difference, so treat the magnitude as kelvin.
    dt = {"value": float(inputs.get("delta_temperature", 0)), "unit": "kelvin"}
    alpha = {"value": float(inputs.get("thermal_expansion_coefficient", 0)), "unit": "1/kelvin"}
    return calculate_relation(
        "thermal_expansion", "dL",
        {"alpha": alpha, "L": length, "dT": dt},
        "mm",
    )


def calc_beam_deflection(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Cantilever tip deflection from force, length, modulus and diameter."""
    f = _q(inputs.get("force", 0), inputs.get("force_unit", "N"))
    l = _q(inputs.get("length", 0), inputs.get("length_unit", "m"))
    e = _q(inputs.get("elasticity", 200e9), inputs.get("elasticity_unit", "Pa"))
    d = _q(inputs.get("diameter", 0.01), inputs.get("diameter_unit", "m"))
    i = RELATIONS["I_solid_circle"].solve({"d": d}, "I")["si_value"]
    return calculate_relation(
        "cantilever_point_deflection", "delta",
        {"F": f, "L": l, "E": e, "I": {"value": i, "unit": "m**4"}},
        "mm",
    )


# --- Dispatcher (transitional) -------------------------------------------
# Maps legacy tool_name strings to the adapters above. New code should call
# calculate_relation() with an explicit kernel relation instead.
_LEGACY = {
    "axial_stress": calc_axial_stress,
    "torsional_stress": calc_torsional_stress,
    "thermal_expansion": calc_thermal_expansion,
    "beam_deflection": calc_beam_deflection,
}


def perform_calculation(tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy entry: resolve a tool_name to an adapter, else try it as a
    kernel relation name directly."""
    norm = tool_name.lower().replace(" ", "_").replace("-", "_")

    if "torsion" in norm:
        return calc_torsional_stress(inputs)
    if "stress" in norm and "torsion" not in norm:
        return calc_axial_stress(inputs)
    if "deflection" in norm:
        return calc_beam_deflection(inputs)
    if "expansion" in norm or "thermal" in norm:
        return calc_thermal_expansion(inputs)
    if norm in _LEGACY:
        return _LEGACY[norm](inputs)

    return {"error": f"Calculator logic for '{tool_name}' not implemented yet."}
