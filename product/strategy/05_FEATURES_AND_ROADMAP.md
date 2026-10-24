# 05 — Feature plan and product roadmap

**Owner:** Technical Director · **Date:** 2026-10-24

---

## 1. Product thesis

**MechCopilot is the senior engineer's check sheet, run in seconds, with a report you can sign.**

It sits between CAD and FEA: the hand calculations, standard-part selection, design checks and
documentation that every part needs and that today live in personal spreadsheets. The language
model plans, explains and reviews; validated calculators produce every number.

**What we are not:** a CAD tool, an FEA solver, a PLM system, or a general chat assistant. We
integrate with those; we do not rebuild them.

**Why we win:**
1. Computed, traceable numbers (general assistants cannot promise this).
2. Check coverage: the knowledge of which checks a part needs, made explicit.
3. Standard, buyable outputs: designations, not abstractions.
4. A deliverable (calc report) that fits the release process.
5. Local-first / private deployment for IP-sensitive industries.

**Market landscape to watch (verify current state before positioning work):** calculation
suites (KISSsoft, MESYS, MITCalc), structural calc SaaS (ClearCalcs, SkyCiv, CalcTree), maths
documents (Mathcad), AI copilots for mechanical engineering (e.g. Leo AI), design review tools
(e.g. CoLab), and the AI assistants inside CAD platforms (Onshape, SolidWorks, Fusion).

---

## 2. Beachhead

**First market: small and mid-size hardware teams — robotics, drones/UAV, industrial machinery,
and consultants.** Reasons: generalist engineers with no specialist per domain (high pain),
short buying cycles, credit-card SaaS acceptable, no certification gate to enter. Automotive
tier-1 and aerospace come second; they need traceability, team review and private deployment,
which this roadmap builds by phase 3.

---

## 3. Feature specs

Effort: **S** ≤ 1 week, **M** 2–4 weeks, **L** 1–3 months (one engineer).
Stories refer to `03_PERSONAS_STORIES_USE_CASES.md`.

### Foundation — trust (Phase 1)

**F1 — Input provenance and no silent defaults** · M · US-1.1, 1.2
- Every calculator input carries `source`: `user | project | assumed | default | derived`.
- Planner output: inputs it sets must state `user` (value quoted from the message) or `assumed`
  (with reason). Everything else is `default`.
- Each calculator declares its **governing params** (loads, speed, span, life, pressure, key
  geometry). If any governing param is `default`, the copilot must clarify or label the run
  `example`.
- Position-type defaults that depend on another input (e.g. `beam_analysis.x1` = 2.5 m) are
  re-derived from that input (e.g. tip of cantilever, mid-span) instead of fixed numbers.
- UI: provenance chips above each card; `default`/`assumed` highlighted.
- **Accept:** `beam_ipe200` and `cantilever_imperial` evals return the hand-calc values;
  `concept` eval never describes defaults as the user's design; unit test asserts every
  calculator lists governing params.

**F2 — Answer contract v2** · M · US-1.3, 1.4, 2.1–2.5
- Implement `04_ANSWER_CONTRACT.md`: seven answer types, level modulation, structured trust
  elements, grounding and length post-checks.
- **Accept:** eval pass rate ≥ 85 % on Fast; grounding ≥ 97 %; length compliance ≥ 90 %; zero
  emoji.

**F3 — Eval suite hardening** · S · US-1.6
- Fix judge JSON parsing (currently "unparsed" on every case).
- Grow to ≥ 50 cases: every answer type, every level, the five domains, follow-ups, card-edit
  follow-ups, adversarial (price, brand, out-of-scope, unsafe request).
- Offline subset (fake model, deterministic planner fixtures) runs in CI on every push; live
  suite runs before each release and its pass rate is recorded in the release notes.

**F4 — Card ↔ chat sync** · S · US-5.1
- Editing a calculator card persists its current inputs and result to the message's `tool_data`
  and feeds them to the next turn's history ("[user edited Bearing finder: Fr 3.5 → 4.2 kN;
  verdict now fail]").
- **Accept:** "I changed the load, is it still OK?" eval passes using the edited values.

**F5 — Calculation report v2 (PDF/DOCX)** · M · US-6.1, 6.2
- Cover: project, component, revision, author, checker, date, status.
- Per calculation: purpose, load case, inputs table with provenance, assumptions, checks with
  margins, worked solution (LaTeX rendered), diagram, references, not-checked list.
- Formats: PDF (primary), DOCX, markdown.
- **Accept:** a reviewer can reproduce every number from the report alone.

**F6 — Quick-win calculators** · M · US-8.2
- Tolerance stack-up (1D: worst case, RSS, contributor ranking).
- Thermal expansion mismatch / fit change with temperature.
- Margin-of-safety output mode on every strength check (for aircraft users).

### Workflow core (Phase 2)

**F7 — Design Project workspace** · L · US-3.1, 3.4
- Project → components → sessions. Project holds requirements, envelope, units, standards set
  (ISO/EN vs ASME/AISC), SF policy per load-case type, preferred materials and parts.
- Every calculation reads project values first (`source: project`).

**F8 — Load case manager** · M · US-3.2, 3.3
- Named load cases with type (operating / peak / misuse / fatigue / ultimate), factors, duty cycle.
- Results carry the load case; a component's verdict = worst case across load cases.
- Domain generators (F15): vehicle g-factors, drone hover/max-thrust/landing, aircraft V-n limit
  → ultimate, robot peak vs RMS duty.

**F9 — Component check plans and coverage map** · L · US-4.1, 4.2, 4.3
- A **check plan** per component type is data: list of failure modes → calculator(s) → when it
  applies. Seed templates: shaft, bolted joint, bearing arrangement, welded bracket, beam/frame,
  spring, gear stage, pressure part, robot joint, drone arm, aircraft fitting.
- Coverage map per component: passed / warn / failed / not run / not applicable (with reason).
- Feeds "Not checked" in every answer (F2) and the report (F5).
- **This is the product's core differentiator. Treat the templates as engineering content
  reviewed by senior engineers, versioned and tested.**

**F10 — Calculation chains** · L · US-5.2
- Outputs of one calculator wire into inputs of another (torque → key, fit, bearing; bearing
  reaction → bearing life). Units checked at each link.
- Starts as fixed chains inside check plans (simple, testable), not a free-form canvas.
- Follow-up limit of 2 extra runs lifted inside a chain.

**F11 — Revisions and stale detection** · M · US-5.3, 6.4
- Project values and load cases are versioned. Any change marks dependent results `stale`;
  one-click re-run; delta report.

**F12 — Materials database v2** · M · US-8.1
- 150+ materials: carbon and alloy steels, stainless, aluminium (6061-T6, 6082-T6, 7075-T6,
  2024-T3), titanium (Ti-6Al-4V), cast iron, magnesium, copper alloys, engineering plastics
  (POM, PA66, PA66-GF30, PEEK, PC), CFRP/GFRP laminates (quasi-isotropic and UD).
- Per material: static properties, fatigue (endurance or S–N), temperature knock-downs, density,
  E, CTE, conductivity, typical processes, source and data quality (`typical` / `minimum`).
- Selection by performance index (stiff light beam, strong light tie, etc.).

**F13 — Standard parts catalogue v2** · L · US-8.5
- Seals and O-rings with groove design, retaining rings (DIN 471/472), dowel and spring pins,
  linear guides, ball screws, couplings, timing belts, chains, gearboxes and motors (robotics).
- Same contract as bearings: standard designation, typical data, link to confirm, user CSV import.

**F14 — Calculator expansion** · L (ongoing)
- Priority by beachhead: motor + gearbox sizing; moment-load bearing (crossed-roller,
  four-point); ball screw and linear guide life; belt and chain drives; link/frame deflection;
  plate and beam natural frequency; tube bending/buckling for composites; bolted joints in
  aluminium and composite (bearing stress, inserts); lug/clevis; rivets; adhesive lap joints;
  snap-fits; Hertz contact; Miner damage accumulation.
- Every new calculator: known-value tests, diagram, governing params declared (F1), check-plan
  mapping (F9).

**F15 — Domain packs** · M each
- Robotics, Drone/UAV, Industrial machinery first; Automotive chassis and Aircraft structures
  in Phase 3. A pack = load case generator + check plan templates + calculators + margin
  convention + eval cases.

### Context and integrations (Phase 3)

**F16 — Design review mode** · M · US-7.1–7.3
- Input: component(s) in a project, or pasted description / calc summary. Output: answer type G.
- Uses the check plan + DFMEA seed per component; every finding cites a calculation or a missing one.

**F17 — Image input** · M · US-9.2
- Upload a sketch, drawing or FEA screenshot. The model extracts dimensions, loads and
  annotations into proposed inputs (`source: assumed`, user confirms). Never measures from pixels
  without stating it.

**F18 — CAD bridge** · L · US-9.1
- **Onshape first** (cloud REST API, no installer, fits startups): read mass properties,
  material, named variables and key dimensions; write variables back.
- SolidWorks add-in second (task pane, same backend); Fusion third.
- CAD values enter as `source: project` with the model revision recorded.

**F19 — FEA assistant** · M · US-9.3
- Hand-calc cross-check for a stated FEA result (beam/plate/shell closed forms, net-section
  stress); setup checklist (BCs, contact, mesh convergence, singularities); result
  interpretation from screenshots (F17).

**F20 — Team, review and approval** · L · US-10.1
- Accounts, shared projects, roles (author, checker, approver), comments on calculations,
  approval status on reports, activity log.

**F21 — Company knowledge** · L · US-9.4
- Upload design guides, preferred parts lists, lessons learned; retrieval-grounded answers with
  citations; company check items added to check plans (F9).

**F22 — Enterprise deployment** · L · US-10.2, 10.3
- SSO, audit log, data retention controls, self-hosted backend, private / on-prem model option.

### Platform (continuous)
- **Latency:** stream the verdict line within 8 s (plan → compute → verdict first, explanation
  after); median full answer < 15 s.
- **Cost:** < 3 cents per Fast answer at current models; plan with the small model, review with
  the strong one only when a check fails or Deep is selected.
- **Units and standards:** metric and imperial first-class; ISO/EN and ASME/AISC sets per project.

---

## 4. Prioritisation

| Feature | User value | Differentiation | Effort | Phase |
|---|---|---|---|---|
| F1 Provenance / no silent defaults | Critical (trust) | High | M | 1 |
| F2 Answer contract v2 | High | Medium | M | 1 |
| F3 Eval hardening | High (enables all) | Medium | S | 1 |
| F4 Card ↔ chat sync | High | Medium | S | 1 |
| F5 Report v2 | High | High | M | 1 |
| F6 Tolerance stack + MS mode | High | Medium | M | 1 |
| F9 Check plans + coverage | Very high | **Very high** | L | 2 |
| F7 Projects | Very high | Medium | L | 2 |
| F8 Load cases | Very high | High | M | 2 |
| F10 Chains | High | High | L | 2 |
| F11 Stale detection | High | High | M | 2 |
| F12 Materials v2 | High | Medium | M | 2 |
| F14/F15 Robotics + Drone packs | High (beachhead) | High | L | 2 |
| F13 Parts catalogue v2 | Medium | Medium | L | 2–3 |
| F16 Review mode | High | High | M | 3 |
| F17 Image input | Medium | Medium | M | 3 |
| F18 CAD bridge (Onshape) | High | Medium | L | 3 |
| F19 FEA assistant | Medium | Medium | M | 3 |
| F20 Team / approval | High (paid tier) | Medium | L | 3 |
| F21 Company knowledge | Medium | Medium | L | 4 |
| F22 Enterprise deployment | High (enterprise) | Medium | L | 4 |

---

## 5. Roadmap

### Phase 1 — "Every number is right and visible" (weeks 0–6)
F1, F2, F3, F4, F5, F6. Clean up stale product docs.
**Exit criteria:** live eval ≥ 85 % pass (≥ 50 cases); grounding ≥ 97 %; zero governing inputs
from defaults in verdict answers; PDF report reproduces every number; 10 external engineers
use it weekly and rate trust ≥ 4/5.

### Phase 2 — "It knows my design" (weeks 6–18)
F7, F8, F9, F10, F11, F12, Robotics and Drone packs (F14/F15), first part of F13.
**Exit criteria:** UC-1, UC-2, UC-6, UC-7, UC-10 run end to end; a junior's component reaches
100 % coverage without the lead adding a check; first 50 paying Pro users.

### Phase 3 — "It sits in my workflow and my team" (months 4–9)
F16, F17, F18 (Onshape), F19, F20, Automotive and Aircraft packs, rest of F13.
**Exit criteria:** UC-3, UC-4, UC-5, UC-8, UC-9 run end to end; first 5 team accounts;
Onshape app published.

### Phase 4 — "Enterprise and series production" (months 9–15)
F21, F22, SolidWorks add-in, PLM export (Teamcenter / Windchill attachment), production-stage
features (cost-down re-verification at scale, Cpk from tolerance data, PFMEA seeds).
**Exit criteria:** first enterprise pilot on private deployment.

---

## 6. Business model (hypothesis to validate in Phase 1–2)

| Tier | Price (hypothesis) | Includes |
|---|---|---|
| Free | $0 | Calculator library, 20 copilot answers / month, markdown export |
| Pro | $39 / month | Unlimited answers, projects, load cases, check plans, PDF/DOCX reports, domain packs |
| Team | $79 / seat / month | Shared projects, review and approval, company templates, Onshape bridge |
| Enterprise | Contract | SSO, audit, private deployment / own model, company knowledge, custom calculators |

---

## 7. Metrics

- **North star:** verified design decisions per active user per week (calculation-backed answers
  the user accepted, exported or marked as reviewed).
- **Trust:** eval pass rate per release; share of verdicts with all governing inputs from
  user/project; user-flagged wrong answers per 1 000.
- **Activation:** first calculation-backed answer within 5 minutes of first visit.
- **Depth:** components with ≥ 80 % check coverage; reports exported per project.
- **Retention:** week-4 retention of Pro users ≥ 40 %.
- **Speed:** time to verdict line (target < 8 s), full answer (< 15 s).
- **Cost:** model cost per answer, per tier.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| A wrong answer in a safety-critical design | F1/F2 enforcement, evals as release gate, provisional/example labels, disclaimer, reports that make review easy |
| Check plans written by too few experts | Version and test them like code; senior reviewers per domain; company extensions |
| Catalogue data licensing (SKF etc.) | Standard dimensions + typical ratings + links (current approach); partnerships later; user import |
| CAD vendors ship their own copilots | Stay CAD-neutral; own the calculation, coverage and report layer they do not do well |
| IP concerns block adoption | Local-first today; private deployment in Phase 4 |
| Model cost/latency | Small planner, verdict-first streaming, cache calculator catalog prompt |
