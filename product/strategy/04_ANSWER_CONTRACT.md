# 04 — Answer contract v2: what a MechCopilot answer looks like

**Owner:** Technical Director · **Date:** 2026-10-24 · **Replaces:** the single format in
`ANSWER_SYSTEM` (`backend/copilot.py`)

Today every answer has the same skeleton (bold line, 2–4 bullets, assumptions, next, ≤170 words).
A torque lookup and a design review should not look alike. This contract defines the answer by
**intent** and **user level**, and makes trust elements mandatory and machine-checkable.

---

## 1. Principles

1. **Length follows the decision, not the data.** The cards hold the detail. The text holds the
   judgement.
2. **Verdict first, always.** The first line answers the question asked, with the deciding number.
3. **Nothing hidden.** Assumed and default inputs are visible every time (rendered as UI, not
   prose, see §4).
4. **Say what was not checked.** Absence of a failure is not a pass.
5. **No invented numbers.** Every number with a unit traces to a result, an input or the user.
   Enforced by a post-check, not only by the prompt (see §5).
6. **The demo is never the design.** Calculator defaults appear only when labelled "example".
7. **One next action.** The most valuable next check, not a menu.

---

## 2. Answer types

The planner already emits `intent`. Extend it to these seven types; the review prompt and the
grader pick the template by type.

### A. Lookup — "Torque for M12 10.9, oiled?"
- **Shape:** 1–2 lines. Value(s) + conditions + standard.
- **Limit:** 50 words.
- **Example** (numbers from `bolt_preload_torque`): **M12 10.9, oiled, μ = 0.12: tighten to
  123 N·m for 63.3 kN max preload (VDI 2230, 90 % yield utilisation).** With a torque wrench
  (αA = 1.7) expect at least 37.2 kN.

### B. Check — "Is an IPE 200 OK for 12 kN/m over 4 m?"
- **Shape:** verdict line with governing margin · 2–3 bullets (governing check, other checks
  with status) · **Not checked:** one line · **Confirm:** only assumptions that flip the verdict ·
  **Next:** one action.
- **Limit:** 130 words (Fast), 220 (Deep).

### C. Sizing / selection — "Which bearing for a 30 mm shaft, 3.5 kN, 1450 rpm, 25 000 h?"
- **Shape:** recommendation with designation and decisive number · runner-up in one line ·
  why (2 bullets) · **Not checked** · **Next**.
- **Limit:** 150 words (Fast), 250 (Deep).
- Alternatives the user did not ask for appear only if the asked-for option fails.

### D. Explain — "How do bending and torsion combine on a shaft?"
- **Shape:** depends on level (§3). Formula in LaTeX. If a calculator ran to show the concept,
  its numbers are presented as **"Example (default values):"**, never as the user's design.
- **Limit:** 120 words (senior) to 250 words (student/junior).

### E. Compare / trade-off — "8.8 vs 10.9?", "Aluminium or steel bracket?"
- **Shape:** one-line recommendation by use case · compact table (≤ 5 rows × 4 columns) of
  computed values · one line on when to pick the other.
- **Limit:** 150 words plus table. **Tables are allowed here only.**

### F. Troubleshoot / root cause — "Bolts are loosening after 200 h."
- **Shape:** likely causes ranked with one-line reason · the discriminating check for each ·
  computed check(s) for the top cause · fix options with margins.
- **Limit:** 220 words.

### G. Review — "Review this bracket design." (Deep tier)
- **Shape:** summary verdict · findings grouped **Critical / Major / Minor**, each with the
  supporting calculation or the missing one · coverage summary · next actions.
- **Limit:** 450 words, sections collapsible in the UI.

### H. Clarify — key input missing
- Unchanged from today (form with 2–5 questions), plus: say what will be checked once answered.

---

## 3. User level modulation

The level comes from onboarding and can be overridden per message ("explain", "terse").

| Element | Student | Junior | Mid | Senior |
|---|---|---|---|---|
| Verdict line | ✓ | ✓ | ✓ | ✓ |
| Why bullets | 3, with the physics | 3, with pitfalls | 2–3, trade-offs | 1–2, governing only |
| Formula in text | Yes | Key one | On request | No (card has it) |
| "What a senior checks next" | Yes | Yes | No | No |
| Definitions of terms | Yes | First use only | No | No |
| Length vs type limit | 100 % | 100 % | 85 % | 60 % |

---

## 4. Mandatory trust elements (structured, rendered by the UI)

These are emitted as structured data in `tool_data`, not left to the model's prose.

| Element | Content | Rendered as |
|---|---|---|
| **Input provenance** | Each input of each calculator run: value, unit, source = `user` / `project` / `assumed` / `default` / `derived` (from another calc) | Chips above the card; `default` and `assumed` highlighted and editable |
| **Load case** | Name and factor applied | Badge on each result |
| **Verdict and margin** | ok / warn / fail + governing margin (SF, MS or utilisation %) | Badge with number |
| **Not checked** | Failure modes relevant to the component that no calculator covered | One line, linked to the check plan |
| **Standards** | Standard and clause per calculator | In the card footer |
| **Confidence** | `verified` (all governing inputs from user/project) / `provisional` (an assumption drives the verdict) / `example` (defaults) | Small label next to verdict |

Rule: if any **governing** input (load, speed, span, life, pressure) has source `default`, the
answer must be type H (clarify) or labelled `example`. Never a verdict.

---

## 5. Enforcement (in code, not just in the prompt)

1. **Grounding post-check:** after the review stream ends, extract numbers with units from the
   answer; any not found in results, inputs or the user message triggers one rewrite pass with
   the offending sentences flagged. If still ungrounded, strip the sentence and add a notice.
   (Reuse the extraction in `evals/grader.py`.)
2. **Length post-check:** over 140 % of the type limit → one shortening pass.
3. **No emoji, no headings** except in type G.
4. **Eval suite** (`backend/evals/cases.py`) gets at least 3 cases per answer type and per
   level, with `answer_type` in `expect`; grader checks shape per type.

---

## 6. Voice

Experienced engineer to a colleague. Direct, specific, no filler, no praise, no restating the
question. Numbers with units, designations exact. Uncertainty is stated as a missing input, not as
hedging words. Never a price. Never a brand or catalogue value not in the results.
