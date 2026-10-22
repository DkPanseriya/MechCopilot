"""Tests for the typed UISpec contract and the model-provider mapping."""
import pytest

from backend.ui_spec import parse_ui_spec, ui_spec_json_schema
from backend.model_provider import (
    extract_ui_spec_from_text,
    to_tool_data,
    supports_structured,
)


# --- schema / validation --------------------------------------------------

def test_valid_calculator_parses():
    spec = parse_ui_spec({
        "type": "calculator",
        "title": "Torsional Shear Stress",
        "relation": "torsional_stress_solid",
        "solve_for": "tau",
        "output_unit": "MPa",
        "inputs": [
            {"name": "T", "label": "Torque", "unit_type": "torque"},
            {"name": "d", "label": "Diameter", "unit_type": "length"},
        ],
    })
    assert spec.type == "calculator"
    assert spec.relation == "torsional_stress_solid"


def test_unknown_relation_rejected():
    with pytest.raises(ValueError):
        parse_ui_spec({
            "type": "calculator", "title": "x",
            "relation": "made_up_relation", "solve_for": "y",
        })


def test_bad_solve_for_rejected():
    with pytest.raises(ValueError):
        parse_ui_spec({
            "type": "calculator", "title": "x",
            "relation": "axial_stress", "solve_for": "zzz",
        })


def test_bad_input_name_rejected():
    with pytest.raises(ValueError):
        parse_ui_spec({
            "type": "calculator", "title": "x",
            "relation": "axial_stress", "solve_for": "sigma",
            "inputs": [{"name": "not_a_var", "label": "Nope"}],
        })


def test_workflow_parses_and_validates_steps():
    spec = parse_ui_spec({
        "type": "workflow", "title": "Shaft Combined Loading",
        "steps": [
            {"step_id": "1", "relation": "torsional_stress_solid", "solve_for": "tau",
             "inputs": {"T": 500, "d": 0.05}},
            {"step_id": "2", "relation": "axial_stress", "solve_for": "sigma",
             "inputs": {"F": 1000, "A": "step_1.result"}},
        ],
    })
    assert spec.type == "workflow"
    assert len(spec.steps) == 2


def test_workflow_bad_step_relation_rejected():
    with pytest.raises(ValueError):
        parse_ui_spec({
            "type": "workflow", "title": "bad",
            "steps": [{"step_id": "1", "relation": "nope", "solve_for": "x", "inputs": {}}],
        })


def test_chart_parses():
    spec = parse_ui_spec({
        "type": "chart", "title": "Stress vs Diameter",
        "relation": "torsional_stress_solid", "solve_for": "tau",
        "sweep_var": "d", "sweep_range": {"min": 0.02, "max": 0.08, "steps": 20},
        "fixed_inputs": {"T": 500},
    })
    assert spec.type == "chart"
    assert spec.sweep_range.steps == 20


def test_discriminator_selects_variant():
    assert parse_ui_spec({"type": "material", "title": "Steel", "material_key": "Steel 1018"}).type == "material"
    assert parse_ui_spec({"type": "figure", "title": "Shaft", "figure_id": "shaft_bending_torsion"}).type == "figure"


def test_json_schema_generates():
    schema = ui_spec_json_schema()
    assert isinstance(schema, dict)


# --- model-provider mapping ----------------------------------------------

def test_extract_legacy_calculator_from_text():
    text = 'Here is the result.\n```json\n{"tool_name":"Torsion","relation":"torsional_stress_solid","solve_for":"tau","inputs":[{"name":"T","label":"Torque"},{"name":"d","label":"Dia"}]}\n```'
    spec = extract_ui_spec_from_text(text)
    assert spec and spec["type"] == "calculator"
    assert spec["relation"] == "torsional_stress_solid"


def test_extract_legacy_workflow_from_text():
    text = '{"workflow_name":"Combined","steps":[{"step_id":"1","relation":"axial_stress","solve_for":"sigma","inputs":{"F":1000,"A":0.001}}]}'
    spec = extract_ui_spec_from_text(text)
    assert spec and spec["type"] == "workflow"


def test_formula_js_only_calculator_is_dropped():
    # No `relation` -> cannot compute safely -> no spec.
    text = '{"tool_name":"Old","formula_js":"return force/area;","inputs":[]}'
    assert extract_ui_spec_from_text(text) is None


def test_extract_returns_none_for_plain_text():
    assert extract_ui_spec_from_text("Just a normal answer, no JSON.") is None


def test_to_tool_data_calculator_shape():
    spec = parse_ui_spec({
        "type": "calculator", "title": "Axial", "relation": "axial_stress",
        "solve_for": "sigma", "inputs": [{"name": "F", "label": "Force"}, {"name": "A", "label": "Area"}],
    }).model_dump()
    td = to_tool_data(spec)
    assert td["tool_name"] == "Axial"
    assert td["relation"] == "axial_stress"
    assert td["ui_spec"]["type"] == "calculator"


def test_to_tool_data_workflow_shape():
    spec = parse_ui_spec({
        "type": "workflow", "title": "WF",
        "steps": [{"step_id": "1", "relation": "axial_stress", "solve_for": "sigma", "inputs": {}}],
    }).model_dump()
    td = to_tool_data(spec)
    assert td["workflow_name"] == "WF"
    assert "steps" in td


def test_supports_structured_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert supports_structured() is False
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert supports_structured() is True
