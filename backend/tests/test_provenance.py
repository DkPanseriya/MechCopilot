"""Input provenance: every input says where it came from, and demo defaults never decide a verdict."""
import json

import pytest

import copilot
from copilot import _given_inputs, _plain_label, clarify_for_missing, normalise_tools, respond, summarise
from engineering.core import derived_inputs, run_calculator
from engineering.registry import CATALOG


def _events(gen):
    return list(gen)


def _model(monkeypatch, plan, answer="Done."):
    """Fake provider: returns `plan` for the planning step, `answer` as the streamed review."""
    monkeypatch.delenv("MECH_DEMO_MODE", raising=False)
    monkeypatch.setattr(copilot, "provider", lambda: "replicate")
    prompts = {}

    def fake_complete(system, prompt, *a, **k):
        prompts.setdefault("plan", prompt)
        return json.dumps(plan) if "FOLLOW-UP" not in system else '{"tools": []}'

    def fake_stream(system, prompt, *a, **k):
        prompts["answer"] = prompt
        yield answer

    monkeypatch.setattr(copilot, "llm_complete", fake_complete)
    monkeypatch.setattr(copilot, "llm_stream", fake_stream)
    return prompts


# --- calculator declarations ------------------------------------------------

@pytest.mark.parametrize("calc_id", sorted(CATALOG))
def test_every_calculator_declares_governing_inputs(calc_id):
    calc = CATALOG[calc_id]
    names = {p.name for p in calc.params}
    assert calc.governing, f"{calc_id} declares no governing inputs"
    assert set(calc.governing) <= names
    assert set(calc.trial) <= names
    assert not set(calc.trial) & set(calc.governing)
    assert set(calc.derived_defaults) <= names


def test_cantilever_point_load_defaults_to_the_tip():
    """A 6 ft cantilever with a tip load: the 2.5 m demo position would lie outside the beam."""
    inputs = {"L": {"value": 6, "unit": "ft"}, "support": "cantilever",
              "P1": {"value": 200, "unit": "lbf"}, "w1": {"value": 0, "unit": "kN/m"},
              "section_mode": "shape", "shape": "rectangle",
              "b": {"value": 2, "unit": "inch"}, "h": {"value": 2, "unit": "inch"}, "self_weight": False}
    x1, why = derived_inputs(CATALOG["beam_analysis"], inputs)["x1"]
    assert x1["value"] == pytest.approx(1.8288) and why == "tip of the cantilever"
    r = run_calculator(CATALOG["beam_analysis"], inputs)
    defl = next(o for o in r["outputs"] if o["label"] == "Max deflection")
    # δ = PL³/(3EI): P = 889.6 N, L = 1.8288 m, E = 210 GPa, I = 0.0508⁴/12 m⁴
    expected = 889.644 * 1.8288 ** 3 / (3 * 210e9 * 0.0508 ** 4 / 12) * 1000
    assert defl["value"] == pytest.approx(expected, rel=0.01)


def test_given_position_is_not_overridden():
    x = derived_inputs(CATALOG["beam_analysis"], {"L": 4, "support": "cantilever",
                                                  "x1": {"value": 1, "unit": "m"}})
    assert "x1" not in x


# --- normalisation ------------------------------------------------------------

def test_provenance_records_user_assumed_derived_and_default():
    tools, _ = normalise_tools({"tools": [{"calculator": "beam_analysis", "inputs": {
        "L": {"value": 4, "unit": "m", "source": "user"},
        "w1": {"value": 12, "unit": "kN/m", "source": "user"},
        "support": {"value": "simply_supported", "source": "assumed", "why": "not stated"},
        "profile": {"value": "IPE 200", "source": "user"}}}]})
    prov = tools[0]["provenance"]
    assert prov["L"]["source"] == "user" and prov["w1"]["source"] == "user"
    assert prov["support"] == {"source": "assumed", "why": "not stated"}
    assert prov["P1"]["source"] == "derived"                     # load not described -> zero
    assert tools[0]["inputs"]["P1"]["value"] == 0
    assert prov["material"]["source"] == "default"
    assert "I_direct" not in prov                                # hidden in profile mode
    assert tools[0]["missing"] == []


def test_missing_governing_inputs_are_listed():
    tools, _ = normalise_tools({"tools": [{"calculator": "bearing_selector", "inputs": {
        "Fr": {"value": 3.5, "unit": "kN", "source": "user"}}}]})
    assert tools[0]["missing"] == ["n", "bore_min"]               # Fa is zeroed as part of the load set


def test_clarify_questions_use_plain_labels_and_units():
    tools, _ = normalise_tools({"tools": [{"calculator": "beam_analysis", "inputs": {}}]})
    clarify = clarify_for_missing(tools)
    labels = [q["label"] for q in clarify["questions"]]
    assert labels[:4] == ["Beam length", "Supports", "Point load", "Distributed load"]
    assert len(labels) <= 5
    assert next(q for q in clarify["questions"] if q["label"] == "Beam length")["unit"] == "m"
    assert next(q for q in clarify["questions"] if q["label"] == "Supports")["options"]


@pytest.mark.parametrize("raw,plain", [
    ("Radial load Fr", "Radial load"), ("Point load P1 (down +)", "Point load"),
    ("Alternating bending moment Ma", "Alternating bending moment"), ("Required life", "Required life"),
    ("Thread", "Thread"), ("Design shear load FEd (total)", "Design shear load"), ("Bore to", "Bore to"),
])
def test_plain_label(raw, plain):
    assert _plain_label(raw) == plain


def test_history_lists_only_given_and_assumed_inputs():
    tools, _ = normalise_tools({"tools": [{"calculator": "round_bar_combined", "inputs": {
        "D": {"value": 40, "source": "user"}, "T": {"value": 300, "unit": "N*m", "source": "assumed"}}}]})
    text = _given_inputs(tools[0])
    assert "D=40 mm" in text and "T=300 N*m (assumed)" in text
    assert "F=" not in text and "material" not in text           # derived zero and default left out


def test_summary_separates_given_assumed_and_default_inputs():
    tools, _ = normalise_tools({"tools": [{"calculator": "round_bar_combined", "inputs": {
        "D": {"value": 40, "source": "user"}, "T": {"value": 300, "unit": "N*m", "source": "user"}}}]})
    s = summarise([{"calculator": "round_bar_combined", "title": "x", "ok": True,
                    "result": run_calculator(CATALOG["round_bar_combined"], tools[0]["inputs"])}], tools)[0]
    assert s["inputs"] == {"Outer diameter D": "40 mm", "Torque T": "300 N·m"}
    assert "Axial force F" in s["assumed"] and "Material" in s["defaults_used"]


# --- orchestration -------------------------------------------------------------

def test_governing_default_asks_instead_of_computing(monkeypatch):
    """The IPE 200 failure mode: the plan forgot the load, so the demo load would decide the verdict."""
    _model(monkeypatch, {"title": "Beam", "intent": "check", "tools": [{"calculator": "beam_analysis", "inputs": {
        "L": {"value": 4, "unit": "m", "source": "user"},
        "support": {"value": "simply_supported", "source": "user"},
        "profile": {"value": "IPE 200", "source": "user"}}}]})
    events = _events(respond("Check an IPE 200 over 4 m", [], "efficient"))
    types = [e["type"] for e in events]
    assert "clarify" in types and "tool" not in types
    clarify = next(e for e in events if e["type"] == "clarify")
    assert [q["label"] for q in clarify["questions"]] == ["Point load", "Distributed load"]
    assert events[-1]["tool_data"]["tools"] == []


def test_explain_runs_defaults_as_a_labelled_example(monkeypatch):
    prompts = _model(monkeypatch, {"title": "Combined stress", "intent": "explain",
                                   "tools": [{"calculator": "round_bar_combined", "inputs": {}}]})
    events = _events(respond("How do bending and torsion combine on a shaft?", [], "efficient"))
    final = events[-1]
    assert final["tool_data"]["tools"][0]["example"] is True
    assert final["tool_data"]["results"][0]["example"] is True
    assert '"example": true' in prompts["answer"]


def test_go_ahead_runs_provisional_with_defaults_named(monkeypatch):
    prompts = _model(monkeypatch, {"title": "Bearing", "intent": "selection", "tools": [
        {"calculator": "bearing_selector", "inputs": {"Fr": {"value": 3.5, "unit": "kN", "source": "user"}}}]})
    events = _events(respond("3.5 kN radial, use typical values for the rest", [], "efficient"))
    tool = events[-1]["tool_data"]["tools"][0]
    assert tool["provisional"] == ["n", "bore_min"]
    assert "Rotational speed n = 1500 rpm" in prompts["answer"]


def test_never_asks_twice_in_a_row(monkeypatch):
    _model(monkeypatch, {"title": "Bearing", "intent": "selection", "tools": [
        {"calculator": "bearing_selector", "inputs": {"Fr": {"value": 3.5, "unit": "kN", "source": "user"}}}]})
    history = [{"role": "user", "content": "I need a bearing"},
               {"role": "assistant", "content": "A few details first.",
                "tool_data": {"clarify": {"questions": [{"label": "Radial load"}]}}}]
    events = _events(respond("Radial load: 3.5 kN", history, "efficient"))
    assert "clarify" not in [e["type"] for e in events]
    assert events[-1]["tool_data"]["tools"][0]["provisional"]


def test_offline_runs_are_examples(monkeypatch):
    monkeypatch.setenv("MECH_DEMO_MODE", "1")
    final = _events(respond("check von mises stress on my shaft", [], "efficient"))[-1]
    assert final["tool_data"]["tools"][0]["example"] is True
    assert "example values" in final["content"]


def test_old_sessions_without_provenance_still_summarise():
    tool = {"type": "calc", "calculator": "round_bar_combined", "title": "x",
            "inputs": {"D": {"value": 40, "unit": "mm"}}}
    assert "round_bar_combined(D=40 mm)" == _given_inputs(tool)
    s = summarise([{"calculator": "round_bar_combined", "title": "x", "ok": True,
                    "result": run_calculator(CATALOG["round_bar_combined"], tool["inputs"])}], [tool])[0]
    assert s["inputs"] == {"Outer diameter D": "40 mm"} and s["outputs"]


def test_provider_failure_is_marked_degraded(monkeypatch):
    """A billing or network failure falls back to offline answers; evals must not count them."""
    monkeypatch.delenv("MECH_DEMO_MODE", raising=False)
    monkeypatch.setattr(copilot, "provider", lambda: "replicate")

    def refuse(*a, **k):
        raise copilot.LLMError("Replicate refused the request for billing reasons.")

    monkeypatch.setattr(copilot, "llm_complete", refuse)
    final = _events(respond("check von mises stress on my shaft", [], "efficient"))[-1]
    assert final["tool_data"]["degraded"] is True
    assert final["tool_data"]["tools"][0]["example"] is True
