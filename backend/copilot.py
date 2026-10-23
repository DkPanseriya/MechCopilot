"""
MechPartner copilot: plan -> compute -> review.

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
from llm_utils import extract_balanced_json, try_parse_json

DEFAULT_MODEL = "anthropic/claude-4.5-haiku"
DEFAULT_DEEP_MODEL = "anthropic/claude-sonnet-4.6"
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


def model_for(tier: str) -> str:
    deep = tier == "deep"
    p = provider()
    if p == "replicate":
        return _env("REPLICATE_MODEL_DEEP" if deep else "REPLICATE_MODEL") or (
            DEFAULT_DEEP_MODEL if deep else DEFAULT_MODEL)
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
        "model": model_for("efficient"),
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
        return LLMError(f"Replicate model not found. Check REPLICATE_MODEL ({model_for('efficient')}).")
    return LLMError(f"Replicate request failed: {msg[:240]}")


def _replicate_stream(system: str, prompt: str, tier: str, max_tokens: int) -> Iterator[str]:
    import replicate
    client = replicate.Client(api_token=_env("REPLICATE_API_TOKEN"))
    model = model_for(tier)
    try:
        for event in client.stream(model, input={
            "prompt": prompt,
            "system_prompt": system,
            "max_tokens": max(int(max_tokens), 1024),
        }):
            text = str(event)
            if text:
                yield text
    except Exception as e:  # replicate raises several exception types
        raise _replicate_error(e) from e


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


def llm_stream(system: str, prompt: str, tier: str = "efficient", max_tokens: int = 2048) -> Iterator[str]:
    p = provider()
    if p == "replicate":
        yield from _replicate_stream(system, prompt, tier, max_tokens)
    elif p == "openai":
        yield from _openai_stream(system, prompt, tier, max_tokens)
    else:
        raise LLMError("No language model configured.")


def llm_complete(system: str, prompt: str, tier: str = "efficient", max_tokens: int = 1536) -> str:
    return "".join(llm_stream(system, prompt, tier, max_tokens))


# --------------------------------------------------------------------------
# Catalog prompt
# --------------------------------------------------------------------------

def catalog_prompt() -> str:
    """Compact catalog: one block per calculator with param names, units and defaults."""
    lines: List[str] = []
    category = None
    for c in ordered():
        if c.category != category:
            category = c.category
            lines.append(f"\n## {category}")
        s = c.llm_summary()
        params = []
        for p in s["params"]:
            if "unit" in p:
                params.append(f"{p['name']}[{p['unit']}]={p['default']}")
            elif "options" in p:
                opts = p["options"]
                shown = "|".join(str(o) for o in opts[:12]) + ("|…" if len(opts) > 12 else "")
                params.append(f"{p['name']}<{shown}>={p['default']}")
            else:
                params.append(f"{p['name']}({p.get('kind')})={p['default']}")
        lines.append(f"- {c.id}: {c.title} — {c.summary}\n  params: {', '.join(params)}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------

PERSONA = """You are MechPartner, a senior mechanical design engineer (20+ years: machine design, \
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
  "missing": ["<critical information the user did not give, if any>"]
}

Rules:
- Use only calculator ids and param names that appear in the catalog. Pick 1-3 calculators that \
answer the question; use selector calculators for "which / choose / find" questions; for concept \
explanations pick the calculator whose diagram and worked solution explain it.
- Numbers are in the unit shown in brackets, e.g. "F": 12 means 12 in the listed unit. To use \
another unit write {"value": 12, "unit": "kN"} (pint unit strings: mm, m, N, kN, MPa, GPa, N*m, rpm...).
- Select params take one of the listed option values exactly.
- Fill everything the user gave. For anything missing choose a sensible engineering default \
(typical material, safety factor, friction, life class) and list it in "assumptions".
- Follow-ups ("make it 10.9", "what if the load doubles") re-run the earlier calculator with the change.
- Pure conversation or advice with nothing to calculate: "tools": [].

CALCULATOR CATALOG
"""

ANSWER_SYSTEM = PERSONA + """

STEP: REVIEW. The calculators you chose have been run by the engineering kernel. Write your reply \
to the user based ONLY on those computed results.

How to write it:
1. Lead with the direct answer or recommendation and the decisive numbers with units.
2. Name concrete standard parts when relevant (e.g. "M10×35 ISO 4762 class 10.9, tighten to 51 N·m", \
"SKF 6206-2RSH", "IPE 200, S355"). Prefer the designation and link the results provide.
3. Verdict: say which checks pass, warn or fail and what governs the design.
4. State the assumptions that matter and how sensitive the answer is to them.
5. Finish with 1-3 specific next checks (fatigue, buckling, deflection, fits...).

Style: an experienced engineer talking to a colleague. Short paragraphs and bullets, markdown, \
no filler, no restating the question. Use LaTeX ($...$) only for a key formula. Never invent \
numbers that are not in the results; if a calculator errored or information is missing, say \
exactly what you need. The interactive calculators appear below your message — point to them \
("adjust the clamp length in the bolted-joint card") rather than repeating every value."""


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
        role = "User" if m["role"] == "user" else "MechPartner"
        content = (m.get("content") or "").strip()
        tools = (m.get("tool_data") or {}).get("tools") if isinstance(m.get("tool_data"), dict) else None
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


def summarise(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compact, model-friendly digest of each run (also stored for reports)."""
    out = []
    for r in results:
        if not r["ok"]:
            out.append({"calculator": r["calculator"], "title": r["title"], "error": r["error"]})
            continue
        res = r["result"]
        s: Dict[str, Any] = {
            "calculator": r["calculator"], "title": r["title"], "verdict": res["verdict"],
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
            lines = [f"**{s['title']}** — {verdict} with the default inputs below."]
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
            raw = llm_complete(PLAN_SYSTEM + catalog_prompt(), prompt, tier, max_tokens=1536)
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

    yield {"type": "plan", "assumptions": plan.get("assumptions") or [],
           "missing": plan.get("missing") or [], "title": plan.get("title")}

    if tools:
        yield {"type": "status", "content": "Running calculations…"}
    results = run_tools(tools)
    summary = summarise(results)
    for t in tools:
        yield {"type": "tool", "data": t}

    answer = ""
    if configured:
        yield {"type": "status", "content": "Reviewing results…"}
        prompt = (f"Conversation so far:\n{_history_text(history)}\n\n"
                  f"Latest user message:\n{message}\n{_profile_line(profile)}\n\n"
                  f"Assumptions you made: {json.dumps(plan.get('assumptions') or [])}\n"
                  f"Missing information: {json.dumps(plan.get('missing') or [])}\n\n"
                  f"COMPUTED RESULTS (authoritative):\n{json.dumps(summary, indent=1)[:12000]}\n\n"
                  "Write your reply.")
        try:
            for chunk in llm_stream(ANSWER_SYSTEM, prompt, tier, max_tokens=4096 if tier == "deep" else 2048):
                answer += chunk
                yield {"type": "token", "content": chunk}
        except LLMError as e:
            yield {"type": "notice", "level": "warn", "content": str(e)}
            notices.append(str(e))
            configured = False
    if not answer:
        answer = offline_answer(summary, configured=provider() != "offline")
        yield {"type": "token", "content": answer}

    yield {"type": "final", "content": answer, "title": plan.get("title"),
           "tool_data": {"tools": tools, "results": summary,
                         "assumptions": plan.get("assumptions") or [],
                         "missing": plan.get("missing") or [], "notices": notices}}
