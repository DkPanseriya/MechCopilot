"""
Calculator framework.

Every engineering calculator is a typed `Calculator` definition:
  params   -> inputs with a physical dimension and unit choices
  outputs  -> results with a display unit
  compute  -> pure function over CANONICAL-unit floats (see CANON below)

`run_calculator` does the unit plumbing: it converts user inputs to canonical
units, calls compute, then converts outputs, plot series and worked steps back
to display units. Compute functions never see units, never format numbers.

Canonical units (what compute() receives and must return):
    length m | force N | stress Pa | torque N*m | speed rpm | angle rad
    temperature degC | temperature_delta K | mass kg | area m^2
    inertia m^4 | section_modulus m^3 | time s | duration_h h
    velocity m/s | acceleration m/s^2 | stiffness N/m | line_load N/m
    frequency Hz | density kg/m^3 | power W | energy J | per_temp 1/K
    kin_viscosity mm^2/s | dimensionless (plain float)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import pint

ureg = pint.UnitRegistry()
ureg.formatter.default_format = "~P"


# --------------------------------------------------------------------------
# Units
# --------------------------------------------------------------------------

CANON: Dict[str, str] = {
    "length": "m",
    "force": "N",
    "stress": "Pa",
    "torque": "N*m",
    "speed": "rpm",
    "angle": "rad",
    "temperature": "degC",
    "temperature_delta": "kelvin",
    "mass": "kg",
    "area": "m**2",
    "inertia": "m**4",
    "section_modulus": "m**3",
    "time": "s",
    "duration_h": "hour",
    "velocity": "m/s",
    "acceleration": "m/s**2",
    "stiffness": "N/m",
    "line_load": "N/m",
    "frequency": "Hz",
    "density": "kg/m**3",
    "power": "W",
    "energy": "J",
    "per_temp": "1/kelvin",
    "kin_viscosity": "mm**2/s",
    "mass_per_length": "kg/m",
    "dimensionless": "",
}

# (pint unit string, display label). First entry is the default input unit.
UNIT_CHOICES: Dict[str, List[Dict[str, str]]] = {
    "length": [{"value": "mm", "label": "mm"}, {"value": "m", "label": "m"},
               {"value": "cm", "label": "cm"}, {"value": "um", "label": "µm"},
               {"value": "inch", "label": "in"}, {"value": "ft", "label": "ft"}],
    "force": [{"value": "N", "label": "N"}, {"value": "kN", "label": "kN"},
              {"value": "lbf", "label": "lbf"}, {"value": "kgf", "label": "kgf"}],
    "stress": [{"value": "MPa", "label": "MPa"}, {"value": "GPa", "label": "GPa"},
               {"value": "kPa", "label": "kPa"}, {"value": "Pa", "label": "Pa"},
               {"value": "bar", "label": "bar"}, {"value": "psi", "label": "psi"},
               {"value": "ksi", "label": "ksi"}],
    "torque": [{"value": "N*m", "label": "N·m"}, {"value": "N*mm", "label": "N·mm"},
               {"value": "kN*m", "label": "kN·m"}, {"value": "lbf*ft", "label": "lbf·ft"},
               {"value": "lbf*inch", "label": "lbf·in"}],
    "speed": [{"value": "rpm", "label": "rpm"}, {"value": "rad/s", "label": "rad/s"}],
    "angle": [{"value": "deg", "label": "°"}, {"value": "rad", "label": "rad"}],
    "temperature": [{"value": "degC", "label": "°C"}, {"value": "degF", "label": "°F"},
                    {"value": "kelvin", "label": "K"}],
    "temperature_delta": [{"value": "kelvin", "label": "K"}, {"value": "delta_degC", "label": "Δ°C"},
                          {"value": "delta_degF", "label": "Δ°F"}],
    "mass": [{"value": "kg", "label": "kg"}, {"value": "g", "label": "g"},
             {"value": "lb", "label": "lb"}, {"value": "t", "label": "t"}],
    "area": [{"value": "mm**2", "label": "mm²"}, {"value": "cm**2", "label": "cm²"},
             {"value": "m**2", "label": "m²"}, {"value": "inch**2", "label": "in²"}],
    "inertia": [{"value": "mm**4", "label": "mm⁴"}, {"value": "cm**4", "label": "cm⁴"},
                {"value": "m**4", "label": "m⁴"}, {"value": "inch**4", "label": "in⁴"}],
    "section_modulus": [{"value": "mm**3", "label": "mm³"}, {"value": "cm**3", "label": "cm³"},
                        {"value": "m**3", "label": "m³"}, {"value": "inch**3", "label": "in³"}],
    "time": [{"value": "s", "label": "s"}, {"value": "ms", "label": "ms"},
             {"value": "min", "label": "min"}, {"value": "hour", "label": "h"}],
    "duration_h": [{"value": "hour", "label": "h"}, {"value": "day", "label": "days"},
                   {"value": "year", "label": "years"}],
    "velocity": [{"value": "m/s", "label": "m/s"}, {"value": "mm/s", "label": "mm/s"},
                 {"value": "km/hour", "label": "km/h"}, {"value": "ft/s", "label": "ft/s"}],
    "acceleration": [{"value": "m/s**2", "label": "m/s²"}, {"value": "g0", "label": "g"}],
    "stiffness": [{"value": "N/mm", "label": "N/mm"}, {"value": "kN/mm", "label": "kN/mm"},
                  {"value": "N/m", "label": "N/m"}, {"value": "lbf/inch", "label": "lbf/in"}],
    "line_load": [{"value": "N/mm", "label": "N/mm"}, {"value": "kN/m", "label": "kN/m"},
                  {"value": "N/m", "label": "N/m"}, {"value": "lbf/inch", "label": "lbf/in"}],
    "frequency": [{"value": "Hz", "label": "Hz"}, {"value": "rpm", "label": "rpm"}],
    "density": [{"value": "kg/m**3", "label": "kg/m³"}, {"value": "g/cm**3", "label": "g/cm³"}],
    "power": [{"value": "W", "label": "W"}, {"value": "kW", "label": "kW"},
              {"value": "hp", "label": "hp"}],
    "energy": [{"value": "J", "label": "J"}, {"value": "kJ", "label": "kJ"}],
    "per_temp": [{"value": "1/kelvin", "label": "1/K"}],
    "kin_viscosity": [{"value": "mm**2/s", "label": "mm²/s (cSt)"}],
    "mass_per_length": [{"value": "kg/m", "label": "kg/m"}, {"value": "lb/ft", "label": "lb/ft"}],
    "dimensionless": [{"value": "", "label": "–"}],
}

# Default display unit per dimension for outputs/plots (overridable per Output).
DISPLAY: Dict[str, str] = {
    "length": "mm", "force": "N", "stress": "MPa", "torque": "N*m", "speed": "rpm",
    "angle": "deg", "temperature": "degC", "temperature_delta": "kelvin", "mass": "kg",
    "area": "mm**2", "inertia": "mm**4", "section_modulus": "mm**3", "time": "s",
    "duration_h": "hour", "velocity": "m/s", "acceleration": "m/s**2",
    "stiffness": "N/mm", "line_load": "N/mm", "frequency": "Hz", "density": "kg/m**3",
    "power": "W", "energy": "J", "per_temp": "1/kelvin", "kin_viscosity": "mm**2/s",
    "mass_per_length": "kg/m", "dimensionless": "",
}

_LABELS = {c["value"]: c["label"] for choices in UNIT_CHOICES.values() for c in choices}


def unit_label(unit: str) -> str:
    if not unit:
        return ""
    return _LABELS.get(unit, unit)


def to_canonical(value: Any, unit: Optional[str], dim: str) -> float:
    """Convert a user value in `unit` to the canonical unit for `dim`."""
    v = float(value)
    if dim == "dimensionless":
        return v
    src = unit or UNIT_CHOICES[dim][0]["value"]
    return ureg.Quantity(v, src).to(CANON[dim]).magnitude


def from_canonical(value: float, dim: str, unit: Optional[str] = None) -> float:
    if dim == "dimensionless":
        return float(value)
    target = unit or DISPLAY[dim]
    return ureg.Quantity(float(value), CANON[dim]).to(target).magnitude


def fmt(value: float, sig: int = 4) -> str:
    """Engineering-friendly number formatting."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    if isinstance(value, float) and math.isinf(value):
        return "∞"
    if value == 0:
        return "0"
    a = abs(value)
    if a >= 1e6 or a < 1e-3:
        return f"{value:.{max(sig - 1, 1)}e}"
    digits = max(sig - int(math.floor(math.log10(a))) - 1, 0)
    s = f"{value:.{digits}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# --------------------------------------------------------------------------
# Definitions
# --------------------------------------------------------------------------

class CalcError(ValueError):
    """Raised by compute() for physically invalid input combinations."""


@dataclass
class Param:
    name: str
    label: str
    kind: str = "number"                 # number | select | bool | text
    dim: str = "dimensionless"           # for numbers
    default: Any = None
    unit: Optional[str] = None           # default input unit (pint string)
    options: Optional[List[Dict[str, Any]]] = None  # select: [{value, label}]
    min: Optional[float] = None          # in DEFAULT input unit
    max: Optional[float] = None
    help: Optional[str] = None
    group: Optional[str] = None
    advanced: bool = False
    show_if: Optional[Dict[str, List[Any]]] = None  # {param: [values]} -> visible

    def to_dict(self) -> Dict[str, Any]:
        unit = self.unit if self.unit is not None else (
            UNIT_CHOICES[self.dim][0]["value"] if self.kind == "number" else None)
        return {
            "name": self.name, "label": self.label, "kind": self.kind, "dim": self.dim,
            "default": self.default, "unit": unit, "options": self.options,
            "min": self.min, "max": self.max, "help": self.help, "group": self.group,
            "advanced": self.advanced, "show_if": self.show_if,
        }


@dataclass
class Output:
    name: str
    label: str
    dim: str = "dimensionless"
    unit: Optional[str] = None           # display unit (defaults to DISPLAY[dim])
    sig: int = 4
    primary: bool = False
    help: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        u = self.unit if self.unit is not None else DISPLAY[self.dim]
        return {"name": self.name, "label": self.label, "dim": self.dim, "unit": u,
                "unit_label": unit_label(u), "primary": self.primary, "help": self.help}


@dataclass
class Calculator:
    id: str
    title: str
    category: str
    summary: str
    params: List[Param]
    outputs: List[Output]
    compute: Callable[[Dict[str, Any]], Dict[str, Any]]
    description: str = ""
    diagram: Optional[str] = None
    formulas: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    presets: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "category": self.category,
            "summary": self.summary, "description": self.description,
            "diagram": self.diagram, "formulas": self.formulas,
            "references": self.references, "keywords": self.keywords,
            "presets": self.presets,
            "params": [p.to_dict() for p in self.params],
            "outputs": [o.to_dict() for o in self.outputs],
        }

    def llm_summary(self) -> Dict[str, Any]:
        """Compact form for model prompts."""
        params = []
        for p in self.params:
            d = {"name": p.name, "label": p.label}
            if p.kind == "number":
                d["unit"] = p.to_dict()["unit"]
                d["default"] = p.default
            elif p.kind == "select":
                d["options"] = [o["value"] for o in (p.options or [])][:30]
                d["default"] = p.default
            else:
                d["kind"] = p.kind
                d["default"] = p.default
            params.append(d)
        return {"id": self.id, "title": self.title, "category": self.category,
                "summary": self.summary, "params": params}


# --------------------------------------------------------------------------
# Compute result helpers (used inside compute functions)
# --------------------------------------------------------------------------

def check(label: str, ok: bool, message: str, *, warn: bool = False,
          value: Optional[float] = None, limit: Optional[float] = None) -> Dict[str, Any]:
    """A pass/warn/fail verdict. `warn=True` downgrades a failure to a warning."""
    status = "ok" if ok else ("warn" if warn else "fail")
    return {"label": label, "status": status, "message": message,
            "value": value, "limit": limit}


def step(label: str, latex: str, value: Optional[float] = None, dim: str = "dimensionless",
         unit: Optional[str] = None, sig: int = 4) -> Dict[str, Any]:
    """One line of the worked solution. `value` is canonical; converted for display."""
    return {"label": label, "latex": latex, "value": value, "dim": dim, "unit": unit, "sig": sig}


def series(id: str, title: str, x: List[float], y: List[float], *, x_label: str, y_label: str,
           x_dim: str = "dimensionless", y_dim: str = "dimensionless",
           x_unit: Optional[str] = None, y_unit: Optional[str] = None,
           kind: str = "line", group: Optional[str] = None,
           markers: Optional[List[Dict[str, Any]]] = None,
           ref_lines: Optional[List[Dict[str, Any]]] = None,
           x_scale: str = "linear", y_scale: str = "linear") -> Dict[str, Any]:
    """A plot series in canonical units.

    kind:      line | area (filled to y=0, for SFD/BMD) | step | scatter (points only)
    markers:   [{"x": canonical, "label": str}] vertical annotations
    ref_lines: [{"y": canonical, "label": str}] horizontal limits (e.g. allowable)
    group:     series sharing a group are drawn on the same axes (shared scales)
    x_scale / y_scale: "linear" | "log" (log axes require positive values)
    """
    return {"id": id, "title": title, "x": x, "y": y, "x_label": x_label, "y_label": y_label,
            "x_dim": x_dim, "y_dim": y_dim, "x_unit": x_unit, "y_unit": y_unit,
            "kind": kind, "group": group, "markers": markers or [], "ref_lines": ref_lines or [],
            "x_scale": x_scale, "y_scale": y_scale}


def table(title: str, columns: List[Dict[str, Any]], rows: List[Dict[str, Any]], *,
          highlight: Optional[Dict[str, Any]] = None, note: Optional[str] = None) -> Dict[str, Any]:
    """columns: [{"key", "label", "unit"?}] — values are display-ready (no conversion).
    A row may carry "_links": [{"label", "url"}] and "_status": ok|warn|fail."""
    return {"title": title, "columns": columns, "rows": rows,
            "highlight": highlight, "note": note}


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def _coerce_input(p: Param, raw: Any) -> Any:
    if p.kind == "number":
        if isinstance(raw, dict):
            val, unit = raw.get("value"), raw.get("unit")
        else:
            val, unit = raw, None
        if val is None or val == "":
            val = p.default
        unit = unit or p.to_dict()["unit"]
        try:
            return to_canonical(val, unit, p.dim)
        except (TypeError, ValueError) as e:
            raise CalcError(f"'{p.label}': invalid number '{val}'") from e
        except pint.errors.PintError as e:
            raise CalcError(f"'{p.label}': unit '{unit}' is not valid for {p.dim}") from e
    if p.kind == "select":
        val = raw.get("value") if isinstance(raw, dict) else raw
        if val is None:
            val = p.default
        allowed = [o["value"] for o in (p.options or [])]
        if allowed and val not in allowed:
            # tolerate type mismatch (e.g. "8.8" vs 8.8)
            match = next((a for a in allowed if str(a) == str(val)), None)
            if match is None:
                raise CalcError(f"'{p.label}': '{val}' is not one of {allowed[:12]}")
            val = match
        return val
    if p.kind == "bool":
        val = raw.get("value") if isinstance(raw, dict) else raw
        if val is None:
            val = p.default
        return val in (True, "true", "True", 1, "1", "yes", "on")
    val = raw.get("value") if isinstance(raw, dict) else raw
    return p.default if val is None else str(val)


def _linear_converter(dim: str, unit: str) -> Callable[[float], float]:
    """All supported conversions are affine; compute factor/offset once per series
    instead of building a Pint Quantity per point."""
    if dim == "dimensionless":
        return lambda v: float(v)
    o = from_canonical(0.0, dim, unit)
    f = from_canonical(1.0, dim, unit) - o
    return lambda v: v * f + o


def _finite(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _clean(obj: Any) -> Any:
    """Replace inf/NaN anywhere in a structure with None (JSON cannot encode them)."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    return obj


def _convert_series(s: Dict[str, Any]) -> Dict[str, Any]:
    xu = s.get("x_unit") or DISPLAY[s["x_dim"]]
    yu = s.get("y_unit") or DISPLAY[s["y_dim"]]
    cx = _linear_converter(s["x_dim"], xu)
    cy = _linear_converter(s["y_dim"], yu)
    pts = [(cx(x), cy(y)) for x, y in zip(s["x"], s["y"]) if _finite(x) and _finite(y)]
    out = dict(s)
    out["x"] = [p[0] for p in pts]
    out["y"] = [p[1] for p in pts]
    out["x_unit"], out["y_unit"] = unit_label(xu), unit_label(yu)
    out["markers"] = [{**m, "x": cx(m["x"])} for m in s.get("markers", []) if _finite(m.get("x"))]
    out["ref_lines"] = [{**r, "y": cy(r["y"])} for r in s.get("ref_lines", []) if _finite(r.get("y"))]
    return out


def run_calculator(calc: Calculator, raw_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Validate + convert inputs, compute, and format everything for display."""
    raw_inputs = raw_inputs or {}
    inputs = {p.name: _coerce_input(p, raw_inputs.get(p.name)) for p in calc.params}

    res = calc.compute(inputs) or {}
    values = res.get("values", {})

    outputs = []
    for o in calc.outputs:
        if o.name not in values or values[o.name] is None:
            continue
        si = values[o.name]
        if isinstance(si, str):
            outputs.append({**o.to_dict(), "value": None, "display": si, "si_value": None})
            continue
        if not _finite(si):  # e.g. safety factor with zero stress
            label = "∞" if isinstance(si, float) and math.isinf(si) else "–"
            outputs.append({**o.to_dict(), "value": None, "display": label, "si_value": None})
            continue
        disp = from_canonical(si, o.dim, o.unit)
        outputs.append({**o.to_dict(), "value": disp, "display": fmt(disp, o.sig), "si_value": si})

    steps = []
    for s in res.get("steps", []):
        entry = {"label": s["label"], "latex": s["latex"]}
        v = s.get("value")
        if v is not None:
            u = s.get("unit") or DISPLAY[s["dim"]]
            if _finite(v):
                entry.update({"display": fmt(from_canonical(v, s["dim"], u), s.get("sig", 4)),
                              "unit_label": unit_label(u)})
            else:
                entry.update({"display": "∞" if isinstance(v, float) and math.isinf(v) else "–",
                              "unit_label": ""})
        steps.append(entry)

    return _clean({
        "id": calc.id,
        "outputs": outputs,
        "checks": res.get("checks", []),
        "steps": steps,
        "series": [_convert_series(s) for s in res.get("series", [])],
        "tables": res.get("tables", []),
        "diagram": {"id": calc.diagram, "params": res.get("diagram", {})} if calc.diagram else None,
        "notes": res.get("notes", []),
        "links": res.get("links", []),
        "verdict": _overall(res.get("checks", [])),
    })


def _overall(checks: List[Dict[str, Any]]) -> str:
    statuses = {c["status"] for c in checks}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "ok" if checks else "none"


def linspace(a: float, b: float, n: int) -> List[float]:
    if n < 2:
        return [a]
    return [a + (b - a) * i / (n - 1) for i in range(n)]
