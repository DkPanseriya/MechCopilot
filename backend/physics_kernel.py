"""
Physics Kernel — the trusted, unit-aware formula library.

Design principles (see product/GENERATIVE_ENGINE_PLAN.md):
  - A bounded, well-defined set of strength-of-materials / mechanics relations.
  - Each relation is a symbolic equation + per-variable SI unit, so the kernel
    can solve for ANY variable and return a result with correct units.
  - All compute is server-side and deterministic. The LLM never authors code;
    it only references a relation by `name`.

The old kernel lost units on output (returned raw SI magnitude with a hardcoded
"SI_derived" label). This version attaches an SI unit to every variable, solves
numerically via SymPy, and returns a real Pint Quantity converted to the
caller's requested display unit.
"""

import sympy
from sympy import symbols, Eq, sympify, nsimplify
from typing import Dict, Any, List, Optional, Union
import pint

ureg = pint.UnitRegistry()

# Value a caller may pass for a known/target variable.
InputValue = Union[int, float, str, Dict[str, Any]]


class PhysicsRelation:
    """A single governing equation with dimensioned variables."""

    def __init__(
        self,
        name: str,
        equation_str: str,
        units: Dict[str, str],
        description: str,
        category: str = "general",
        formula_latex: Optional[str] = None,
    ):
        self.name = name
        self.description = description
        self.category = category
        self.formula_latex = formula_latex
        # SI unit string per variable ("" = dimensionless).
        self.units = units
        self.variables = list(units.keys())

        self.syms = {v: symbols(v, real=True) for v in self.variables}

        lhs_str, rhs_str = equation_str.split("=", 1)
        self.lhs = sympify(lhs_str, locals=self.syms)
        self.rhs = sympify(rhs_str, locals=self.syms)
        self.equation = Eq(self.lhs, self.rhs)
        self.equation_str = equation_str

    # -- input / output unit handling -------------------------------------

    def _to_si_magnitude(self, val: InputValue, si_unit: str) -> float:
        """Normalize a user-supplied value to the variable's SI magnitude.

        Accepts: bare number (assumed already in the variable's SI unit),
        a string like "10 mm", or {"value": 10, "unit": "mm"}.
        """
        if si_unit == "" or si_unit is None:
            if isinstance(val, dict):
                return float(val["value"])
            if isinstance(val, str):
                try:
                    return float(val)
                except ValueError:
                    return float(ureg(val).magnitude)
            return float(val)

        if isinstance(val, (int, float)):
            quantity = ureg.Quantity(float(val), si_unit)
        elif isinstance(val, str):
            quantity = ureg(val)
        elif isinstance(val, dict) and "value" in val and "unit" in val:
            quantity = ureg.Quantity(float(val["value"]), val["unit"])
        else:
            raise ValueError(f"Unsupported input value: {val!r}")

        return quantity.to(si_unit).magnitude

    @staticmethod
    def _pick_solution(solutions: List[Any]) -> float:
        """Pick a physically sensible real solution (prefer positive)."""
        reals: List[float] = []
        for s in solutions:
            try:
                c = complex(s)
            except (TypeError, ValueError):
                continue
            if abs(c.imag) < 1e-9:
                reals.append(c.real)
        if not reals:
            raise ValueError("No real solution found.")
        positives = [r for r in reals if r > 0]
        return positives[0] if positives else reals[0]

    # -- solve ------------------------------------------------------------

    def solve(
        self,
        knowns: Dict[str, InputValue],
        target: str,
        target_unit: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Solve for `target` given `knowns`. Returns a unit-bearing result."""
        if target not in self.variables:
            raise ValueError(f"Target '{target}' not in {self.variables}")

        subs = []
        for var, val in knowns.items():
            if var not in self.syms:
                continue
            if var == target:
                continue
            subs.append((self.syms[var], self._to_si_magnitude(val, self.units[var])))

        eq = self.equation.subs(subs)
        solutions = sympy.solve(eq, self.syms[target])
        if not solutions:
            raise ValueError("No solution found.")

        si_value = self._pick_solution(solutions)
        si_unit = self.units[target]

        if si_unit:
            quantity = ureg.Quantity(si_value, si_unit)
            if target_unit:
                quantity = quantity.to(target_unit)
            return {
                "value": quantity.magnitude,
                "unit": f"{quantity.units:~P}",
                "si_value": si_value,
                "si_unit": si_unit,
            }
        return {"value": si_value, "unit": "", "si_value": si_value, "si_unit": ""}


# ---------------------------------------------------------------------------
# Relation library
# ---------------------------------------------------------------------------
# SI unit conventions: length=meter, force=newton, stress/pressure=pascal,
# area=meter**2, second moment I=meter**4, section modulus Z=meter**3,
# torque/moment=newton*meter, angle=radian, dimensionless="".

_R = PhysicsRelation
RELATIONS: Dict[str, PhysicsRelation] = {}


def _add(rel: PhysicsRelation) -> None:
    RELATIONS[rel.name] = rel


# --- Stress ---------------------------------------------------------------
_add(_R("axial_stress", "sigma = F / A",
        {"sigma": "pascal", "F": "newton", "A": "meter**2"},
        "Normal (axial) stress = Force / Area", "stress",
        r"\sigma = \frac{F}{A}"))

_add(_R("direct_shear_stress", "tau = F / A",
        {"tau": "pascal", "F": "newton", "A": "meter**2"},
        "Direct (average) shear stress = Force / Area", "stress",
        r"\tau = \frac{F}{A}"))

_add(_R("bearing_stress", "sigma = F / (d * t)",
        {"sigma": "pascal", "F": "newton", "d": "meter", "t": "meter"},
        "Bearing/crushing stress on a projected contact area", "stress",
        r"\sigma = \frac{F}{d\,t}"))

_add(_R("bending_stress", "sigma = (M * y) / I",
        {"sigma": "pascal", "M": "newton*meter", "y": "meter", "I": "meter**4"},
        "Bending stress = Moment * dist_from_neutral_axis / second_moment_of_area",
        "stress", r"\sigma = \frac{M y}{I}"))

_add(_R("bending_stress_modulus", "sigma = M / Z",
        {"sigma": "pascal", "M": "newton*meter", "Z": "meter**3"},
        "Bending stress from section modulus Z", "stress",
        r"\sigma = \frac{M}{Z}"))

_add(_R("transverse_shear_stress", "tau = (V * Q) / (I * b)",
        {"tau": "pascal", "V": "newton", "Q": "meter**3", "I": "meter**4", "b": "meter"},
        "Transverse shear stress (shear-flow formula)", "stress",
        r"\tau = \frac{V Q}{I b}"))

_add(_R("torsional_stress_solid", "tau = (16 * T) / (pi * d**3)",
        {"tau": "pascal", "T": "newton*meter", "d": "meter"},
        "Max shear stress in a solid circular shaft", "stress",
        r"\tau = \frac{16 T}{\pi d^3}"))

_add(_R("torsional_stress_general", "tau = (T * r) / J",
        {"tau": "pascal", "T": "newton*meter", "r": "meter", "J": "meter**4"},
        "Torsional shear stress = Torque * radius / polar_moment", "stress",
        r"\tau = \frac{T r}{J}"))

_add(_R("hoop_stress", "sigma = (P * d) / (2 * t)",
        {"sigma": "pascal", "P": "pascal", "d": "meter", "t": "meter"},
        "Hoop (circumferential) stress, thin-walled pressure vessel", "stress",
        r"\sigma_\theta = \frac{P d}{2 t}"))

_add(_R("longitudinal_stress", "sigma = (P * d) / (4 * t)",
        {"sigma": "pascal", "P": "pascal", "d": "meter", "t": "meter"},
        "Longitudinal (axial) stress, thin-walled pressure vessel", "stress",
        r"\sigma_z = \frac{P d}{4 t}"))

_add(_R("thermal_stress", "sigma = E * alpha * dT",
        {"sigma": "pascal", "E": "pascal", "alpha": "1/kelvin", "dT": "kelvin"},
        "Thermal stress in a fully constrained member", "stress",
        r"\sigma = E \alpha \Delta T"))

# --- Section properties ---------------------------------------------------
_add(_R("circle_area", "A = pi * d**2 / 4",
        {"A": "meter**2", "d": "meter"},
        "Area of a circle from diameter", "section",
        r"A = \frac{\pi d^2}{4}"))

_add(_R("rectangle_area", "A = b * h",
        {"A": "meter**2", "b": "meter", "h": "meter"},
        "Area of a rectangle", "section", r"A = b h"))

_add(_R("I_rectangle", "I = (b * h**3) / 12",
        {"I": "meter**4", "b": "meter", "h": "meter"},
        "Second moment of area, rectangle about centroidal axis", "section",
        r"I = \frac{b h^3}{12}"))

_add(_R("I_solid_circle", "I = (pi * d**4) / 64",
        {"I": "meter**4", "d": "meter"},
        "Second moment of area, solid circle", "section",
        r"I = \frac{\pi d^4}{64}"))

_add(_R("I_hollow_circle", "I = (pi * (D**4 - d**4)) / 64",
        {"I": "meter**4", "D": "meter", "d": "meter"},
        "Second moment of area, hollow circle (D outer, d inner)", "section",
        r"I = \frac{\pi (D^4 - d^4)}{64}"))

_add(_R("J_solid_circle", "J = (pi * d**4) / 32",
        {"J": "meter**4", "d": "meter"},
        "Polar moment of area, solid circle", "section",
        r"J = \frac{\pi d^4}{32}"))

_add(_R("section_modulus", "Z = I / c",
        {"Z": "meter**3", "I": "meter**4", "c": "meter"},
        "Section modulus = I / extreme_fiber_distance", "section",
        r"Z = \frac{I}{c}"))

# --- Deflection / stiffness ----------------------------------------------
_add(_R("axial_deflection", "delta = (F * L) / (A * E)",
        {"delta": "meter", "F": "newton", "L": "meter", "A": "meter**2", "E": "pascal"},
        "Axial elongation of a bar", "deflection",
        r"\delta = \frac{F L}{A E}"))

_add(_R("cantilever_point_deflection", "delta = (F * L**3) / (3 * E * I)",
        {"delta": "meter", "F": "newton", "L": "meter", "E": "pascal", "I": "meter**4"},
        "Tip deflection, cantilever with end point load", "deflection",
        r"\delta = \frac{F L^3}{3 E I}"))

_add(_R("simply_supported_center_deflection", "delta = (F * L**3) / (48 * E * I)",
        {"delta": "meter", "F": "newton", "L": "meter", "E": "pascal", "I": "meter**4"},
        "Mid-span deflection, simply supported beam with central point load",
        "deflection", r"\delta = \frac{F L^3}{48 E I}"))

_add(_R("angle_of_twist", "theta = (T * L) / (G * J)",
        {"theta": "radian", "T": "newton*meter", "L": "meter", "G": "pascal", "J": "meter**4"},
        "Angle of twist of a shaft", "deflection",
        r"\theta = \frac{T L}{G J}"))

_add(_R("thermal_expansion", "dL = alpha * L * dT",
        {"dL": "meter", "alpha": "1/kelvin", "L": "meter", "dT": "kelvin"},
        "Free thermal expansion (change in length)", "deflection",
        r"\Delta L = \alpha L \Delta T"))

# --- Combined loading -----------------------------------------------------
_add(_R("von_mises_2d",
        "sv = sqrt(sx**2 - sx*sy + sy**2 + 3*txy**2)",
        {"sv": "pascal", "sx": "pascal", "sy": "pascal", "txy": "pascal"},
        "von Mises equivalent stress (plane stress)", "combined",
        r"\sigma' = \sqrt{\sigma_x^2 - \sigma_x\sigma_y + \sigma_y^2 + 3\tau_{xy}^2}"))

_add(_R("principal_stress_max",
        "s1 = (sx + sy)/2 + sqrt(((sx - sy)/2)**2 + txy**2)",
        {"s1": "pascal", "sx": "pascal", "sy": "pascal", "txy": "pascal"},
        "Maximum principal stress (plane stress)", "combined",
        r"\sigma_1 = \frac{\sigma_x+\sigma_y}{2} + \sqrt{\left(\frac{\sigma_x-\sigma_y}{2}\right)^2 + \tau_{xy}^2}"))

_add(_R("principal_stress_min",
        "s2 = (sx + sy)/2 - sqrt(((sx - sy)/2)**2 + txy**2)",
        {"s2": "pascal", "sx": "pascal", "sy": "pascal", "txy": "pascal"},
        "Minimum principal stress (plane stress)", "combined",
        r"\sigma_2 = \frac{\sigma_x+\sigma_y}{2} - \sqrt{\left(\frac{\sigma_x-\sigma_y}{2}\right)^2 + \tau_{xy}^2}"))

_add(_R("max_shear_stress_2d",
        "tmax = sqrt(((sx - sy)/2)**2 + txy**2)",
        {"tmax": "pascal", "sx": "pascal", "sy": "pascal", "txy": "pascal"},
        "Maximum in-plane shear stress", "combined",
        r"\tau_{max} = \sqrt{\left(\frac{\sigma_x-\sigma_y}{2}\right)^2 + \tau_{xy}^2}"))

_add(_R("shaft_equivalent_stress",
        "se = sqrt(sb**2 + 3*tt**2)",
        {"se": "pascal", "sb": "pascal", "tt": "pascal"},
        "Equivalent (von Mises) stress on a shaft under bending + torsion",
        "combined", r"\sigma' = \sqrt{\sigma_b^2 + 3\tau_t^2}"))

# --- Failure / safety -----------------------------------------------------
_add(_R("factor_of_safety", "n = S / sigma",
        {"n": "", "S": "pascal", "sigma": "pascal"},
        "Factor of safety = strength / applied_stress", "safety",
        r"n = \frac{S}{\sigma}"))

_add(_R("euler_buckling", "Pcr = (pi**2 * E * I) / (Le**2)",
        {"Pcr": "newton", "E": "pascal", "I": "meter**4", "Le": "meter"},
        "Euler critical buckling load (Le = effective length)", "safety",
        r"P_{cr} = \frac{\pi^2 E I}{L_e^2}"))

# --- Material relations ---------------------------------------------------
_add(_R("hookes_law", "sigma = E * eps",
        {"sigma": "pascal", "E": "pascal", "eps": ""},
        "Hooke's law (uniaxial): stress = modulus * strain", "material",
        r"\sigma = E \varepsilon"))

_add(_R("shear_modulus", "G = E / (2 * (1 + nu))",
        {"G": "pascal", "E": "pascal", "nu": ""},
        "Shear modulus from Young's modulus and Poisson's ratio", "material",
        r"G = \frac{E}{2(1+\nu)}"))

# --- Dynamics / misc ------------------------------------------------------
_add(_R("newton_second_law", "F = m * a",
        {"F": "newton", "m": "kilogram", "a": "meter/second**2"},
        "Force = mass * acceleration", "dynamics", r"F = m a"))

_add(_R("reynolds_number", "Re = (rho * v * d) / mu",
        {"Re": "", "rho": "kilogram/meter**3", "v": "meter/second",
         "d": "meter", "mu": "pascal*second"},
        "Reynolds number (flow regime)", "dynamics",
        r"Re = \frac{\rho v d}{\mu}"))


def get_manifest() -> List[Dict[str, Any]]:
    """Compact relation catalog for LLM consumption."""
    return [
        {
            "name": rel.name,
            "category": rel.category,
            "description": rel.description,
            "variables": rel.variables,
            "units": rel.units,
            "equation": rel.equation_str,
            "formula_latex": rel.formula_latex,
        }
        for rel in RELATIONS.values()
    ]
