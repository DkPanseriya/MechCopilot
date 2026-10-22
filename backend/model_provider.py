"""
Model layer — provider-abstracted structured generation.

Phase 1 moves the dynamic-UI contract off "scrape JSON from a chatty 8B model"
onto a validated UISpec.

Two providers:
  * OpenAI (preferred when OPENAI_API_KEY is set): JSON mode, returns a single
    envelope {"narration", "ui_spec"} which we validate against ui_spec.py.
  * Replicate Llama (fallback): existing streaming text; we extract the first
    JSON object and validate / map it to a UISpec.

Either way the result is a validated spec or None — never executable code, and
never an unvalidated blob reaching the frontend.
"""
import os
import json
from typing import Any, Dict, List, Optional, TypedDict

from ui_spec import parse_ui_spec
from llm_utils import extract_balanced_json, try_parse_json


class GenResult(TypedDict):
    narration: str
    ui_spec: Optional[Dict[str, Any]]  # validated UISpec, model_dump()ed


def supports_structured() -> bool:
    """True when the reliable structured-output provider is configured."""
    return bool(os.getenv("OPENAI_API_KEY"))


def use_demo() -> bool:
    """Offline deterministic provider (default ON).

    The POC runs with no external LLM: intents are matched to validated UISpecs
    and computed by the real kernel. Set MECH_DEMO_MODE=0 to use a real model
    (OpenAI if OPENAI_API_KEY is set, else Replicate).
    """
    return os.getenv("MECH_DEMO_MODE", "1") != "0"


# --- OpenAI structured path ----------------------------------------------

_ENVELOPE_INSTRUCTION = """
### OUTPUT ENVELOPE (STRICT)
Respond with a SINGLE JSON object, nothing else:
{
  "narration": "<your markdown answer to the user>",
  "ui_spec": <one UISpec object, or null if no widget is needed>
}

A UISpec carries a "type" discriminator and a "title". Use these shapes
(reference ONLY relations from the MANIFEST; never include executable code):

calculator (single relation):
{
  "type": "calculator",
  "title": "Torsional Shear Stress",
  "relation": "torsional_stress_solid",
  "solve_for": "tau",
  "output_unit": "MPa",
  "formula_latex": "\\\\tau = \\\\frac{16 T}{\\\\pi d^3}",
  "inputs": [
    {"name": "T", "label": "Torque", "unit_type": "torque", "default_value": 500},
    {"name": "d", "label": "Diameter", "unit_type": "length", "default_value": 50}
  ],
  "suggestions": ["Check combined stress if bending is also present."]
}
Every inputs[].name MUST be a variable of the chosen relation; "solve_for" too.

workflow (stack multiple relations; a step input may be "step_N.result"):
{
  "type": "workflow",
  "title": "Shaft Combined Loading",
  "steps": [
    {"step_id": "1", "relation": "torsional_stress_solid", "solve_for": "tau",
     "inputs": {"T": 500, "d": 0.05}}
  ]
}

If no widget helps, set "ui_spec": null.
"""


def generate_structured(
    messages: List[Dict[str, str]],
    system_prompt: str,
    tier: str = "efficient",
) -> GenResult:
    """OpenAI JSON-mode generation. Returns narration + validated ui_spec."""
    from openai import OpenAI  # lazy import

    client = OpenAI()
    model = "gpt-4o" if tier == "deep" else "gpt-4o-mini"

    full_system = system_prompt + "\n" + _ENVELOPE_INSTRUCTION
    chat_messages = [{"role": "system", "content": full_system}, *messages]

    resp = client.chat.completions.create(
        model=model,
        messages=chat_messages,
        response_format={"type": "json_object"},
        temperature=0.7 if tier == "deep" else 0.4,
    )
    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {"narration": content, "ui_spec": None}

    narration = data.get("narration", "") or ""
    return {"narration": narration, "ui_spec": _validate_or_none(data.get("ui_spec"))}


# --- Replicate fallback: extract a spec from free text -------------------

def extract_ui_spec_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Find the first JSON object in LLM text and validate/map it to a UISpec."""
    if not text:
        return None
    # Scan for a balanced JSON object (skip code fences handled by the scan).
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        raw = extract_balanced_json(text, i)
        if not raw:
            continue
        parsed = try_parse_json(raw)
        if not isinstance(parsed, dict):
            continue
        parsed = parsed.get("arguments", parsed)
        mapped = _map_legacy(parsed)
        if mapped is not None:
            validated = _validate_or_none(mapped)
            if validated:
                return validated
    return None


def _map_legacy(parsed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map older LLM JSON shapes onto a UISpec dict."""
    if "type" in parsed:
        return parsed  # already a UISpec
    if parsed.get("steps") or parsed.get("workflow_name"):
        return {
            "type": "workflow",
            "title": parsed.get("workflow_name", "Workflow"),
            "description": parsed.get("description"),
            "steps": parsed.get("steps", []),
            "suggestions": parsed.get("suggestions"),
        }
    if parsed.get("relation") and parsed.get("solve_for"):
        return {
            "type": "calculator",
            "title": parsed.get("tool_name", "Calculator"),
            "description": parsed.get("description"),
            "relation": parsed["relation"],
            "solve_for": parsed["solve_for"],
            "output_unit": parsed.get("output_unit"),
            "formula_latex": parsed.get("formula_latex"),
            "inputs": parsed.get("inputs", []),
            "suggestions": parsed.get("suggestions"),
        }
    # Legacy formula_js-only calculators can no longer compute safely — drop.
    return None


def _validate_or_none(spec_raw: Any) -> Optional[Dict[str, Any]]:
    if not spec_raw or not isinstance(spec_raw, dict):
        return None
    try:
        return parse_ui_spec(spec_raw).model_dump()
    except ValueError as e:
        print(f"UISpec rejected: {e}")
        return None


# --- frontend compatibility ----------------------------------------------

## --- offline demo provider ------------------------------------------------
# Deterministic intent matching -> narration + UISpec. Real compute still runs
# in the kernel/selectors; only the "which widget + which inputs" decision is
# rule-based here instead of model-driven.

def _last_user(messages: List[Dict[str, str]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return (m.get("content") or "").lower()
    return ""


def _demo_intents(q: str):
    """Return (narration, ui_spec_dict|None) for a user query."""
    has = lambda *ws: any(w in q for w in ws)
    explain = has("explain", "revisit", "remind", "concept", "understand", "how do", "what is", "show me how")

    # Concept revisit: figure-first (annotated diagram + formula).
    if explain and has("bending", "torsion", "shaft"):
        return (
            "**Combined bending and torsion on a shaft.** A rotating shaft carrying a "
            "transverse load sees a bending stress $\\sigma_b = \\frac{32 M}{\\pi d^3}$ and, "
            "from the transmitted torque, a shear stress $\\tau_t = \\frac{16 T}{\\pi d^3}$. "
            "Combine them with the von Mises criterion for the equivalent stress "
            "$\\sigma' = \\sqrt{\\sigma_b^2 + 3\\tau_t^2}$, then check it against the yield "
            "strength with a factor of safety. The figure shows the stress element and how "
            "the two components superpose.",
            {
                "type": "figure", "title": "Shaft: Bending + Torsion",
                "figure_id": "shaft_bending_torsion",
                "caption": "Bending stress σ_b and torsional shear τ_t on the outer fibre; combine via von Mises.",
                "suggestions": ["Size the shaft diameter for a target safety factor.",
                                 "Plot equivalent stress vs. diameter."],
            },
        )

    # Combined loading: stacked workflow.
    if has("combined", "equivalent stress", "von mises") and has("shaft", "bending", "torsion"):
        return (
            "Let's stack it: compute the torsional shear and the bending stress on the outer "
            "fibre, then combine with von Mises. Edit any input and the chain re-runs.",
            {
                "type": "workflow", "title": "Shaft Combined Loading",
                "description": "Torsion + bending → von Mises equivalent stress.",
                "steps": [
                    {"step_id": "1", "relation": "torsional_stress_solid", "solve_for": "tau",
                     "explanation": "Shear stress from the transmitted torque.",
                     "inputs": {"T": "250 N*m", "d": "40 mm"}},
                    {"step_id": "2", "relation": "shaft_equivalent_stress", "solve_for": "se",
                     "explanation": "Combine bending and torsional shear (von Mises).",
                     "inputs": {"sb": "80 MPa", "tt": "step_1.result"}},
                ],
                "suggestions": ["Add a factor-of-safety check against the material yield."],
            },
        )

    if has("bearing", "l10", "rating life", "rolling element"):
        return (
            "Here's a **bearing selector** driven by ISO 281 basic rating life "
            "$L_{10} = (C/P)^p$. Enter the dynamic load and speed; it ranks candidate "
            "bearings by life. Note: catalog C/C₀ values are representative estimates, not "
            "SKF-certified data.",
            {
                "type": "selector", "title": "Bearing Selector (ISO 281)",
                "service": "bearing",
                "constraints": {"P": 5000, "speed_rpm": 1500, "bore_min_mm": 20},
                "suggestions": ["Check static safety factor s₀ = C₀/P₀.",
                                 "Target a specific L10h life in hours."],
            },
        )

    if has("bolt", "fastener", "screw", "thread", "preload", "torque spec"):
        return (
            "A **fastener selector** for ISO metric bolts. Pick the load and it recommends a "
            "size/grade with preload $F_i = 0.9\\,A_t S_p$ and tightening torque $T = K F_i d$.",
            {
                "type": "selector", "title": "Fastener Selector (ISO metric)",
                "service": "fastener",
                "constraints": {"axial_load_N": 8000, "grade": "8.8"},
                "suggestions": ["Check combined shear + tension.",
                                 "Verify joint stiffness and separation."],
            },
        )

    if has("plot", "chart", "sweep", "sensitivity", " vs ", "vary", "over a range"):
        return (
            "Here's how the **torsional shear stress** varies with shaft diameter for a fixed "
            "torque — useful for sizing. Drag the range to explore.",
            {
                "type": "chart", "title": "Shear Stress vs Diameter",
                "chart_kind": "line",
                "relation": "torsional_stress_solid", "solve_for": "tau",
                "sweep_var": "d", "sweep_unit": "mm",
                "sweep_range": {"min": 20, "max": 80, "steps": 30},
                "output_unit": "MPa",
                "fixed_inputs": {"T": "250 N*m"},
                "suggestions": ["Overlay the allowable stress line."],
            },
        )

    if has("factor of safety", "safety factor", "fos", "safe"):
        return (
            "**Factor of safety** calculator: $n = S/\\sigma$. Enter the material strength and "
            "applied stress.",
            {
                "type": "calculator", "title": "Factor of Safety",
                "relation": "factor_of_safety", "solve_for": "n",
                "formula_latex": "n = \\frac{S}{\\sigma}",
                "inputs": [
                    {"name": "S", "label": "Strength (yield)", "unit": "MPa", "unit_type": "pressure", "default_value": 250},
                    {"name": "sigma", "label": "Applied Stress", "unit": "MPa", "unit_type": "pressure", "default_value": 125},
                ],
                "suggestions": ["Is this static or fatigue loading?"],
            },
        )

    if has("buckling", "column", "slender", "critical load"):
        return (
            "**Euler buckling** of a column: $P_{cr} = \\pi^2 E I / L_e^2$.",
            {
                "type": "calculator", "title": "Euler Buckling Load",
                "relation": "euler_buckling", "solve_for": "Pcr",
                "formula_latex": "P_{cr} = \\frac{\\pi^2 E I}{L_e^2}",
                "output_unit": "kN",
                "inputs": [
                    {"name": "E", "label": "Young's Modulus", "unit_type": "modulus_of_elasticity", "default_value": 200e9},
                    {"name": "I", "label": "Second Moment of Area", "unit": "m**4", "default_value": 1e-8},
                    {"name": "Le", "label": "Effective Length", "unit_type": "length", "default_value": 1},
                ],
            },
        )

    if has("torsion", "torque", "twist"):
        return (
            "**Torsional shear stress** in a solid shaft: $\\tau = 16T/\\pi d^3$.",
            {
                "type": "calculator", "title": "Torsional Shear Stress",
                "relation": "torsional_stress_solid", "solve_for": "tau",
                "formula_latex": "\\tau = \\frac{16 T}{\\pi d^3}",
                "output_unit": "MPa",
                "inputs": [
                    {"name": "T", "label": "Torque", "unit": "N*m", "unit_type": "torque", "default_value": 250},
                    {"name": "d", "label": "Shaft Diameter", "unit": "mm", "unit_type": "length", "default_value": 40},
                ],
                "suggestions": ["Combine with bending for the equivalent stress."],
            },
        )

    if has("bending", "moment", "flexure"):
        return (
            "**Bending stress**: $\\sigma = M y / I$.",
            {
                "type": "calculator", "title": "Bending Stress",
                "relation": "bending_stress", "solve_for": "sigma",
                "formula_latex": "\\sigma = \\frac{M y}{I}",
                "output_unit": "MPa",
                "inputs": [
                    {"name": "M", "label": "Bending Moment", "unit": "N*m", "unit_type": "torque", "default_value": 500},
                    {"name": "y", "label": "Dist. to Fibre", "unit": "mm", "unit_type": "length", "default_value": 25},
                    {"name": "I", "label": "Second Moment of Area", "unit": "m**4", "default_value": 5e-7},
                ],
            },
        )

    if has("thermal", "expansion", "temperature"):
        return (
            "**Thermal expansion**: $\\Delta L = \\alpha L \\Delta T$.",
            {
                "type": "calculator", "title": "Thermal Expansion",
                "relation": "thermal_expansion", "solve_for": "dL",
                "formula_latex": "\\Delta L = \\alpha L \\Delta T",
                "output_unit": "mm",
                "inputs": [
                    {"name": "alpha", "label": "Expansion Coeff (1/K)", "unit": "1/kelvin", "default_value": 12e-6},
                    {"name": "L", "label": "Length", "unit_type": "length", "default_value": 1},
                    {"name": "dT", "label": "Temp Rise (K)", "unit": "kelvin", "default_value": 50},
                ],
            },
        )

    if has("stress", "axial", "tensile", "load"):
        return (
            "**Axial stress**: $\\sigma = F/A$.",
            {
                "type": "calculator", "title": "Axial Stress",
                "relation": "axial_stress", "solve_for": "sigma",
                "formula_latex": "\\sigma = \\frac{F}{A}",
                "output_unit": "MPa",
                "inputs": [
                    {"name": "F", "label": "Axial Force", "unit": "N", "unit_type": "force", "default_value": 10000},
                    {"name": "A", "label": "Cross-section Area", "unit": "mm2", "unit_type": "area", "default_value": 500},
                ],
            },
        )

    return (
        "I'm your mechanical design co-pilot. Ask me to size a shaft, check combined "
        "bending and torsion, select a bearing or fastener, plot how a stress varies, or "
        "revisit a concept — I'll spin up the right interactive tool.",
        None,
    )


def generate_demo(messages: List[Dict[str, str]]) -> GenResult:
    narration, spec_raw = _demo_intents(_last_user(messages))
    return {"narration": narration, "ui_spec": _validate_or_none(spec_raw)}


def to_tool_data(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Adapt a validated UISpec to the shape the current ToolCard expects.

    (Phase 2 replaces ToolCard with a registry renderer that consumes UISpec
    directly; until then we keep the existing renderer working.)
    """
    t = spec.get("type")
    if t == "workflow":
        return {
            "workflow_name": spec.get("title"),
            "description": spec.get("description", ""),
            "steps": spec.get("steps", []),
            "suggestions": spec.get("suggestions"),
            "ui_spec": spec,
        }
    if t == "calculator":
        return {
            "tool_name": spec.get("title"),
            "description": spec.get("description", ""),
            "relation": spec.get("relation"),
            "solve_for": spec.get("solve_for"),
            "output_unit": spec.get("output_unit"),
            "formula_latex": spec.get("formula_latex"),
            "inputs": spec.get("inputs", []),
            "suggestions": spec.get("suggestions"),
            "ui_spec": spec,
        }
    # Other widget types pass through as-is; the frontend registry handles them.
    return {"tool_name": spec.get("title", t), "description": spec.get("description", ""), "ui_spec": spec}
