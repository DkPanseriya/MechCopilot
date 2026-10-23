"""Shared material selection for calculators (backed by data/materials.json)."""
import json
import os
from typing import Any, Dict, List

from .core import CalcError, Param

_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "materials.json")

with open(_PATH, "r", encoding="utf-8") as f:
    MATERIALS: List[Dict[str, Any]] = json.load(f)

BY_ID: Dict[str, Dict[str, Any]] = {m["id"]: m for m in MATERIALS}


def material_options(include_custom: bool = True, category: str = None) -> List[Dict[str, str]]:
    opts = [{"value": m["id"], "label": m["name"]} for m in MATERIALS
            if category is None or m["category"] == category]
    if include_custom:
        opts.append({"value": "custom", "label": "Custom…"})
    return opts


def material_params(name: str = "material", default: str = "s355j2", label: str = "Material",
                    group: str = "Material", need_E: bool = True) -> List[Param]:
    """A material select plus custom-property fields shown only for 'Custom…'."""
    show = {name: ["custom"]}
    params = [
        Param(name, label, kind="select", default=default, options=material_options(), group=group),
        Param(f"{name}_Sy", "Yield strength Sy", dim="stress", default=355, unit="MPa",
              group=group, show_if=show),
        Param(f"{name}_Sut", "Ultimate strength Sut", dim="stress", default=510, unit="MPa",
              group=group, show_if=show),
    ]
    if need_E:
        params.append(Param(f"{name}_E", "Young's modulus E", dim="stress", default=210, unit="GPa",
                            group=group, show_if=show))
    return params


def resolve_material(inputs: Dict[str, Any], name: str = "material") -> Dict[str, Any]:
    """Return material properties in canonical SI units."""
    mid = inputs.get(name)
    if mid == "custom":
        Sy, Sut = inputs.get(f"{name}_Sy"), inputs.get(f"{name}_Sut")
        if not Sy or not Sut:
            raise CalcError("Custom material needs yield and ultimate strength.")
        return {"id": "custom", "name": "Custom material", "Sy": Sy, "Sut": Sut,
                "E": inputs.get(f"{name}_E") or 210e9, "nu": 0.3, "rho": 7850.0,
                "alpha": 12e-6, "brittle": False}
    m = BY_ID.get(mid)
    if m is None:
        raise CalcError(f"Unknown material '{mid}'.")
    return {"id": m["id"], "name": m["name"], "Sy": m["yield_strength"],
            "Sut": m["ultimate_strength"], "E": m["elastic_modulus"],
            "nu": m.get("poisson", 0.3), "rho": m["density"],
            "alpha": m.get("thermal_expansion", 12e-6),
            "brittle": m.get("sub_category") == "Cast Iron" and "GJL" in m["name"]}
