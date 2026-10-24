"""Copilot orchestration: plan parsing, input normalisation, offline and model paths."""
import json

import pytest

import copilot
from copilot import _clean_inputs, normalise_tools, parse_plan, respond


def _events(gen):
    return list(gen)


# --- input normalisation ----------------------------------------------------

def test_clean_inputs_accepts_numbers_dicts_and_strings():
    cleaned, dropped, sources = _clean_inputs("round_bar_combined", {
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
    assert all(s == {"source": "assumed"} for s in sources.values())  # no source given


def test_clean_inputs_converts_units_outside_the_choice_list():
    cleaned, _, _ = _clean_inputs("round_bar_combined", {"D": "0.5 dm"})
    assert cleaned["D"]["unit"] == "mm"
    assert cleaned["D"]["value"] == pytest.approx(50.0)


def test_clean_inputs_drops_wrong_dimension_and_bad_options():
    cleaned, dropped, _ = _clean_inputs("round_bar_combined", {"D": "5 kg", "material": "unobtainium"})
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

    def fake_complete(system, prompt, tier="efficient", max_tokens=0, **kw):
        seen["plan_prompt"] = system + prompt
        return "Here is the plan: " + json.dumps(plan)

    def fake_stream(system, prompt, tier="efficient", max_tokens=0, **kw):
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


def test_failed_check_triggers_follow_up_round(monkeypatch):
    """A failing result makes the model plan once more; the extra calculator is run and shown."""
    monkeypatch.delenv("MECH_DEMO_MODE", raising=False)
    monkeypatch.setattr(copilot, "provider", lambda: "replicate")
    calls = []

    def fake_complete(system, prompt, tier="efficient", max_tokens=0, **kw):
        calls.append(system)
        if "FOLLOW-UP" in system:
            assert "inputs" in prompt  # the follow-up sees what was run
            return json.dumps({"tools": [{"calculator": "round_bar_combined",
                                          "inputs": {"D": {"value": 60, "source": "assumed",
                                                           "why": "next size up"}},
                                          "purpose": "next size up"}]})
        # First plan: a deliberately undersized bar that fails its check.
        return json.dumps({"title": "Axle", "tools": [{"calculator": "round_bar_combined",
                                                       "inputs": {"D": {"value": 20, "source": "user"},
                                                                  "M": {"value": 1500, "unit": "N*m",
                                                                        "source": "user"}}}]})

    monkeypatch.setattr(copilot, "llm_complete", fake_complete)
    monkeypatch.setattr(copilot, "llm_stream", lambda *a, **k: iter(["Use D = 60 mm."]))
    events = _events(respond("Is a 20 mm axle OK for 1500 N·m bending?", [], "efficient"))
    final = events[-1]
    assert len(calls) == 2
    assert [t["inputs"]["D"]["value"] for t in final["tool_data"]["tools"]] == [20.0, 60.0]
    verdicts = [r["verdict"] for r in final["tool_data"]["results"]]
    assert verdicts[0] == "fail" and verdicts[1] in ("ok", "warn")
    assert sum(e["type"] == "tool" for e in events) == 2
    assert final["tool_data"]["results"][0]["inputs"]["Outer diameter D"] == "20 mm"
    # the follow-up kept the user's bending moment instead of falling back to the demo default
    assert final["tool_data"]["tools"][1]["inputs"]["M"] == {"value": 1500.0, "unit": "N*m"}
    assert final["tool_data"]["tools"][1]["provenance"]["M"]["source"] == "user"


def test_passing_result_skips_follow_up(monkeypatch):
    monkeypatch.delenv("MECH_DEMO_MODE", raising=False)
    monkeypatch.setattr(copilot, "provider", lambda: "replicate")
    calls = []
    monkeypatch.setattr(copilot, "llm_complete", lambda system, *a, **k: (calls.append(system), json.dumps(
        {"title": "x", "tools": [{"calculator": "round_bar_combined",
                                  "inputs": {"D": 60, "M": {"value": 200, "unit": "N*m"}}}]}))[1])
    monkeypatch.setattr(copilot, "llm_stream", lambda *a, **k: iter(["ok"]))
    _events(respond("check a 60 mm bar", [], "efficient"))
    assert len(calls) == 1


def _replay(chunks):
    state = {"out": "", "seg": ""}
    shown = "".join(copilot.dedupe_chunk(state, c) for c in chunks)
    return shown


def test_dedupe_recovers_replayed_stream():
    """Event sequence captured from Replicate's claude-sonnet-4.6 stream: the text restarts
    from the beginning three times mid-answer."""
    full = ("The preload of a property class 8.8 bolt is limited by its proof load (approximately "
            "85% of yield strength), beyond which permanent plastic deformation occurs.")
    chunks = [
        "", "The", " preload of a property class 8.8 bolt is limited by its proof",
        "The preload of a property class ", "8.8 bolt is limited", " by its", " proof load (",
        "approximately 85% of yield",
        "The preload of a property class 8.8 bolt is limited by its proof load (approximately",
        " 85%", " of yield strength),",
        "The preload of a property class 8.8 bolt is limited by its proof load (approximately 85",
        "% of yield strength), beyond which permanent plastic deformation occurs.",
    ]
    assert _replay(chunks) == full


def test_dedupe_passes_clean_deltas_through():
    chunks = ["Use", " an", " M10", " bolt.", " The", " torque", " is", " 48 N·m."]
    assert _replay(chunks) == "Use an M10 bolt. The torque is 48 N·m."


def test_dedupe_handles_restart_inside_a_replay():
    full = "Alpha beta gamma delta epsilon."
    chunks = ["Alpha beta", " gamma delta", "Alpha be", "Alpha beta gamma", " delta epsilon."]
    assert _replay(chunks) == full


def test_final_text_replaces_glitched_stream(monkeypatch):
    monkeypatch.delenv("MECH_DEMO_MODE", raising=False)
    monkeypatch.setattr(copilot, "provider", lambda: "replicate")
    monkeypatch.setattr(copilot, "llm_complete", lambda *a, **k: json.dumps({"title": "t", "tools": []}))

    def glitchy(*a, **k):
        s = copilot.TextStream()
        s._gen = iter(["Clean answer", " with a glitchglitch."])
        s.final = "Clean answer with a glitch."
        return s

    monkeypatch.setattr(copilot, "llm_stream", glitchy)
    events = _events(respond("hi", [], "efficient"))
    assert any(e["type"] == "replace_content" for e in events)
    assert events[-1]["content"] == "Clean answer with a glitch."


def test_model_routing_uses_stronger_model_for_review(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_test")
    monkeypatch.delenv("MECH_DEMO_MODE", raising=False)
    for k in ("REPLICATE_MODEL", "REPLICATE_MODEL_REVIEW", "REPLICATE_MODEL_DEEP"):
        monkeypatch.delenv(k, raising=False)
    assert copilot.model_for("efficient", "plan") == copilot.DEFAULT_MODEL
    assert copilot.model_for("efficient", "review") == copilot.DEFAULT_REVIEW_MODEL
    assert copilot.model_for("deep", "plan") == copilot.model_for("deep", "review") == copilot.DEFAULT_DEEP_MODEL


def test_catalog_marks_conditional_params():
    text = copilot.catalog_prompt()
    assert "(only if material=custom)" in text


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


# --- load defaults and clarifying questions -----------------------------------

def _output(result, label_start):
    return next(o for o in result["outputs"] if o["label"].startswith(label_start))


def test_unset_loads_are_zero_once_the_plan_sets_one():
    """A beam planned with only a UDL must not keep the calculator's demo point load.
    IPE 200 (22.4 kg/m), 4 m, 12 kN/m: M = (12 + 0.22) * 4^2 / 8 = 24.4 kN·m, δ ≈ 10 mm."""
    tools, _ = normalise_tools({"tools": [{"calculator": "beam_analysis", "inputs": {
        "L": 4, "support": "simply_supported", "w1": 12, "profile": "IPE 200"}}]})
    assert tools[0]["inputs"]["P1"]["value"] == 0
    r = copilot.run_tools(tools)[0]["result"]
    assert float(_output(r, "Max bending moment")["display"]) == pytest.approx(24.4, rel=0.01)
    assert float(_output(r, "Max deflection")["display"]) == pytest.approx(10.0, rel=0.03)


def test_demo_loads_kept_when_plan_sets_no_load():
    tools, _ = normalise_tools({"tools": [{"calculator": "beam_analysis", "inputs": {"L": 4}}]})
    assert "P1" not in tools[0]["inputs"]


def test_missing_key_inputs_ask_instead_of_computing(monkeypatch):
    monkeypatch.delenv("MECH_DEMO_MODE", raising=False)
    monkeypatch.setattr(copilot, "provider", lambda: "replicate")
    plan = {"title": "Bearing selection", "tools": [], "clarify": {
        "message": "I'll size a bearing for your shaft.",
        "questions": [{"id": "Fr", "label": "Radial load", "unit": "kN", "placeholder": "3.5"},
                      {"id": "type", "label": "Bearing type", "unit": "x", "options": ["Ball", "Roller"]},
                      {"label": ""}]}}
    monkeypatch.setattr(copilot, "llm_complete", lambda *a, **k: json.dumps(plan))

    def no_review(*a, **k):
        raise AssertionError("must not write an answer before the user replies")

    monkeypatch.setattr(copilot, "llm_stream", no_review)
    events = _events(respond("I need a bearing for my shaft", [], "efficient"))
    asked = next(e for e in events if e["type"] == "clarify")
    assert [q["label"] for q in asked["questions"]] == ["Radial load", "Bearing type"]
    assert asked["questions"][1]["unit"] == ""          # choices carry no unit
    final = events[-1]
    assert final["tool_data"]["clarify"]["questions"] and final["tool_data"]["tools"] == []
    assert "[asked the user: Radial load; Bearing type]" in copilot._history_text(
        [{"role": "assistant", "content": final["content"], "tool_data": final["tool_data"]}])


def test_results_for_review_stays_valid_json():
    import json
    from copilot import results_for_review
    big = [{"calculator": f"c{i}", "outputs": {"x": "1 mm"}, "tables": ["t" * 3000]} for i in range(30)]
    lean = json.loads(results_for_review(big, limit=4000))          # detail dropped first
    assert len(lean) == 30 and all("tables" not in s for s in lean)
    many = [{"calculator": f"c{i}", "outputs": {f"o{k}": "1 mm" for k in range(20)}} for i in range(30)]
    text = results_for_review(many, limit=4000)                      # then whole results, said so
    assert len(text) <= 4000 and "omitted" in json.loads(text)[-1]


def test_ungrounded_numbers_flags_only_invented_values():
    from copilot import ungrounded_numbers
    summary = [{"calculator": "bolt", "outputs": {"Preload": "29.6 kN"}}]
    answer = "**Use M10 8.8.** Preload 29.6 kN, tightening torque 48.5 N·m."
    assert ungrounded_numbers(answer, "M10 bolt, 8.8", [], summary, [], []) == ["48.5"]
