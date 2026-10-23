"""
UISpec — the typed contract between the model and the frontend.

The model never emits executable code or markup. It emits a UISpec: a
discriminated union (by `type`) that names a widget from the registry and fills
typed, validated props. The server validates every relation / variable / figure
reference against the libraries before anything renders. This mirrors the
ChatGPT Apps / Vercel AI SDK pattern (component registry + typed props), adapted
for engineering (see product/GENERATIVE_ENGINE_PLAN.md Part 3 & 7).

Pydantic v2. The Zod mirror lives in frontend/types/uiSpec.ts — keep the two in
sync.
"""
from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, field_validator

from physics_kernel import RELATIONS


# --- shared pieces --------------------------------------------------------

UnitType = Literal[
    "length", "force", "pressure", "area", "mass", "density",
    "modulus_of_elasticity", "torque", "acceleration", "velocity",
    "time", "energy", "power", "temperature", "angle",
]


class InputField(BaseModel):
    name: str                       # MUST be a variable of the chosen relation
    label: str
    type: Literal["number", "text"] = "number"
    unit: Optional[str] = None
    unit_type: Optional[UnitType] = None
    default_value: Optional[Any] = None


class SpecBase(BaseModel):
    title: str
    description: Optional[str] = None
    citations: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None


# --- widget variants ------------------------------------------------------

class CalculatorSpec(SpecBase):
    type: Literal["calculator"] = "calculator"
    relation: str
    solve_for: str
    output_unit: Optional[str] = None
    formula_latex: Optional[str] = None
    inputs: List[InputField] = Field(default_factory=list)

    @field_validator("relation")
    @classmethod
    def _relation_exists(cls, v: str) -> str:
        if v not in RELATIONS:
            raise ValueError(f"Unknown relation '{v}'.")
        return v


class WorkflowStep(BaseModel):
    step_id: str
    relation: str
    solve_for: str
    explanation: Optional[str] = None
    # Value is a number, a unit string ("10 mm"), or a "step_N.result" reference.
    inputs: Dict[str, Union[float, int, str]] = Field(default_factory=dict)
    output_unit: Optional[str] = None


class WorkflowSpec(SpecBase):
    type: Literal["workflow"] = "workflow"
    steps: List[WorkflowStep] = Field(default_factory=list)


class SweepRange(BaseModel):
    min: float
    max: float
    steps: int = 25


class ChartSpec(SpecBase):
    type: Literal["chart"] = "chart"
    chart_kind: Literal["line", "bar", "scatter"] = "line"
    relation: str
    solve_for: str
    sweep_var: str
    sweep_range: SweepRange
    sweep_unit: Optional[str] = None
    output_unit: Optional[str] = None
    fixed_inputs: Dict[str, Union[float, int, str]] = Field(default_factory=dict)

    @field_validator("relation")
    @classmethod
    def _relation_exists(cls, v: str) -> str:
        if v not in RELATIONS:
            raise ValueError(f"Unknown relation '{v}'.")
        return v


class FigureSpec(SpecBase):
    type: Literal["figure"] = "figure"
    figure_id: str
    annotations: Optional[Dict[str, Any]] = None
    caption: Optional[str] = None


class SelectorSpec(SpecBase):
    type: Literal["selector"] = "selector"
    service: Literal["bearing", "fastener"]
    constraints: Dict[str, Any] = Field(default_factory=dict)


class ComparisonSpec(SpecBase):
    type: Literal["comparison"] = "comparison"
    columns: List[str] = Field(default_factory=list)
    options: List[Dict[str, Any]] = Field(default_factory=list)
    recommendation: Optional[str] = None


class MaterialCardSpec(SpecBase):
    type: Literal["material"] = "material"
    material_key: str


class CalcSpec(SpecBase):
    """A calculator from the engineering library, prefilled with inputs."""
    type: Literal["calc"] = "calc"
    calculator: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    purpose: Optional[str] = None

    @field_validator("calculator")
    @classmethod
    def _calculator_exists(cls, v: str) -> str:
        from engineering.registry import CATALOG
        if v not in CATALOG:
            raise ValueError(f"Unknown calculator '{v}'.")
        return v


UISpec = Annotated[
    Union[
        CalcSpec,
        CalculatorSpec,
        WorkflowSpec,
        ChartSpec,
        FigureSpec,
        SelectorSpec,
        ComparisonSpec,
        MaterialCardSpec,
    ],
    Field(discriminator="type"),
]

_ADAPTER: TypeAdapter = TypeAdapter(UISpec)


# --- validation entry points ---------------------------------------------

def validate_cross_refs(spec: BaseModel) -> List[str]:
    """Deeper checks the per-field validators can't do alone.

    Returns a list of human-readable problems (empty = OK). Relation existence
    is already enforced by field validators; here we check that solve_for and
    input/variable names actually belong to the referenced relation.
    """
    problems: List[str] = []

    if isinstance(spec, CalculatorSpec):
        rel = RELATIONS.get(spec.relation)
        if rel:
            if spec.solve_for not in rel.variables:
                problems.append(
                    f"solve_for '{spec.solve_for}' not a variable of '{spec.relation}' {rel.variables}")
            for inp in spec.inputs:
                if inp.name not in rel.variables:
                    problems.append(
                        f"input '{inp.name}' not a variable of '{spec.relation}' {rel.variables}")

    elif isinstance(spec, ChartSpec):
        rel = RELATIONS.get(spec.relation)
        if rel:
            for var in (spec.solve_for, spec.sweep_var):
                if var not in rel.variables:
                    problems.append(f"'{var}' not a variable of '{spec.relation}' {rel.variables}")

    elif isinstance(spec, WorkflowSpec):
        for step in spec.steps:
            rel = RELATIONS.get(step.relation)
            if not rel:
                problems.append(f"step {step.step_id}: unknown relation '{step.relation}'")
                continue
            if step.solve_for not in rel.variables:
                problems.append(
                    f"step {step.step_id}: solve_for '{step.solve_for}' not in {rel.variables}")

    return problems


def parse_ui_spec(data: Dict[str, Any]) -> UISpec:
    """Validate a raw dict into a typed UISpec. Raises ValueError on failure."""
    try:
        spec = _ADAPTER.validate_python(data)
    except ValidationError as e:
        raise ValueError(f"UISpec schema validation failed: {e}") from e

    problems = validate_cross_refs(spec)
    if problems:
        raise ValueError("UISpec reference errors: " + "; ".join(problems))
    return spec


def ui_spec_json_schema() -> Dict[str, Any]:
    """JSON Schema for the union — fed to a model's structured-output mode."""
    return _ADAPTER.json_schema()
