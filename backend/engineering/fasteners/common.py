"""Shared parameter builders and helpers for fastener calculators."""
import math
from typing import Any, Dict, List

from ..core import CalcError, Param
from . import data

CATEGORY = "Fasteners"

REFS_VDI = "VDI 2230-1:2015 Systematic calculation of highly stressed bolted joints"
REFS_898 = "ISO 898-1:2013 Mechanical properties of fasteners (steel)"
REFS_261 = "ISO 261 / ISO 724 ISO general-purpose metric screw threads"
REFS_SHIG = "Shigley's Mechanical Engineering Design, 10th ed., ch. 8"
REFS_EC3 = "EN 1993-1-8:2005 Design of joints (Eurocode 3)"


def mm(x_m: float) -> float:
    return x_m * 1000.0


def mpa(x_pa: float) -> float:
    return x_pa / 1e6


def thread_param(default: str = "M10", group: str = "Bolt", coarse_only: bool = False) -> Param:
    opts = data.THREAD_OPTIONS
    if coarse_only:
        opts = [o for o in opts if o["value"] in data.COARSE_PITCH]
    return Param("thread", "Thread", kind="select", default=default, options=opts, group=group)


def class_param(default: str = "8.8", group: str = "Bolt", steel_only: bool = False) -> Param:
    opts = data.CLASS_OPTIONS
    if steel_only:
        opts = [o for o in opts if not data.PROPERTY_CLASSES[o["value"]].get("stainless")]
    return Param("cls", "Property class", kind="select", default=default, options=opts, group=group)


def head_param(default: str = "shcs", group: str = "Bolt") -> Param:
    return Param("head", "Head type", kind="select", default=default, options=data.HEAD_TYPES,
                 group=group)


def friction_params(group: str = "Tightening") -> List[Param]:
    show = {"friction": ["custom"]}
    return [
        Param("friction", "Lubrication / surface", kind="select", default="oiled",
              options=data.FRICTION_OPTIONS, group=group),
        Param("muG", "Thread friction μG", default=0.12, min=0.04, max=0.4, group=group, show_if=show),
        Param("muK", "Head friction μK", default=0.12, min=0.04, max=0.4, group=group, show_if=show),
    ]


def method_param(default: str = "torque_estimated", group: str = "Tightening") -> Param:
    return Param("method", "Tightening method", kind="select", default=default,
                 options=data.TIGHTENING_OPTIONS, group=group,
                 help="Sets the tightening factor αA = FM,max / FM,min (VDI 2230 Table A8).")


def resolve_thread(x: Dict[str, Any]) -> Dict[str, float]:
    try:
        return data.thread(x["thread"])
    except KeyError:
        raise CalcError(f"Unknown thread '{x['thread']}'.")


def resolve_strength(cls: str, d: float) -> Dict[str, Any]:
    try:
        return data.strength(cls, d)
    except ValueError as e:
        raise CalcError(str(e))


def resolve_friction(x: Dict[str, Any]) -> Dict[str, float]:
    f = data.FRICTION[x["friction"]]
    if x["friction"] == "custom":
        muG, muK = x.get("muG"), x.get("muK")
        if not muG or not muK or muG <= 0 or muK <= 0:
            raise CalcError("Custom friction needs positive μG and μK.")
        return {"muG": muG, "muK": muK, "label": "custom"}
    return {"muG": f["muG"], "muK": f["muK"], "label": f["label"]}


def head_geometry(head_type: str, size: str, hole: str = "medium") -> Dict[str, float]:
    """dW (head bearing dia), dh (hole), DKm (mean friction dia) in mm."""
    if data.head(head_type, size) is None:
        raise CalcError(f"{data.HEAD_STD[head_type]} is not listed for {size}. "
                        "Choose another head type or size.")
    dW = data.bearing_diameter(head_type, size)
    dh = data.CLEARANCE[size][hole]
    if dW <= dh:
        raise CalcError("Head bearing diameter is not larger than the hole.")
    return {"dW": dW, "dh": dh, "DKm": (dW + dh) / 2}


def int_param(x: Dict[str, Any], name: str, label: str, lo: int = 1, hi: int = 200) -> int:
    v = x[name]
    n = int(round(v))
    if abs(v - n) > 1e-9 or n < lo or n > hi:
        raise CalcError(f"{label} must be a whole number between {lo} and {hi}.")
    return n


def kN(f_newton: float) -> str:
    from ..core import fmt
    return f"{fmt(f_newton / 1000.0, 3)} kN"


def Nm(t_nm: float) -> str:
    from ..core import fmt
    return f"{fmt(t_nm, 3)} N·m"


def MPa(s_mpa: float) -> str:
    from ..core import fmt
    return f"{fmt(s_mpa, 3)} MPa"


def torsion_section_modulus(ds: float) -> float:
    return math.pi * ds ** 3 / 16
