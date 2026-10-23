"""
MechCopilot copilot: plan -> compute -> review.

  1. PLAN    The model reads the calculator catalog and the conversation and
             returns JSON: which calculators to run, with which inputs, and the
             assumptions it made.
  2. COMPUTE Every chosen calculator runs server-side through the engineering
             kernel (never model arithmetic).
  3. REVIEW  The model gets the computed numbers and writes the answer like a
             senior design engineer: recommendation first, assumptions, verdict,
             concrete parts, next checks. Streamed to the client.

Providers: Replicate (default; Claude via REPLICATE_API_TOKEN), OpenAI
(OPENAI_API_KEY), or an offline deterministic fallback when neither is set.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

import pint

from engineering.core import CalcError, UNIT_CHOICES, run_calculator, to_canonical, ureg
from engineering.registry import CATALOG, ordered


def extract_balanced_json(text: str, start: int) -> Optional[str]:
    """The JSON object starting at text[start] == '{', matched by brace depth (string-aware)."""
    if start >= len(text) or text[start] != "{":
        return None
    depth, in_str, i = 0, False, start
    while i < len(text):
        ch = text[i]
        if in_str and ch == "\\":
            i += 2
            continue
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        i += 1
    return None


def try_parse_json(text: str) -> Optional[Any]:
    """Parse model JSON, tolerating stray backslashes (LaTeX) and control characters."""
    for candidate in (text, re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)):
        try:
            return json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            continue
    return None

# Planning is structured selection: a small fast model does it well. Reviewing results is
# engineering judgement: a stronger model writes the answer and runs the follow-up round.
DEFAULT_MODEL = "anthropic/claude-4.5-haiku"          # plan (Fast)
DEFAULT_REVIEW_MODEL = "anthropic/claude-sonnet-4.6"  # follow-up + answer (Fast)
DEFAULT_DEEP_MODEL = "anthropic/claude-sonnet-5"      # every step in Deep review
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_DEEP_MODEL = "gpt-4o"


class LLMError(RuntimeError):
    """Provider failure with a user-facing message."""


# --------------------------------------------------------------------------
# Provider selection
# --------------------------------------------------------------------------

def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def provider() -> str:
    """'replicate' | 'openai' | 'offline'."""
    if _env("MECH_DEMO_MODE") == "1":
        return "offline"
    if _env("REPLICATE_API_TOKEN"):
        return "replicate"
    if _env("OPENAI_API_KEY"):
        return "openai"
    return "offline"


def model_for(tier: str, role: str = "plan") -> str:
    """Model for a tier ("efficient" | "deep") and role ("plan" | "review")."""
    deep = tier == "deep"
    p = provider()
    if p == "replicate":
        if deep:
            return _env("REPLICATE_MODEL_DEEP") or DEFAULT_DEEP_MODEL
        if role == "review":
            return _env("REPLICATE_MODEL_REVIEW") or DEFAULT_REVIEW_MODEL
        return _env("REPLICATE_MODEL") or DEFAULT_MODEL
    if p == "openai":
        return _env("OPENAI_MODEL_DEEP" if deep else "OPENAI_MODEL") or (
            OPENAI_DEEP_MODEL if deep else OPENAI_MODEL)
    return "offline"


_KEY_CHECK: Dict[str, Any] = {"token": None, "ok": None, "at": 0.0}


def _replicate_key_valid() -> Optional[bool]:
    """True/False if Replicate accepted/rejected the token, None if unknown (offline etc.).
    Cached for 5 minutes so the UI can poll cheaply."""
    import time
    token = _env("REPLICATE_API_TOKEN")
    now = time.time()
    if _KEY_CHECK["token"] == token and now - _KEY_CHECK["at"] < 300:
        return _KEY_CHECK["ok"]
    ok: Optional[bool]
    try:
        import httpx
        r = httpx.get("https://api.replicate.com/v1/account",
                      headers={"Authorization": f"Bearer {token}"}, timeout=5)
        ok = True if r.status_code == 200 else (False if r.status_code in (401, 403) else None)
    except Exception:
        ok = None
    _KEY_CHECK.update(token=token, ok=ok, at=now)
    return ok


def status() -> Dict[str, Any]:
    p = provider()
    return {
        "provider": p,
        "model": model_for("efficient", "review"),
        "plan_model": model_for("efficient", "plan"),
        "deep_model": model_for("deep"),
        "calculators": len(CATALOG),
        "configured": p != "offline",
        "key_valid": _replicate_key_valid() if p == "replicate" else None,
    }


def _replicate_error(e: Exception) -> LLMError:
    msg = str(e)
    if "401" in msg or "authentication" in msg.lower() or "Unauthenticated" in msg:
        return LLMError("Replicate rejected the API token. Check REPLICATE_API_TOKEN in backend/.env "
                        "(tokens start with r8_) and restart the backend.")
    if "402" in msg or "billing" in msg.lower() or "credit" in msg.lower():
        return LLMError("Replicate refused the request for billing reasons — add credit or a payment "
                        "method on replicate.com.")
    if "404" in msg:
        return LLMError("Replicate model not found. Check REPLICATE_MODEL / REPLICATE_MODEL_REVIEW in backend/.env.")
    return LLMError(f"Replicate request failed: {msg[:240]}")


def _transient(e: Exception) -> bool:
    msg = f"{type(e).__name__} {e}".lower()
    return any(k in msg for k in ("timed out", "timeout", "connection", "502", "503", "504", "temporarily"))


def _replicate_client():
    import httpx
    import replicate
    # Generous read timeout: a cold model can sit in the queue before the first token.
    return replicate.Client(api_token=_env("REPLICATE_API_TOKEN"),
                            timeout=httpx.Timeout(180.0, connect=20.0))


def _payload(system: str, prompt: str, max_tokens: int) -> Dict[str, Any]:
    return {"prompt": prompt, "system_prompt": system, "max_tokens": max(int(max_tokens), 1024)}


def _joined(output: Any) -> str:
    if isinstance(output, list):
        return "".join(str(o) for o in output)
    return "" if output is None else str(output)


class TextStream:
    """Iterable of text chunks; `final` holds the provider's authoritative full text
    once iteration ends (None if the provider has no separate final output)."""

    def __init__(self) -> None:
        self.final: Optional[str] = None
        self._gen: Iterator[str] = iter(())

    def __iter__(self) -> Iterator[str]:
        return self._gen


def dedupe_chunk(state: Dict[str, str], chunk: str) -> str:
    """Return only the genuinely new text in `chunk`.

    Replicate's streams for some models are not purely incremental: they periodically
    re-send the answer from the beginning (in pieces), mixed with normal deltas. Joined
    naively the user sees sentences repeated several times. `state` keeps what has been
    shown ("out") and the text of the current (possibly replayed) segment ("seg")."""
    out, seg = state["out"], state["seg"]
    continuing_replay = len(seg) < len(out) and out.startswith(seg + chunk)
    if not continuing_replay and len(chunk) >= 3 and out.startswith(chunk):
        state["seg"] = chunk                      # a replay from the start begins
        return ""
    new_seg = seg + chunk
    if out.startswith(new_seg):                   # still replaying text already shown
        state["seg"] = new_seg
        return ""
    if new_seg.startswith(out):                   # extends past what was shown
        state["out"] = state["seg"] = new_seg
        return new_seg[len(out):]
    state["out"] = out + chunk                    # unexpected: treat as a plain delta
    state["seg"] = state["out"]
    return chunk


def _replicate_stream(system: str, prompt: str, tier: str, max_tokens: int, role: str,
                      holder: TextStream) -> Iterator[str]:
    client = _replicate_client()
    model = model_for(tier, role)
    for attempt in range(2):
        produced = False
        try:
            pred = client.predictions.create(model=model, input=_payload(system, prompt, max_tokens),
                                             stream=True)
            state = {"out": "", "seg": ""}
            for event in pred.stream():
                text = dedupe_chunk(state, str(event)) if str(event) else ""
                if text:
                    produced = True
                    yield text
            pred.reload()
            if pred.status == "failed":
                raise LLMError(f"The model failed: {str(pred.error)[:200]}")
            holder.final = _joined(pred.output) or state["out"]
            return
        except LLMError:
            raise
        except Exception as e:  # replicate raises several exception types
            # Retry once on a transient failure, but never after streaming has started.
            if attempt == 0 and not produced and _transient(e):
                continue
            raise _replicate_error(e) from e


def _replicate_complete(system: str, prompt: str, tier: str, max_tokens: int, role: str) -> str:
    """Non-streaming call: the prediction's final output is always clean."""
    client = _replicate_client()
    for attempt in range(2):
        try:
            pred = client.predictions.create(model=model_for(tier, role),
                                             input=_payload(system, prompt, max_tokens))
            pred.wait()
            if pred.status != "succeeded":
                raise LLMError(f"The model {pred.status}: {str(pred.error)[:200]}")
            return _joined(pred.output)
        except LLMError:
            raise
        except Exception as e:
            if attempt == 0 and _transient(e):
                continue
            raise _replicate_error(e) from e
    raise LLMError("Replicate request failed after a retry.")


def _openai_stream(system: str, prompt: str, tier: str, max_tokens: int) -> Iterator[str]:
    from openai import OpenAI
    try:
        client = OpenAI(api_key=_env("OPENAI_API_KEY"))
        stream = client.chat.completions.create(
            model=model_for(tier), stream=True, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except Exception as e:
        raise LLMError(f"OpenAI request failed: {str(e)[:240]}") from e


def llm_stream(system: str, prompt: str, tier: str = "efficient", max_tokens: int = 2048,
               role: str = "review") -> TextStream:
    p = provider()
    stream = TextStream()
    if p == "replicate":
        stream._gen = _replicate_stream(system, prompt, tier, max_tokens, role, stream)
    elif p == "openai":
        stream._gen = _openai_stream(system, prompt, tier, max_tokens)
    else:
        raise LLMError("No language model configured.")
    return stream


def llm_complete(system: str, prompt: str, tier: str = "efficient", max_tokens: int = 1536,
                 role: str = "plan") -> str:
    p = provider()
    if p == "replicate":
        return _replicate_complete(system, prompt, tier, max_tokens, role)
    if p == "openai":
        return "".join(_openai_stream(system, prompt, tier, max_tokens))
    raise LLMError("No language model configured.")


# --------------------------------------------------------------------------
# Catalog prompt
# --------------------------------------------------------------------------

def catalog_prompt() -> str:
    """Compact catalog: one block per calculator with param names, units, defaults and
    the conditions under which a param is used (so a preset select does not silently
    override a number the model also sets)."""
    lines: List[str] = []
    category = None
    for c in ordered():
        if c.category != category:
            category = c.category
            lines.append(f"\n## {category}")
        s = c.llm_summary()
        by_name = {p.name: p for p in c.params}
        params = []
        for p in s["params"]:
            if "unit" in p:
                txt = f"{p['name']}[{p['unit']}]={p['default']}"
            elif "options" in p:
                opts = p["options"]
                shown = "|".join(str(o) for o in opts[:12]) + ("|…" if len(opts) > 12 else "")
                txt = f"{p['name']}<{shown}>={p['default']}"
            else:
                txt = f"{p['name']}({p.get('kind')})={p['default']}"
            cond = by_name[p["name"]].show_if
            if cond:
                txt += " (only if " + " & ".join(f"{k}={'|'.join(map(str, v))}" for k, v in cond.items()) + ")"
            params.append(txt)
        lines.append(f"- {c.id}: {c.title} — {c.summary}\n  params: {', '.join(params)}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------

PERSONA = """You are MechCopilot, a senior mechanical design engineer (20+ years: machine design, \
drivetrains, structures, fasteners, bearings). You are rigorous, practical and concise. You think \
in load paths, failure modes and safety factors, you know the standards (ISO, DIN/EN, VDI 2230, \
ISO 281, Shigley, Roark) and you always recommend concrete, standard, buyable parts."""

PLAN_SYSTEM = PERSONA + """

STEP: PLAN. Decide which engineering calculators to run for the user's latest message. You have a \
catalog of validated calculators (below). The server runs them; you never do arithmetic yourself.

Reply with ONE JSON object and nothing else:
{
  "title": "3-6 word session title",
  "intent": "sizing | check | selection | explain | lookup | general",
  "tools": [
    {"calculator": "<id from catalog>", "inputs": {"<param>": <value>}, "purpose": "<why, one line>"}
  ],
  "assumptions": ["<each engineering assumption you made, with the value>"],
  "missing": ["<critical information the user did not give, if any>"],
  "clarify": null
}

ASK FIRST when the user describes a task or names a part but leaves out a value that drives the \
result and has no safe default: the loads (force, torque, power, pressure), the speed of a rotating \
part, the span or length, the required life, or the size/space available when that sets the answer. \
Then return "tools": [] and
  "clarify": {"message": "<1-2 sentences: what you understood and what you will check>",
              "questions": [{"id": "<short_key>", "label": "<what to enter>", "unit": "<unit or empty>",
                             "options": ["<choice>", ...] or [], "placeholder": "<typical value>"}]}
- 2-5 questions, most important first, ONE value per question (radial and axial load are two questions).
- Use "options" for categorical answers (load type, bearing type, material, joint type) and leave \
"unit" empty for those. Options are short plain-language labels an engineer reads at a glance \
("Continuous 24 h", "Ball or roller, any"), never catalog codes like "8h_partial" or "dgbb".
- Labels are plain words without symbols ("Radial load", not "Radial load (Fr)").
- Never ask for what has a sound engineering default (friction, safety factor, reliability, lubrication, \
standard material grade): assume it and list it in "assumptions" later.
- Never ask again when the user already answered your questions, gave the values, or says to use \
typical values / assume / go ahead: run the calculators with sensible defaults instead.
- Explanation, comparison and lookup questions never need clarify.

Rules:
- Use only calculator ids and param names that appear in the catalog.
- Use the FEWEST calculators that answer the question: usually 1, at most 3. Selector calculators \
answer "which / choose / find" questions and already report torque, life, preload etc. — do not \
add a second calculator that repeats them. Shaft fatigue already applies notch factors; do not add \
a separate stress-concentration run unless the user asks about the notch itself.
- Never guess a part size, designation or geometry for one calculator that depends on another \
calculator's result in the same plan. A follow-up step can verify the chosen part afterwards.
- Concept explanations: pick the one calculator whose diagram and worked solution show the concept.
- Numbers are in the unit shown in brackets, e.g. "F": 12 means 12 in the listed unit. To use \
another unit write {"value": 12, "unit": "kN"} (pint unit strings: mm, m, N, kN, MPa, GPa, N*m, rpm...).
- Select params take one of the listed option values exactly.
- A param marked "(only if X=Y)" is ignored unless X=Y. When the user gives a number that a preset \
select would otherwise override (e.g. a required life vs an application class), set that select to \
its custom option so the user's number is used.
- Loads you do not set are zero once you set any load of a calculator (e.g. a beam with only "w1" \
carries no point load), so set every load the user describes.
- Fill everything the user gave, exactly as given. For anything missing choose a sensible \
engineering default (load factor, friction, safety factor, reliability, lubrication) and list it in \
"assumptions" with its value. Do NOT restate material or catalogue properties (strengths, masses, \
ratings) in assumptions — the library supplies them; just name the material you picked.
- Follow-ups ("make it 10.9", "what if the load doubles") re-run the earlier calculator with the change.
- General or comparison questions about standard parts and materials (e.g. "8.8 vs 10.9", "ball vs \
roller bearing") still run a lookup or calculator for a representative case (e.g. fastener_lookup for \
each class, bearing_life for each type) so the answer quotes library values, not memory.
- Pure conversation with nothing to look up or calculate: "tools": [].

CALCULATOR CATALOG
"""

FOLLOWUP_INSTRUCTION = """

STEP: FOLLOW-UP. The first calculations are done (results below). If a check failed, a selector \
found nothing, or the chosen part should be verified in detail, you may run up to 2 MORE \
calculators to reach a design that passes — e.g. another bearing type or a heavier series, a \
smaller interference fit, the next standard shaft size, the selected bolt checked in the bolted-joint \
calculator. Use the parts and numbers the results produced. Reply with ONE JSON object:
{"tools": [ {"calculator": "<id>", "inputs": {...}, "purpose": "<why>"} ], "reason": "<one line>"}
Reply {"tools": []} if more calculations would not change the recommendation."""

ANSWER_SYSTEM = PERSONA + """

STEP: REVIEW. The calculators have been run by the engineering kernel. Write the reply to the user.

FORMAT (strict)
- First line: the answer in **bold**, with the 1-3 decisive numbers. If a part or design failed a \
check and a computed alternative passes, recommend the passing one. Never present a part whose \
check failed as the recommendation without saying plainly that it fails.
- Then 2-4 bullets: why — the governing checks with their numbers and pass/warn/fail.
- Then a line "Assumptions to confirm:" with 1-3 bullets — only those that would change the answer.
- Then a line "Next:" with 1-2 bullets — a specific check, or which input to adjust in the cards.
- No headings, tables or horizontal rules: the calculator cards below the reply show every detail, \
the diagram and the worked solution. Refer to them instead of repeating values.
- At most {word_limit} words.
- Explanation questions: 3-6 sentences of theory with the key formula(s) in LaTeX ($...$), then \
point to the diagram and worked solution in the card. Theory needs no extra numbers.

GROUNDING (most important)
- Every number with a unit that you write must appear in COMPUTED RESULTS, in the TOOL INPUTS or in \
the user's message. Do not estimate, scale or extrapolate new numbers ("if friction drops to 0.10 \
the preload becomes …" is forbidden). Describe sensitivity in words and name the input to change.
- Use part designations and links exactly as the results give them. Cite only standards you are \
sure of (e.g. ISO 273 clearance holes, ISO 898-1, EN 1993-1-8). Never invent brands, products \
or catalogue values. Never state a price or price range, not even "typically": say where to get a quote.
- If no calculator ran, answer qualitatively from engineering knowledge and name the calculator \
that would quantify it. Quote a number only if it is a standard value you are certain of.
- Getting the direction of an effect wrong is worse than saying nothing: e.g. interference-fit \
stresses depend on the interference, not on press vs shrink assembly.
- If a calculator errored or information is missing, say exactly what is needed.
Voice: an experienced engineer talking to a colleague — direct, no filler, no restating the question."""

WORD_LIMIT = {"efficient": 170, "deep": 320}

# Which way to move when a check fails — given to the follow-up step for the calculators
# that actually ran, so it changes the right input in the right direction.
DESIGN_HINTS: Dict[str, str] = {
    "interference_fit": "Hub/shaft stress fails while torque has margin → LOOSER fit (e.g. H7/r6, H7/p6) "
                        "or larger hub OD; torque fails → tighter fit, longer hub or higher friction. "
                        "Press vs shrink assembly does not change the stresses.",
    "iso_fits": "Choose the fit class that gives the needed interference/clearance range.",
    "bearing_selector": "Nothing found → FIRST re-run the selector at the same bore with btype 'any' "
                        "(roller bearings carry far more radial load), so the answer can name a bearing "
                        "that passes; then consider a larger bore. The modified life Lnm (basis Lnmh) can "
                        "exceed the basic L10h.",
    "bearing_life": "Life short → heavier series, roller bearing, cleaner lubrication (raises aISO) or larger bore.",
    "bearing_required_c": "Use the required C to pick the smallest bearing per series that meets it.",
    "shaft_fatigue": "Fatigue fails → next standard diameter up, larger fillet radius (lower Kf), better "
                     "surface finish or stronger material; first-cycle yield fails → larger diameter.",
    "round_bar_combined": "Fails → larger diameter or stronger material.",
    "fastener_selector": "To verify the chosen bolt for cyclic load or soft plates, run bolted_joint with "
                         "that exact size and class.",
    "bolted_joint": "Separation or fatigue fails → larger size or higher class, more preload (better "
                    "tightening method), longer clamp length; surface pressure fails → washer or flange head.",
    "bolt_preload_torque": "Utilisation too high → lower utilisation or better friction control; preload "
                           "too low → larger size or higher class.",
    "thread_engagement": "Too short → deeper tapped hole, thread insert or lower bolt class.",
    "bolt_shear_joint": "Slip or shear fails → more or larger bolts, higher class, more shear planes.",
    "bolt_group_eccentric": "Critical bolt fails → larger pattern spacing, more bolts or larger size.",
    "beam_analysis": "Stress or deflection fails → next standard profile up (beam_profile_selector gives "
                     "the lightest that passes), stronger axis, shorter span or an extra support.",
    "beam_profile_selector": "Use the lightest passing profile per family.",
    "column_buckling": "Buckling fails → larger second moment of area, shorter effective length (better "
                       "end fixity or bracing).",
    "compression_spring": "Stress too high → thicker wire or stronger material; buckling → guide it or "
                          "reduce free length / mean diameter ratio.",
    "torsion_spring": "Stress too high → thicker wire or more coils.",
    "fillet_weld": "Weld stress fails → larger leg size, longer weld or a pattern with larger section modulus.",
    "spur_gear": "Bending fails → larger module or face width; contact fails → larger pinion, wider face "
                 "or harder material.",
    "parallel_key": "Crushing or shear fails → longer key, second key at 180° or an interference fit.",
    "pressure_vessel": "Stress fails → thicker wall or stronger material.",
    "fatigue_life": "Fatigue fails → lower alternating stress (larger section), lower Kf or better surface.",
}


def _profile_line(profile: Optional[Dict[str, Any]]) -> str:
    if not profile:
        return ""
    stage = profile.get("careerStage") or "general"
    area = profile.get("focusArea") or "general"
    depth = {
        "student": "Explain the reasoning and first principles briefly; define terms.",
        "junior": "Explain the key reasoning and point out common pitfalls.",
        "mid": "Focus on trade-offs and manufacturability.",
        "senior": "Be terse; focus on risks, governing checks and margins.",
    }.get(stage, "")
    return f"\nUser: {stage} engineer, focus area {area}. {depth}"


def _history_text(history: List[Dict[str, Any]], limit: int = 12) -> str:
    out = []
    for m in history[-limit:]:
        role = "User" if m["role"] == "user" else "MechCopilot"
        content = (m.get("content") or "").strip()
        td = m.get("tool_data") if isinstance(m.get("tool_data"), dict) else {}
        tools = td.get("tools")
        asked = (td.get("clarify") or {}).get("questions") or []
        if asked:
            content += "\n[asked the user: " + "; ".join(q["label"] for q in asked) + "]"
        if tools:
            used = "; ".join(f"{t.get('calculator')}({json.dumps(t.get('inputs', {}))[:300]})"
                             for t in tools if t.get("type") == "calc")
            if used:
                content += f"\n[calculators shown: {used}]"
        if len(content) > 2500:
            content = content[:2500] + " …"
        out.append(f"{role}: {content}")
    return "\n\n".join(out)


# --------------------------------------------------------------------------
# Plan parsing + input validation
# --------------------------------------------------------------------------

_NUM_UNIT = re.compile(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([^\d\s].*)?$")


def _clean_inputs(calc_id: str, raw: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Keep only valid params; normalise values into the frontend/backend input format."""
    calc = CATALOG[calc_id]
    params = {p.name: p for p in calc.params}
    cleaned: Dict[str, Any] = {}
    dropped: List[str] = []
    for name, val in (raw or {}).items():
        p = params.get(name)
        if p is None:
            dropped.append(name)
            continue
        try:
            if p.kind == "number":
                default_unit = p.to_dict()["unit"]
                if isinstance(val, dict) and "value" in val:
                    num, unit = float(val["value"]), val.get("unit") or default_unit
                elif isinstance(val, (int, float)) and not isinstance(val, bool):
                    num, unit = float(val), default_unit
                elif isinstance(val, str):
                    m = _NUM_UNIT.match(val.replace(",", "."))
                    if not m:
                        raise ValueError(val)
                    num, unit = float(m.group(1)), (m.group(2) or default_unit).strip()
                else:
                    raise ValueError(val)
                if p.dim != "dimensionless":
                    to_canonical(num, unit, p.dim)          # validates the unit
                    choices = [c["value"] for c in UNIT_CHOICES[p.dim]]
                    if unit not in choices:                 # express in the param's own unit
                        num = ureg.Quantity(num, unit).to(default_unit).magnitude
                        unit = default_unit
                cleaned[name] = {"value": round(num, 10), "unit": unit}
            elif p.kind == "select":
                opts = p.options or []
                hit = next((o["value"] for o in opts if str(o["value"]).lower() == str(val).lower()), None)
                if hit is None:
                    hit = next((o["value"] for o in opts if str(o["label"]).lower() == str(val).lower()), None)
                if hit is None:
                    raise ValueError(val)
                cleaned[name] = hit
            elif p.kind == "bool":
                cleaned[name] = val in (True, "true", "True", 1, "yes")
            else:
                cleaned[name] = str(val)
        except (ValueError, TypeError, pint.errors.PintError):
            dropped.append(name)
    return cleaned, dropped


def clean_clarify(plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The plan's questions for the user, validated; None when it did not ask."""
    raw = plan.get("clarify")
    if not isinstance(raw, dict):
        return None
    questions = []
    for i, q in enumerate(raw.get("questions") or []):
        if not isinstance(q, dict) or not str(q.get("label") or "").strip():
            continue
        options = [str(o)[:60] for o in (q.get("options") or []) if str(o).strip()][:8]
        questions.append({
            "id": re.sub(r"\W+", "_", str(q.get("id") or f"q{i}"))[:32],
            "label": str(q["label"]).strip()[:80],
            "unit": "" if options else str(q.get("unit") or "").strip()[:16],
            "options": options,
            "placeholder": re.sub(r"^(e\.g\.|eg|for example)[,:]?\s*", "",
                                  str(q.get("placeholder") or "").strip(), flags=re.I)[:40],
        })
    if not questions:
        return None
    message = str(raw.get("message") or "").strip() or "A few details first, so the numbers fit your case:"
    return {"message": message[:600], "questions": questions[:5]}


def parse_plan(text: str) -> Optional[Dict[str, Any]]:
    start = text.find("{")
    while start != -1:
        raw = extract_balanced_json(text, start)
        if raw:
            data = try_parse_json(raw)
            if isinstance(data, dict) and "tools" in data:
                return data
        start = text.find("{", start + 1)
    return None


# Loads that act together. Their defaults are demo values (a 10 kN point load AND 5 kN/m on
# a beam); once the plan sets any of them, the ones it left out must be zero, not the demo.
LOAD_SETS: Dict[str, Tuple[str, ...]] = {
    "beam_analysis": ("P1", "P2", "P3", "w1", "w1_end", "w2", "M1"),
    "beam_profile_selector": ("w", "P"),
    "shaft_fatigue": ("Ma", "Mm", "Ta", "Tm"),
    "round_bar_combined": ("F", "M", "T"),
    "bearing_selector": ("Fr", "Fa"),
    "bearing_life": ("Fr", "Fa"),
    "fastener_selector": ("FA", "FQ"),
    "bolted_joint": ("FA_max", "FA_min"),
    "bolt_group_eccentric": ("F", "Fx"),
    "fillet_weld": ("V", "N"),
    "pressure_vessel": ("p_i", "p_o"),
    "fatigue_life": ("sa", "sm"),
}


def _zero_unset_loads(calc_id: str, inputs: Dict[str, Any]) -> None:
    names = LOAD_SETS.get(calc_id, ())
    if not any(n in inputs for n in names):
        return                                  # nothing set: keep the demo case intact
    params = {p.name: p for p in CATALOG[calc_id].params}
    for n in names:
        if n not in inputs:
            inputs[n] = {"value": 0.0, "unit": params[n].to_dict()["unit"]}


def normalise_tools(plan: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Validate the model's tool list against the catalog."""
    tools, notes = [], []
    seen = set()
    for t in (plan.get("tools") or [])[:4]:
        cid = str(t.get("calculator") or t.get("id") or "").strip()
        if cid not in CATALOG:
            notes.append(f"Skipped unknown calculator '{cid}'.")
            continue
        inputs, dropped = _clean_inputs(cid, t.get("inputs") or {})
        _zero_unset_loads(cid, inputs)
        key = (cid, json.dumps(inputs, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        if dropped:
            notes.append(f"{CATALOG[cid].title}: ignored unrecognised inputs {', '.join(dropped)}.")
        tools.append({"type": "calc", "calculator": cid, "title": CATALOG[cid].title,
                      "inputs": inputs, "purpose": str(t.get("purpose") or "")[:200]})
    return tools, notes


# --------------------------------------------------------------------------
# Compute + summarise
# --------------------------------------------------------------------------

def run_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for t in tools:
        calc = CATALOG[t["calculator"]]
        try:
            r = run_calculator(calc, t["inputs"])
            results.append({"calculator": calc.id, "title": calc.title, "ok": True, "result": r})
        except CalcError as e:
            results.append({"calculator": calc.id, "title": calc.title, "ok": False, "error": str(e)})
        except Exception as e:  # keep the conversation alive; report the failure
            results.append({"calculator": calc.id, "title": calc.title, "ok": False,
                            "error": f"{type(e).__name__}: {e}"})
    return results


def _inputs_display(tool: Dict[str, Any]) -> Dict[str, str]:
    """The inputs the planner set, keyed by human label ("Axial load": "9 kN")."""
    calc = CATALOG[tool["calculator"]]
    by_name = {p.name: p for p in calc.params}
    out = {}
    for name, val in tool.get("inputs", {}).items():
        p = by_name.get(name)
        if p is None:
            continue
        if isinstance(val, dict) and "value" in val:
            unit = next((c["label"] for c in UNIT_CHOICES.get(p.dim, []) if c["value"] == val.get("unit")),
                        val.get("unit") or "")
            shown = f"{val['value']:g} {unit}".strip() if unit != "–" else f"{val['value']:g}"
        elif p.kind == "select":
            shown = next((str(o["label"]) for o in (p.options or []) if o["value"] == val), str(val))
        else:
            shown = str(val)
        out[p.label] = shown
    return out


def summarise(results: List[Dict[str, Any]],
              tools: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Compact, model-friendly digest of each run (also stored for reports).
    Includes the inputs each run used, so the review never has to guess them."""
    out = []
    for i, r in enumerate(results):
        tool = tools[i] if tools and i < len(tools) else None
        inputs = _inputs_display(tool) if tool else {}
        if not r["ok"]:
            out.append({"calculator": r["calculator"], "title": r["title"], "inputs": inputs,
                        "error": r["error"]})
            continue
        res = r["result"]
        s: Dict[str, Any] = {
            "calculator": r["calculator"], "title": r["title"], "verdict": res["verdict"],
            "inputs": inputs, "other_inputs": "calculator defaults",
            "outputs": {o["label"]: f"{o['display']} {o['unit_label']}".strip() for o in res["outputs"]},
            "checks": [f"[{c['status']}] {c['label']}: {c['message']}" for c in res["checks"]],
        }
        if res.get("notes"):
            s["notes"] = res["notes"][:4]
        if res.get("links"):
            s["links"] = [f"{l['label']}: {l['url']}" for l in res["links"][:3]]
        for tbl in res.get("tables", [])[:1]:
            cols = [c["key"] for c in tbl["columns"]][:8]
            rows = [{k: row.get(k) for k in cols} for row in tbl["rows"][:6]]
            s["table"] = {"title": tbl["title"], "rows": rows}
        out.append(s)
    return out


# --------------------------------------------------------------------------
# Offline fallback (no model configured or provider failure)
# --------------------------------------------------------------------------

_OFFLINE_RULES: List[Tuple[Tuple[str, ...], str]] = [
    (("which bolt", "select bolt", "choose bolt", "bolt size", "fastener size", "what bolt"), "fastener_selector"),
    (("bolted joint", "clamp", "separation", "flange joint", "joint diagram"), "bolted_joint"),
    (("slip", "shear joint", "lap joint", "friction grip"), "bolt_shear_joint"),
    (("engagement", "stripping", "tapped", "thread strip"), "thread_engagement"),
    (("bolt pattern", "bolt group", "eccentric"), "bolt_group_eccentric"),
    (("dimension", "clearance hole", "tap drill", "head size"), "fastener_lookup"),
    (("preload", "tightening", "torque spec", "tighten", "bolt", "screw", "fastener"), "bolt_preload_torque"),
    (("which bearing", "select a bearing", "select bearing", "choose bearing", "find a bearing", "find bearing", "bearing selector"), "bearing_selector"),
    (("required c", "dynamic load rating"), "bearing_required_c"),
    (("bearing",), "bearing_life"),
    (("profile", "ipe", "hea", "heb", "i-beam", "which beam"), "beam_profile_selector"),
    (("section propert", "moment of inertia", "section modulus", "second moment"), "section_properties"),
    (("beam", "span", "cantilever", "simply supported", "deflection", "girder", "joist"), "beam_analysis"),
    (("critical speed", "whirl"), "shaft_critical_speed"),
    (("combined", "von mises", "bending and torsion"), "round_bar_combined"),
    (("shaft",), "shaft_fatigue"),
    (("keyway", "key "), "parallel_key"),
    (("press fit", "shrink", "interference"), "interference_fit"),
    (("fit", "tolerance", "h7", "g6", "iso 286"), "iso_fits"),
    (("gear", "pinion", "module"), "spur_gear"),
    (("spring",), "compression_spring"),
    (("weld",), "fillet_weld"),
    (("column", "buckling", "strut"), "column_buckling"),
    (("pressure vessel", "tank", "pipe", "cylinder pressure", "hoop"), "pressure_vessel"),
    (("stress concentration", "kt", "notch"), "stress_concentration"),
    (("fatigue", "s-n", "endurance", "goodman"), "fatigue_life"),
]


def offline_plan(message: str) -> Dict[str, Any]:
    q = f" {message.lower()} "
    tools = []
    for words, cid in _OFFLINE_RULES:
        if cid in CATALOG and any(w in q for w in words):
            tools.append({"calculator": cid, "inputs": {}, "purpose": "Matched from your question."})
            break
    return {"title": message.strip()[:48], "intent": "check", "tools": tools,
            "assumptions": ["Calculator opened with its default inputs — adjust them to your case."]
            if tools else [], "missing": []}


def offline_answer(summary: List[Dict[str, Any]], configured: bool) -> str:
    if not summary:
        text = ("I can run sizing and checks for fasteners, bearings, beams, shafts, fits, gears, springs, "
                "welds, columns, pressure vessels and fatigue. Describe the part and its loads, or open the "
                "**Calculator Library** in the sidebar.")
    else:
        parts = []
        for s in summary:
            if "error" in s:
                parts.append(f"**{s['title']}** could not run with these inputs: {s['error']}")
                continue
            verdict = {"ok": "passes all checks", "warn": "passes with warnings",
                       "fail": "fails at least one check", "none": "computed"}[s["verdict"]]
            lines = [f"**{s['title']}** — {verdict} with the inputs below."]
            for label, val in list(s["outputs"].items())[:4]:
                lines.append(f"- {label}: **{val}**")
            for c in s["checks"][:3]:
                c = c.replace("[ok] ", "✓ ").replace("[warn] ", "⚠ ").replace("[fail] ", "✗ ")
                lines.append(f"- {c}")
            parts.append("\n".join(lines))
        text = "\n\n".join(parts) + "\n\nAdjust the inputs in the card below; it recalculates live."
    if not configured:
        text += ("\n\n> Offline mode: answers are templated. Add a Replicate API token to "
                 "`backend/.env` to get the full engineering copilot.")
    return text


# --------------------------------------------------------------------------
# Orchestration (yields SSE-ready event dicts)
# --------------------------------------------------------------------------

def respond(message: str, history: List[Dict[str, Any]], tier: str = "efficient",
            profile: Optional[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
    """Yield events: status, notice, plan, tool, token, final."""
    configured = provider() != "offline"
    notices: List[str] = []
    plan: Optional[Dict[str, Any]] = None

    if configured:
        yield {"type": "status", "content": "Planning the analysis…"}
        prompt = (f"Conversation so far:\n{_history_text(history)}\n\n"
                  f"Latest user message:\n{message}\n{_profile_line(profile)}\n\nReturn the JSON plan.")
        try:
            raw = llm_complete(PLAN_SYSTEM + catalog_prompt(), prompt, tier, max_tokens=1536, role="plan")
            plan = parse_plan(raw)
            if plan is None:
                notices.append("The model's plan could not be parsed; used keyword matching instead.")
        except LLMError as e:
            notices.append(str(e))
            configured = False
    if plan is None:
        plan = offline_plan(message)

    tools, tool_notes = normalise_tools(plan)
    notices.extend(tool_notes)
    for n in notices:
        yield {"type": "notice", "level": "warn", "content": n}

    # Key inputs missing: ask before computing anything (the UI shows the questions as a form).
    clarify = clean_clarify(plan) if configured and not tools else None
    if clarify:
        yield {"type": "plan", "assumptions": [], "missing": [], "title": plan.get("title")}
        yield {"type": "clarify", **clarify}
        yield {"type": "token", "content": clarify["message"]}
        yield {"type": "final", "content": clarify["message"], "title": plan.get("title"),
               "tool_data": {"tools": [], "results": [], "assumptions": [], "missing": [],
                             "notices": notices, "clarify": clarify}}
        return

    yield {"type": "plan", "assumptions": plan.get("assumptions") or [],
           "missing": plan.get("missing") or [], "title": plan.get("title")}
    if tools:
        yield {"type": "status", "content": "Running calculations…"}
    results = run_tools(tools)
    summary = summarise(results, tools)
    for t in tools:
        yield {"type": "tool", "data": t}

    # Follow-up round: let the model chase a passing design when something failed,
    # or (deep review) verify a selected part in a detail calculator.
    failed = any(s.get("verdict") == "fail" or "error" in s for s in summary)
    has_selector = any("selector" in t["calculator"] or t["calculator"].endswith("_required_c")
                       for t in tools)
    if configured and tools and (failed or (tier == "deep" and has_selector)):
        yield {"type": "status", "content": "Exploring alternatives…" if failed else "Verifying the selection…"}
        hints = "\n".join(f"- {cid}: {DESIGN_HINTS[cid]}"
                          for cid in dict.fromkeys(t["calculator"] for t in tools) if cid in DESIGN_HINTS)
        prompt = (f"Latest user message:\n{message}\n\n"
                  f"Calculators already run and their results:\n{json.dumps(summary, ensure_ascii=False)[:9000]}\n\n"
                  + (f"Design guidance for these calculators:\n{hints}\n\n" if hints else "")
                  + "Return the follow-up JSON.")
        try:
            raw = llm_complete(PLAN_SYSTEM + catalog_prompt() + FOLLOWUP_INSTRUCTION, prompt, tier,
                               max_tokens=1024, role="review")
            follow = parse_plan(raw) or {"tools": []}
            done = {(t["calculator"], json.dumps(t["inputs"], sort_keys=True)) for t in tools}
            extra, extra_notes = normalise_tools({"tools": (follow.get("tools") or [])[:2]})
            extra = [t for t in extra
                     if (t["calculator"], json.dumps(t["inputs"], sort_keys=True)) not in done][:max(0, 5 - len(tools))]
            if extra:
                extra_results = run_tools(extra)
                tools += extra
                results += extra_results
                summary = summarise(results, tools)
                for t in extra:
                    yield {"type": "tool", "data": t}
            notices.extend(extra_notes)
        except LLMError as e:
            notices.append(f"Follow-up skipped: {e}")

    answer = ""
    if configured:
        yield {"type": "status", "content": "Reviewing results…"}
        prompt = (f"Conversation so far:\n{_history_text(history)}\n\n"
                  f"Latest user message:\n{message}\n{_profile_line(profile)}\n\n"
                  f"Assumptions made when planning: {json.dumps(plan.get('assumptions') or [], ensure_ascii=False)}\n"
                  f"Missing information: {json.dumps(plan.get('missing') or [], ensure_ascii=False)}\n\n"
                  f"COMPUTED RESULTS with TOOL INPUTS (authoritative):\n"
                  f"{json.dumps(summary, indent=1, ensure_ascii=False)[:14000]}\n\n"
                  "Write your reply.")
        system = ANSWER_SYSTEM.replace("{word_limit}", str(WORD_LIMIT.get(tier, 170)))
        try:
            stream = llm_stream(system, prompt, tier, max_tokens=2048 if tier == "deep" else 1200,
                                role="review")
            for chunk in stream:
                answer += chunk
                yield {"type": "token", "content": chunk}
            # The provider's final text is authoritative; if live de-duplication missed a
            # stream glitch, swap the shown text for it.
            final_text = getattr(stream, "final", None)
            if final_text and final_text.strip() and final_text.strip() != answer.strip():
                answer = final_text
                yield {"type": "replace_content", "content": answer}
        except LLMError as e:
            yield {"type": "notice", "level": "warn", "content": str(e)}
            notices.append(str(e))
            configured = False
    if not answer:
        answer = offline_answer(summary, configured=provider() != "offline")
        yield {"type": "token", "content": answer}

    yield {"type": "final", "content": answer.strip(), "title": plan.get("title"),
           "tool_data": {"tools": tools, "results": summary,
                         "assumptions": plan.get("assumptions") or [],
                         "missing": plan.get("missing") or [], "notices": notices}}
