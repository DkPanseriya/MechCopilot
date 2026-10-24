# 02 — Current state audit and gap analysis

**Owner:** Technical Director · **Date:** 2026-10-24 · **Code baseline:** `bda0714` on `master`

Sources: the code (`backend/copilot.py`, `backend/engineering/`, `backend/routers/`,
`frontend/components/`), the test suite (333 tests pass), the latest live eval report
(`backend/evals/reports/20261023-191744-efficient.md`), and direct runs of the calculators.

---

## 1. What exists today

| Area | State |
|---|---|
| **Calculator kernel** | 27 typed calculators (fasteners, bearings, beams, shafts, keys and fits, gears, springs, welds, columns, pressure vessels, fatigue, combined stress). Pint units end to end, worked steps in LaTeX, checks with ok/warn/fail, plots, tables, annotated SVG diagrams. Verified against textbook and standard examples. **This is the moat. It is good.** |
| **Data** | 285 bearings (ISO dimensions, typical ratings, SKF designations and links), full ISO metric fastener tables, 26 materials, CSV import for user bearing catalogues. |
| **Copilot pipeline** | PLAN (small model picks 1–3 calculators and inputs) → COMPUTE (kernel) → FOLLOW-UP (up to 2 more calculators if a check fails) → REVIEW (strong model writes the answer from computed numbers only). Clarifying questions as a form when key inputs are missing. Fast and Deep tiers. Offline keyword fallback. |
| **Answer format** | Bold verdict line, 2–4 "why" bullets, "Assumptions to confirm", "Next", ≤170 words (Fast) / ≤320 (Deep). Grounding rule: every number must come from results or the user. |
| **Personalisation** | Onboarding asks career stage and focus area; one line of tone guidance goes into the prompt. |
| **Frontend** | Chat with streamed answers and inline calculator cards; calculator library usable without chat; materials page; dark mode; markdown report export. |
| **Persistence** | SQLite sessions and messages. No users, no projects. |
| **Quality tooling** | 333 unit tests; 19-case live eval suite with grounding check and model judge. |
| **Distribution** | Local app (start.bat / start.sh), Replicate or OpenAI key, MIT licence. |

---

## 2. How good are the answers? (evidence)

Latest live eval, Fast tier, 2026-10-23: **2 of 17 cases pass**, mean grounding 87 %, median
latency 19.9 s. Reading the answers one by one, the failures fall into five groups:

### 2.1 Silent default leakage (critical: wrong engineering answers)
The planner sets some inputs; every input it leaves out silently takes the calculator's **demo
default**. The review model is told only "other inputs: calculator defaults", not which values.

- `beam_ipe200`: correct answer 9.8 mm deflection. The copilot reported **13 mm**. Running
  `beam_analysis` directly with the question's inputs gives 9.8 mm, so the kernel is right and
  the planner's input mapping was wrong.
- `cantilever_imperial`: correct answer ≈ 16 mm (0.64 in). The copilot reported **77.9 mm and
  472 MPa, "this design fails"**. A direct run with the stated inputs gives 15.6 mm. Note also that
  `x1` (point load position) defaults to 2.5 m, which lies outside a 6 ft (1.83 m) cantilever and
  makes the calculator error unless the planner sets it.
- `concept` ("remind me how bending and torsion combine"): the answer told the user their
  "40 mm C45 shaft is oversized" — the user has no shaft. The demo case was presented as the
  user's design.

An engineer who catches one of these stops trusting the tool. **This is the highest priority
defect in the product.**

### 2.2 Grounding violations
The prompt forbids extrapolated numbers, yet answers contain them: "if μ drops to ~0.09 … preload
becomes ~104 kN" (`bolt_torque_m16`), "αA ≈ 1.2–1.4", "45 mm is a standard EN 10060 size". Prompt
rules alone do not hold; a post-check is needed.

### 2.3 Length and format drift
Fast answers run 190–260 words against a 170 limit; most "fails" in the report are the length
check. Emoji (✅ ❌) appear. Every answer has the same skeleton regardless of question type, so a
one-line lookup gets four sections.

### 2.4 Answering a different question
The selector answers are good engineering, but several recommend alternatives the user did not
ask for, at length, before answering what was asked.

### 2.5 Eval infrastructure
The model judge result is "unparsed" for every case, so contradictions are not being measured.
`evals/run.py::judge` extracts the first `{` and parses; the judge replies with fenced JSON that
fails to parse (likely LaTeX escapes or truncation). Fix before using the judge as a gate.

**What is good in the answers:** verdict first, real part designations, failures stated plainly,
alternatives computed rather than guessed, correct identification of missing checks (LTB on the
IPE, fatigue on the shaft). The senior-engineer voice is right. The problems are trust plumbing,
not engineering judgement.

---

## 3. Product-level gaps

### 3.1 Workflow gaps (the tool is stateless; design is not)
| Gap | Effect on the engineer |
|---|---|
| No project / design context | Loads, materials, envelope and SF policy are re-typed in every chat. |
| No load case concept | Results are not tied to a named load case; peak vs fatigue vs misuse is implicit. |
| No calculation chaining | Shaft torque does not flow into key, fit and bearing loads. Follow-up is capped at 2 extra runs. |
| Card edits are invisible to the copilot | `ChatThread` renders `CalculatorView` with `initial` inputs only; changes in the card never return to the conversation. "I changed the load to 12 kN, still OK?" fails. |
| No check coverage | Nothing tells the user which failure modes of the part are unchecked. |
| No change tracking | When an input changes, nothing marks dependent results stale. |
| Report is a markdown dump | No revision, no signature block, no inputs-with-provenance, no PDF/DOCX. Not usable for a design review. |
| Persona is one prompt line | Juniors and seniors get the same structure. |

### 3.2 Coverage gaps by lifecycle stage
| Stage | Coverage today | Missing |
|---|---|---|
| 0 Requirements | None | Load case derivation, duty cycles, g-factor generators, target cascade |
| 1 Concept | Weak (single calculators) | Trade study / option comparison, quick sizing chains, material selection indices, motor/gearbox sizing |
| 2 Layout | Partial (selectors) | Free-body / reactions for assemblies, bearing arrangement, tolerance stacks, mass roll-up |
| 3 Detail | **Strong for 27 checks** | Tolerance stack-up, lugs, thin-wall buckling, O-rings, retaining rings, pins, belts/chains, ball screws, linear guides, plastics, composites, adhesives, rivets, inserts, modal hand calcs, thermal mismatch |
| 4 Prototype | None | FEA sanity check, test correlation, root-cause guidance, re-sizing after failure |
| 5 Series | None | Cost-down re-verification, change impact, Cpk from tolerances |

### 3.3 Data gaps
- 26 materials, no fatigue curves, no temperature dependence, few aluminium alloys, no
  titanium, plastics or composites. Drones and aircraft cannot be served without these.
- Standard parts limited to bolts and bearings.
- No company data (design guides, preferred parts lists, lessons learned).

### 3.4 Platform gaps
- No accounts, teams, roles, sharing or approval.
- No CAD or FEA connection.
- No image input (sketches, drawings, FEA contour plots).
- Latency ~20 s with no early verdict; cost 3–5 cents per Fast answer.
- Product docs (`product/PRODUCT.md`, `OVERVIEW.md`, `REQUIREMENTS.md`,
  `GENERATIVE_ENGINE_PLAN.md`) describe a pre-v1 system (Llama, `formula_js`, AI-generated UI)
  and contradict the code. They should be marked superseded by this strategy set.

---

## 4. Strengths to protect

1. **The model never does arithmetic.** Every number comes from a tested calculator. This is the
   single biggest differentiator against general chat assistants and must never be diluted.
2. **Typed calculator contract.** Adding a calculator is a contained, testable task. Breadth can
   scale.
3. **Standard, buyable outputs.** Designations and links, not abstract "a bearing with C ≥ 20 kN".
4. **Works offline / local-first.** IP-sensitive customers (automotive, defence, aerospace) care.
5. **An eval suite exists.** Most AI products ship without one.

---

## 5. Summary scorecard

| Dimension | Score (1–5) | Note |
|---|---|---|
| Calculation correctness | 5 | Kernel verified; failures are upstream |
| Answer trustworthiness | 2 | Silent defaults, ungrounded numbers |
| Answer usability | 3 | Right voice, wrong length, one shape for all questions |
| Workflow fit | 1 | Stateless chat; design work is stateful |
| Lifecycle coverage | 2 | Detail design only |
| Domain breadth | 2 | Industrial machine design; not drones, aircraft, robots |
| Team / enterprise readiness | 1 | Single user, local SQLite |
| Differentiation | 4 | Computed answers + standard parts is rare |
