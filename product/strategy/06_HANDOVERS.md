# 06 — Handovers: Phase 1 work packages

**From:** Technical Director · **Date:** 2026-10-24 · **To:** whoever picks up the work (engineer
or coding agent)

Each handover can be started from this page alone. Read `02_CURRENT_STATE_AND_GAPS.md` for the
evidence and `04_ANSWER_CONTRACT.md` for the answer rules. Do them in order: H1 and H3 first,
because every other package is measured by the eval suite and depends on provenance.

General rules for every package:
- The model never does arithmetic. Do not add any path where a number in an answer comes from
  the model.
- Every behaviour change gets a test (`backend/tests/`) and, where it touches answers, an eval
  case (`backend/evals/cases.py`).
- `python -m pytest backend/tests -q` and `cd frontend && npx tsc --noEmit` must pass.
- One package = one branch = one PR.

---

## H1 — Input provenance and no silent defaults (F1)

**Why:** the copilot gave 13 mm instead of 9.8 mm (IPE 200) and 77.9 mm instead of ≈ 16 mm
(cantilever) because inputs the planner did not set silently took demo defaults. The kernel is
correct; the plumbing is not.

**Scope**
1. `backend/engineering/core.py`: add `governing: bool = False` to `Param`. Mark governing params
   in every calculator (loads, speeds, spans/lengths, required life, pressure, geometry that sets
   the answer). Registry test: every calculator has ≥ 1 governing param.
2. Dependent defaults: allow a param default to be a function of other inputs
   (e.g. `beam_analysis.x1` → `L` for cantilever, `L/2` otherwise). Fixes the "point load outside
   the beam" error on short cantilevers.
3. `backend/copilot.py`:
   - Planner JSON: each input becomes `{"value", "unit", "source": "user"|"assumed", "why"?}`.
     Keep accepting the old shape (treat as `assumed`).
   - `normalise_tools` adds every unset param with `source: "default"` (zeroed loads from
     `LOAD_SETS` become `source: "derived"` with reason "load not described").
   - If a governing param is `default` and the intent is not `explain`: return a clarify event
     for those params instead of computing. For `explain`, mark the run `example: true`.
   - `summarise` passes provenance to the review prompt; `ANSWER_SYSTEM` says: never present
     `example` runs as the user's design.
4. `tool_data.tools[i].inputs` stores provenance; `services/reporting.py` prints it.
5. Frontend: `CalculatorView` shows provenance chips (user / project / assumed / default) next to
   inputs in compact mode; default and assumed are highlighted.

**Accept**
- Live evals `beam_ipe200` (9.8 mm ± 5 %) and `cantilever_imperial` (0.644 in / 16.4 mm ± 5 %)
  pass. `concept` answer contains "example" and no claim about the user's shaft.
- Unit test: a plan that omits a governing load yields a clarify event, not a computed verdict.
- Old sessions without provenance still load.

**Not in scope:** project-level values (`source: project`) arrive with F7; keep the enum ready.

---

## H2 — Answer contract v2 and grounding enforcement (F2)

**Why:** answers exceed limits, contain extrapolated numbers ("μ ≈ 0.09 → 104 kN") and use one
template for every question.

**Scope**
1. Planner `intent` enum → `lookup | check | sizing | explain | compare | troubleshoot | review |
   general`.
2. Split `ANSWER_SYSTEM` into a shared persona/grounding block plus one template per type, with
   word limits and level modulation from `04_ANSWER_CONTRACT.md` §2–3.
   `_profile_line` becomes a level table, not one sentence.
3. Structured trust elements in `tool_data`: per run `verdict`, `governing_margin`
   (label + value), `load_case` (placeholder until F8), `not_checked: []`, `confidence`
   (`verified | provisional | example`). `not_checked` starts from a static map per calculator
   (e.g. `beam_analysis` → lateral-torsional buckling, connection design) until check plans (F9)
   replace it.
4. Post-checks after the stream completes (`respond`):
   - Grounding: reuse `evals/grader.py::numbers` / `grounded`; ungrounded numbers → one rewrite
     call with the sentences flagged; still ungrounded → remove sentence, add notice.
   - Length > 140 % of the type limit → one shortening call.
   - Strip emoji.
   Send the corrected text with the existing `replace_content` event.
5. Frontend: render verdict badge with margin, confidence label and the "Not checked" line from
   structured data, not from prose.

**Accept**
- Live Fast eval ≥ 85 % pass on the H3 suite; grounding ≥ 97 %; length compliance ≥ 90 %.
- Unit tests for each post-check with a fake model.
- Latency: median added by post-checks < 3 s (rewrite only runs when needed).

---

## H3 — Eval suite hardening (F3)

**Why:** the judge returns "unparsed" on every case, so contradictions are unmeasured; 19 cases
do not cover answer types, levels or domains.

**Scope**
1. `backend/evals/run.py::judge`: strip code fences, parse with `copilot.try_parse_json`, raise
   `max_tokens` if truncated; add a grader unit test with a fenced, LaTeX-containing judge reply.
2. Extend `CASES` to ≥ 50: ≥ 3 per answer type, cases per user level (same question, student vs
   senior, different length/shape expectations), robotics/drone/automotive/aircraft/machinery
   questions within today's calculators, follow-ups, card-edit follow-ups (after H4),
   adversarial (price, brand, unsafe, out of scope). Every numeric target comes from a hand
   calculation in a comment, never from calculator output.
3. Add `expect.answer_type` and per-type shape checks in `grader.py`.
4. Offline CI subset: deterministic planner fixtures (recorded plans) + fake review model test the
   plumbing (provenance, clarify, post-checks) in `.github/workflows/ci.yml` on every push.
5. Report: pass rate per answer type and per domain; write `summary.txt` with trend vs last run.

**Accept:** judge parses ≥ 95 % of replies; CI runs the offline subset; live run documented in the
PR with pass rate per type.

---

## H4 — Card ↔ chat sync (F4)

**Why:** `ChatThread` renders `CalculatorView` with `initial` inputs only; edits never reach the
conversation, so "I changed the load, is it still OK?" cannot work.

**Scope**
1. `CalculatorView`: optional `onChange(values, result)` prop, debounced (~800 ms) after a
   successful run.
2. `ChatThread`: keep the latest edited state per card; on send, include `card_edits` in the chat
   request: `[{message_index, calculator, inputs, verdict, key_outputs}]`.
3. Backend `ChatRequest` accepts `card_edits`; store them on the assistant message's `tool_data`
   (`edited_inputs`, `edited_summary`) via a small `PATCH /sessions/{id}/messages/{mid}` endpoint
   or as part of the next chat call (pick one; document why).
4. `_history_text` includes edited state ("[user edited Bearing finder: Fr 3.5 → 4.2 kN; verdict
   now fail]"); the planner re-runs with edited inputs for "still OK?" follow-ups.
5. Reloading a session restores the edited values in the card.

**Accept:** eval case "edited load, still OK?" passes; reload shows edited values; unit test for
`_history_text` with edits.

---

## H5 — Calculation report v2 (F5)

**Why:** the markdown export is a transcript, not a deliverable for a design review.

**Scope**
1. Report model built from `tool_data` (not from chat text): cover (project, component, revision,
   author, checker, date, status — editable fields in an export dialog), per-calculation
   sections (purpose, load case, inputs with provenance, assumptions, checks with margins, worked
   steps, diagram, references, not-checked), summary table of all checks.
2. Renderers: HTML → PDF (e.g. WeasyPrint or headless Chromium; choose for Windows install
   simplicity and document it), DOCX (python-docx), markdown (existing).
3. Diagrams: render the same SVG the frontend uses (export from the client and send with the
   request, or server-side render — decide and document).
4. Re-run every calculation at export time from stored inputs; if a result differs from the
   stored one, flag it in the report.

**Accept:** a reviewer can reproduce every number from the PDF alone (checked on 3 sessions:
bolted joint, bearing selection, beam); PDF opens correctly on Windows and macOS.

---

## H6 — Tolerance stack-up calculator and MS output mode (F6)

**Scope**
1. New `backend/engineering/tolerances/stackup.py`: 1D stack, up to 15 contributors (nominal,
   +/− tolerance or ISO 286 fit reference, direction ±1). Outputs: nominal gap, worst-case
   min/max, RSS min/max (and optional Monte Carlo with fixed seed), contributor percentage ranking,
   check against required gap range. Diagram: stack bar chart. Known-value tests from a textbook
   example.
2. Margin-of-safety mode: an optional `n_convention = "SF" | "MS"` project/global setting; strength
   checks additionally report `MS = allowable / (applied × FS) − 1`. Start with fasteners, lugs
   (when added), beams and columns.
3. Planner catalog line and offline keyword rule for "stack", "tolerance chain", "axial play".

**Accept:** registry tests pass on defaults and presets; UC-10 runs in chat.

---

## H7 — Design spike: check plans, load cases and projects (F7–F9)

**Why:** Phase 2 is a data model change. Decide it on paper before building.

**Deliverable:** `product/strategy/specs/SPEC_PROJECT_MODEL.md` with:
1. Entities and relations: Project, Component (type), LoadCase, CheckPlan template, CheckItem,
   CalculationRun (inputs with provenance, load case, revision), Revision.
2. Check plan template format (YAML or Python dataclasses), with two complete examples written
   and reviewed: **shaft** and **bolted joint**. Each check item: failure mode, calculator id,
   input mapping from component/load case, applicability condition, required margin.
3. How coverage is computed and how "Not checked" flows into answers (H2) and reports (H5).
4. Migration from today's sessions (sessions become children of an "Unsorted" project).
5. Open questions with a recommendation each.

**Accept:** spec reviewed by the Technical Director; the shaft template, applied by hand to the
UC-6 conveyor shaft, produces the check list a senior engineer would write.

---

## Order and dependencies

```
H3 eval fixes ──┐
                ├─► H2 answer contract ─► H5 report v2
H1 provenance ──┘          ▲
H4 card sync ──────────────┘ (eval cases)
H6 tolerance stack (independent)
H7 spike (independent, informs Phase 2)
```

H1, H3, H6 and H7 can run in parallel. H2 after H1 and H3. H5 after H1 and H2.
