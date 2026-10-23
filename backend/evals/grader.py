"""Deterministic grading of one copilot answer.

Checks what can be checked without a second model:
- grounding: every number in the answer must trace back to the computed results,
  the tool inputs, the plan or the user's question (rounding allowed);
- the right calculators ran, and ran without errors;
- the answer quotes the expected key values and avoids forbidden claims;
- length and the house format (bold first line).
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

# Standard names carry numbers that are not engineering values ("ISO 4017", "EN 1993-1-8").
_STANDARD = re.compile(r"\b(?:ISO|DIN|EN|VDI|ASME|AISC|AWS|ASTM|SAE|ANSI|BS|JIS|IEC|AGMA|DNV)\s*[\d\-.:/]+",
                       re.IGNORECASE)
_LATEX = re.compile(r"\$\$.*?\$\$|\$[^$\n]+\$", re.DOTALL)
_NUMBER = re.compile(r"(?<![\w.])[-−]?(?:\d{1,3}(?:[,  ]\d{3})+|\d+)(?:\.\d+)?(?:e[-+]?\d+)?",
                     re.IGNORECASE)
SMALL_INT = 10   # bare integers up to this are counts, list items, "2 bolts": not graded


def numbers(text: str) -> List[Tuple[float, str]]:
    """(value, as written) for every number in `text`, ignoring standard names."""
    text = _STANDARD.sub(" ", text)
    out = []
    for m in _NUMBER.finditer(text):
        raw = m.group(0)
        try:
            out.append((float(re.sub(r"[,  ]", "", raw).replace("−", "-")), raw))
        except ValueError:
            continue
    return out


def _tolerance(raw: str, value: float) -> float:
    decimals = len(raw.split(".")[1]) if "." in raw and "e" not in raw.lower() else 0
    return max(abs(value) * 0.01, 0.5 * 10 ** -decimals)


def grounded(value: float, raw: str, sources: List[float]) -> bool:
    """True if `value` matches a source number, allowing rounding, a sign flip
    and SI prefix rescaling (420 N quoted as 0.42 kN)."""
    tol = _tolerance(raw, value)
    for scale in (1.0, 1e3, 1e-3, 1e6, 1e-6):
        v = abs(value) * scale
        t = tol * scale
        if any(abs(v - abs(s)) <= max(t, abs(s) * 0.01) for s in sources):
            return True
    return False


_ANY_DIGITS = re.compile(r"\d+(?:\.\d+)?")


def grounding(answer: str, sources_text: str) -> Dict[str, Any]:
    # Sources also count digits inside names: "S355J2" grounds a quoted yield of 355 MPa.
    sources = [v for v, _ in numbers(sources_text)] + [float(d) for d in _ANY_DIGITS.findall(sources_text)]
    graded, missing = 0, []
    for value, raw in numbers(_LATEX.sub(" ", answer)):
        if "." not in raw and abs(value) <= SMALL_INT:
            continue
        graded += 1
        if not grounded(value, raw, sources):
            missing.append(raw)
    return {"graded": graded, "ungrounded": missing,
            "score": 1.0 if graded == 0 else round(1 - len(missing) / graded, 3)}


def sources_text(question: str, final: Dict[str, Any]) -> str:
    td = final.get("tool_data") or {}
    return "\n".join([question, json.dumps(td.get("results", []), ensure_ascii=False),
                      json.dumps(td.get("tools", []), ensure_ascii=False),
                      json.dumps(td.get("assumptions", []), ensure_ascii=False)])


def _contains_value(answer: str, target: float, rel: float) -> bool:
    return any(abs(v - target) <= abs(target) * rel for v, _ in numbers(answer))


def grade(case: Dict[str, Any], final: Dict[str, Any], word_limit: int) -> Dict[str, Any]:
    """Score one case. Returns per-check pass/fail plus details; `passed` is all checks."""
    answer: str = final.get("content", "")
    td = final.get("tool_data") or {}
    ran = [t["calculator"] for t in td.get("tools", [])]
    results = td.get("results", [])
    expect = case.get("expect", {})
    checks: Dict[str, Optional[bool]] = {}
    notes: List[str] = []

    if "calculators_any" in expect:
        want = expect["calculators_any"]
        checks["picked calculator"] = any(c in ran for c in want) if want else not ran
        if not checks["picked calculator"]:
            notes.append(f"ran {ran or 'nothing'}, wanted one of {want or 'none'}")

    asked = bool(td.get("clarify"))
    checks["asks only when needed"] = asked == bool(expect.get("asks"))
    if not checks["asks only when needed"]:
        notes.append("asked for details on a complete question" if asked else "did not ask for missing details")

    errors = [r for r in results if "error" in r]
    checks["no calculator errors"] = not errors
    for r in errors:
        notes.append(f"{r['calculator']} error: {r['error'][:120]}")

    if expect.get("finds_passing_design"):
        key = set(expect.get("calculators_any") or ran)
        checks["found passing design"] = any(r.get("verdict") in ("ok", "warn")
                                             for r in results if r["calculator"] in key)

    for target, rel in expect.get("answer_values", []):
        targets = target if isinstance(target, (list, tuple)) else [target]
        label = " or ".join(f"{t:g}" for t in targets)
        checks[f"quotes ≈{label}"] = any(_contains_value(answer, t, rel) for t in targets)
        if not checks[f"quotes ≈{label}"]:
            notes.append(f"expected ≈{label} (±{rel:.0%}) in the answer")

    low = answer.lower()
    if expect.get("must_mention_any"):
        checks["mentions key term"] = any(p.lower() in low for p in expect["must_mention_any"])
        if not checks["mentions key term"]:
            notes.append(f"mentions none of {expect['must_mention_any']}")
    for phrase in expect.get("must_not_mention", []):
        if phrase.lower() in low:
            checks[f"avoids “{phrase}”"] = False
            notes.append(f"answer contains forbidden “{phrase}”")

    g = grounding(answer, sources_text(case["question"], final))
    checks["numbers grounded"] = g["score"] >= expect.get("min_grounding", 0.9)
    if g["ungrounded"]:
        notes.append(f"ungrounded numbers: {', '.join(g['ungrounded'][:8])}")

    words = len(answer.split())
    checks["length"] = words <= word_limit * 1.4
    checks["bold first line"] = answer.lstrip().startswith("**") if expect.get("format", True) else None

    graded = {k: v for k, v in checks.items() if v is not None}
    return {"id": case["id"], "passed": all(graded.values()), "checks": graded, "notes": notes,
            "grounding": g, "words": words, "calculators": ran}
