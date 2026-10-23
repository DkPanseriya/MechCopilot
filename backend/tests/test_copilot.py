"""Copilot orchestration: plan parsing, input normalisation, offline and model paths."""
import json

import pytest

import copilot
from copilot import _clean_inputs, normalise_tools, parse_plan, respond


def _events(gen):
    return list(gen)


# --- input normalisation ----------------------------------------------------

def test_clean_inputs_accepts_numbers_dicts_and_strings():
    cleaned, dropped = _clean_inputs("round_bar_combined", {
        "D": 40,                                   # number in the param's default unit (mm)
        "F": {"value": 12, "unit": "kN"},
        "M": "250 N*m",                            # string with unit
        "T": "1.5 kN*m",
        "material": "C45 quenched & tempered (EN 10083-2)",  # option label
        "bogus": 3,
    })
    assert cleaned["D"] == {"value": 40.0, "unit": "mm"}
    assert cleaned["F"] == {"value": 12.0, "unit": "kN"}
    assert cleaned["M"] == {"value": 250.0, "unit": "N*m"}
    assert cleaned["T"] == {"value": 1.5, "unit": "kN*m"}
    assert cleaned["material"] == "c45_qt"
    assert dropped == ["bogus"]


def test_clean_inputs_converts_units_outside_the_choice_list():
    cleaned, _ = _clean_inputs("round_bar_combined", {"D": "0.5 dm"})
    assert cleaned["D"]["unit"] == "mm"
    assert cleaned["D"]["value"] == pytest.approx(50.0)


def test_clean_inputs_drops_wrong_dimension_and_bad_options():
    cleaned, dropped = _clean_inputs("round_bar_combined", {"D": "5 kg", "material": "unobtainium"})
    assert "D" not in cleaned and "material" not in cleaned
    assert set(dropped) == {"D", "material"}


def test_parse_plan_tolerates_prose_around_json():
    text = 'Sure.\n```json\n{"title": "Shaft", "tools": [{"calculator": "round_bar_combined", "inputs": {}}]}\n```'
    plan = parse_plan(text)
    assert plan and plan["tools"][0]["calculator"] == "round_bar_combined"


def test_normalise_tools_rejects_unknown_and_dedupes():
    tools, notes = normalise_tools({"tools": [
        {"calculator": "round_bar_combined", "inputs": {"D": 30}},
        {"calculator": "round_bar_combined", "inputs": {"D": 30}},
        {"calculator": "does_not_exist", "inputs": {}},
    ]})
    assert len(tools) == 1 and tools[0]["type"] == "calc"
    assert any("does_not_exist" in n for n in notes)


# --- offline path ------------------------------------------------------------

def test_offline_respond_runs_matching_calculator(monkeypatch):
    monkeypatch.setenv("MECH_DEMO_MODE", "1")
    events = _events(respond("check von mises stress on my shaft", [], "efficient"))
    types = [e["type"] for e in events]
    assert "tool" in types and "token" in types and types[-1] == "final"
    final = events[-1]
    assert final["tool_data"]["tools"][0]["calculator"] == "round_bar_combined"
    assert final["tool_data"]["results"][0]["verdict"] in ("ok", "warn", "fail")
    assert "Offline mode" in final["content"]


def test_offline_respond_without_match_still_answers(monkeypatch):
    monkeypatch.setenv("MECH_DEMO_MODE", "1")
    events = _events(respond("hello there", [], "efficient"))
    assert events[-1]["type"] == "final"
    assert events[-1]["tool_data"]["tools"] == []


# --- model path (provider mocked) --------------------------------------------

def test_model_path_plans_computes_and_streams(monkeypatch):
    monkeypatch.delenv("MECH_DEMO_MODE", raising=False)
    monkeypatch.setattr(copilot, "provider", lambda: "replicate")
    plan = {"title": "Drive shaft check", "intent": "check",
            "tools": [{"calculator": "round_bar_combined",
                       "inputs": {"D": 30, "T": {"value": 400, "unit": "N*m"}},
                       "purpose": "static check"}],
            "assumptions": ["C45 normalised"], "missing": []}
    seen = {}

    def fake_complete(system, prompt, tier="efficient", max_tokens=0):
        seen["plan_prompt"] = system + prompt
        return "Here is the plan: " + json.dumps(plan)

    def fake_stream(system, prompt, tier="efficient", max_tokens=0):
        seen["answer_prompt"] = prompt
        yield "The shaft "
        yield "passes."

    monkeypatch.setattr(copilot, "llm_complete", fake_complete)
    monkeypatch.setattr(copilot, "llm_stream", fake_stream)

    events = _events(respond("Is a 30 mm C45 shaft OK for 400 N·m?", [], "efficient"))
    final = events[-1]
    assert "round_bar_combined" in seen["plan_prompt"]          # catalog was in the prompt
    assert "COMPUTED RESULTS" in seen["answer_prompt"]           # review saw real numbers
    assert final["content"] == "The shaft passes."
    assert final["title"] == "Drive shaft check"
    tool = final["tool_data"]["tools"][0]
    assert tool["inputs"]["T"] == {"value": 400.0, "unit": "N*m"}
    assert final["tool_data"]["results"][0]["outputs"]


def test_model_failure_falls_back_to_offline(monkeypatch):
    monkeypatch.delenv("MECH_DEMO_MODE", raising=False)
    monkeypatch.setattr(copilot, "provider", lambda: "replicate")

    def boom(*a, **k):
        raise copilot.LLMError("Replicate rejected the API token.")

    monkeypatch.setattr(copilot, "llm_complete", boom)
    events = _events(respond("von mises on a round bar", [], "efficient"))
    assert any(e["type"] == "notice" and "rejected" in e["content"] for e in events)
    assert events[-1]["tool_data"]["tools"][0]["calculator"] == "round_bar_combined"


def test_catalog_prompt_lists_every_calculator():
    from engineering.registry import CATALOG
    text = copilot.catalog_prompt()
    for cid in CATALOG:
        assert f"- {cid}:" in text
