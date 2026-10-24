"""The eval grader itself (offline): number extraction, grounding and case checks."""
from evals.cases import CASES
from evals.grader import grade, grounding, numbers


def _final(answer, results=None, tools=None):
    return {"content": answer, "tool_data": {"results": results or [], "tools": tools or [],
                                             "assumptions": []}}


def test_numbers_skip_standard_names_and_read_thousands():
    found = [raw for _, raw in numbers("Per ISO 4017 and EN 1993-1-8, life 25,000 h at 36.4 N·m on M8")]
    assert found == ["25,000", "36.4"]


def test_grounding_accepts_rounding_and_prefix_rescaling():
    src = "Tightening torque 36.37 N·m; residual clamp 420 N; life 399724 h"
    g = grounding("**36.4 N·m**, clamp 0.42 kN, life ≈ 400,000 h", src)
    assert g["ungrounded"] == [] and g["score"] == 1.0


def test_grounding_flags_invented_numbers_but_not_small_counts():
    g = grounding("Use 4 bolts at 52.5 N·m", "Tightening torque 36.4 N·m")
    assert g["ungrounded"] == ["52.5"]


def test_grade_checks_calculator_values_and_format():
    case = {"id": "x", "question": "beam 4 m", "expect": {
        "calculators_any": ["beam_analysis"], "answer_values": [(9.8, 0.05)]}}
    results = [{"calculator": "beam_analysis", "verdict": "ok", "outputs": {"Max deflection": "9.79 mm"}}]
    good = grade(case, _final("**Deflection 9.79 mm — passes.**", results,
                              [{"calculator": "beam_analysis", "inputs": {}}]), 170)
    assert good["passed"], good
    bad = grade(case, _final("Deflection is 12 mm.", results, [{"calculator": "section_properties"}]), 170)
    failed = {k for k, v in bad["checks"].items() if not v}
    assert {"picked calculator", "quotes ≈9.8", "numbers grounded", "bold first line"} <= failed


def test_cases_are_well_formed():
    from copilot import CATALOG
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))
    for c in CASES:
        for cid in c.get("expect", {}).get("calculators_any", []):
            assert cid in CATALOG, (c["id"], cid)


def test_grade_flags_silent_defaults_and_missing_terms():
    case = {"id": "x", "question": "explain", "expect": {"must_mention_all": ["example"], "format": False}}
    silent = [{"calculator": "round_bar_combined", "inputs": {}, "missing": ["F", "M", "T"]}]
    bad = grade(case, _final("Bending and torsion combine as von Mises.", tools=silent), 170)
    assert bad["checks"]["no silent defaults"] is False and bad["checks"]["mentions “example”"] is False
    labelled = [{**silent[0], "example": True}]
    good = grade(case, _final("Example with the default values: von Mises.", tools=labelled), 170)
    assert good["checks"]["no silent defaults"] and "mentions “example”" not in good["checks"]
