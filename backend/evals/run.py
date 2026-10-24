"""Run the answer-quality evaluation against the live model.

    cd backend
    ../.venv/Scripts/python -m evals.run                 # all cases, Fast tier
    ../.venv/Scripts/python -m evals.run --judge         # + model judge for contradictions
    ../.venv/Scripts/python -m evals.run beam_ipe200 column_euler --tier deep

Needs REPLICATE_API_TOKEN in backend/.env. Each case costs roughly 3-5 US cents
(Fast), plus about 1 cent with --judge. Reports go to backend/evals/reports/.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
load_dotenv(os.path.join(BACKEND, ".env"))

import copilot  # noqa: E402
from evals.cases import CASES  # noqa: E402
from evals.grader import grade  # noqa: E402

PROFILE = {"careerStage": "mid", "focusArea": "general"}

JUDGE_SYSTEM = """You audit answers written by an engineering assistant. You get the user's question,
the calculator results the assistant was given, and its answer. Report only real problems:
- contradictions: the answer states something the results contradict (a failing check called OK,
  a wrong value, a wrong direction such as "increase" where the results need "decrease");
- unsafe: advice that could lead to an unsafe design;
- unsupported: technical claims that are neither in the results nor standard engineering knowledge.
Return JSON only: {"contradictions": [..], "unsafe": [..], "unsupported": [..],
"usefulness": 1-5, "comment": "one sentence"}"""


def judge(case: Dict[str, Any], final: Dict[str, Any], tier: str) -> Dict[str, Any]:
    prompt = (f"Question:\n{case['question']}\n\nResults given to the assistant:\n"
              f"{json.dumps(final['tool_data']['results'], ensure_ascii=False)[:9000]}\n\n"
              f"Answer:\n{final['content']}")
    raw = copilot.llm_complete(JUDGE_SYSTEM, prompt, tier, max_tokens=1024, role="review")
    block = copilot.extract_balanced_json(raw, raw.find("{")) if "{" in raw else None
    return (block and copilot.try_parse_json(block)) or {"comment": f"unparsed: {raw[:200]}"}


def run_case(case: Dict[str, Any], tier: str, use_judge: bool) -> Dict[str, Any]:
    t0 = time.time()
    try:
        events = list(copilot.respond(case["question"], case.get("history", []), tier, PROFILE))
    except Exception as e:  # report and keep going
        return {"id": case["id"], "passed": False, "checks": {"ran": False},
                "notes": [f"{type(e).__name__}: {e}"], "seconds": round(time.time() - t0, 1)}
    final = events[-1]
    result = grade(case, final, copilot.WORD_LIMIT.get(tier, 170))
    result["seconds"] = round(time.time() - t0, 1)
    result["notices"] = final["tool_data"].get("notices", [])
    result["answer"] = final["content"]
    if final["tool_data"].get("degraded"):  # the offline fallback answered: nothing was evaluated
        result["checks"]["model answered"] = False
        result["passed"] = False
    if use_judge:
        try:
            verdict = judge(case, final, tier)
        except copilot.LLMError as e:
            verdict = {"comment": f"judge failed: {e}"}
        result["judge"] = verdict
        if verdict.get("contradictions") or verdict.get("unsafe"):
            result["checks"]["judge: no contradictions"] = False
            result["passed"] = False
    return result


def report(results, tier: str) -> str:
    passed = sum(r["passed"] for r in results)
    graded = [r for r in results if "grounding" in r]
    ground = sum(r["grounding"]["score"] for r in graded) / max(1, len(graded))
    lines = [f"# Copilot eval — {time.strftime('%Y-%m-%d %H:%M')} — tier {tier}",
             f"Models: plan `{copilot.model_for(tier, 'plan')}`, answer `{copilot.model_for(tier, 'review')}`",
             "", f"**{passed}/{len(results)} cases pass** · mean grounding {ground:.0%} · "
             f"median time {sorted(r['seconds'] for r in results)[len(results) // 2]} s", ""]
    for r in results:
        failed = [k for k, v in r["checks"].items() if not v]
        lines.append(f"## {'PASS' if r['passed'] else 'FAIL'} {r['id']} ({r['seconds']} s)")
        lines.append(f"calculators: {r.get('calculators')}; failed checks: {failed or 'none'}")
        lines += [f"- {n}" for n in r.get("notes", []) + r.get("notices", [])]
        if r.get("judge"):
            lines.append(f"- judge: {json.dumps(r['judge'], ensure_ascii=False)}")
        if r.get("answer"):
            lines += ["", "> " + r["answer"].replace("\n", "\n> ")]
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate copilot answers on reference questions.")
    ap.add_argument("ids", nargs="*", help="case ids to run (default: all)")
    ap.add_argument("--tier", default="efficient", choices=["efficient", "deep"])
    ap.add_argument("--judge", action="store_true", help="also ask a model to look for contradictions")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    if copilot.provider() == "offline":
        print("No model configured: set REPLICATE_API_TOKEN in backend/.env.")
        return 2
    cases = [c for c in CASES if not args.ids or c["id"] in args.ids]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda c: run_case(c, args.tier, args.judge), cases))

    for r in results:
        failed = [k for k, v in r["checks"].items() if not v]
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['id']:<22} {r['seconds']:>5}s  {', '.join(failed)}")
    print(f"\n{sum(r['passed'] for r in results)}/{len(results)} pass")

    out_dir = os.path.join(HERE, "reports")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, time.strftime("%Y%m%d-%H%M%S") + f"-{args.tier}")
    with open(stem + ".md", "w", encoding="utf-8") as f:
        f.write(report(results, args.tier))
    with open(stem + ".json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"report: {stem}.md")
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
