# MechCopilot product strategy — October 2026

**Owner:** Technical Director · **Date:** 2026-10-24 · **Code baseline:** `bda0714`

This folder is the product direction for MechCopilot from today's v1 to a product engineering
teams pay for. It supersedes `product/PRODUCT.md`, `product/OVERVIEW.md`,
`product/REQUIREMENTS.md` and `product/GENERATIVE_ENGINE_PLAN.md`, which describe a pre-v1
system (Llama models, model-written JavaScript, AI-generated UI) that no longer matches the code.

## Read in this order

| File | What it answers |
|---|---|
| [01_DESIGN_ENGINEERING_WORKFLOW.md](01_DESIGN_ENGINEERING_WORKFLOW.md) | How design work really runs from concept to series production, junior vs senior, per domain (vehicles, drones, robots, aircraft, machinery), and what an engineer needs from the tool |
| [02_CURRENT_STATE_AND_GAPS.md](02_CURRENT_STATE_AND_GAPS.md) | What the product does today, how good its answers are (with eval evidence), and the gaps |
| [03_PERSONAS_STORIES_USE_CASES.md](03_PERSONAS_STORIES_USE_CASES.md) | Six personas, 40+ user stories in 10 epics, 10 end-to-end use cases |
| [04_ANSWER_CONTRACT.md](04_ANSWER_CONTRACT.md) | The type, length and structure of every answer, by intent and user level, and how it is enforced |
| [05_FEATURES_AND_ROADMAP.md](05_FEATURES_AND_ROADMAP.md) | Product thesis, beachhead, 22 feature specs, prioritisation, four-phase roadmap, pricing, metrics, risks |
| [06_HANDOVERS.md](06_HANDOVERS.md) | Seven Phase 1 work packages, each ready to start: scope, files, acceptance criteria |

## The decision in one page

**Thesis:** the senior engineer's check sheet, run in seconds, with a report you can sign. The
model plans and explains; validated calculators produce every number.

**What is strong:** the calculation kernel (27 calculators, units end to end, 333 passing tests,
standard part outputs). Keep it.

**What is broken:** trust plumbing. The latest live eval passed 2 of 17 cases. Two beam answers
were wrong (13 mm instead of 9.8 mm; 77.9 mm instead of ≈ 16 mm) because inputs the planner left
out silently took demo defaults. Answers also contain extrapolated numbers and run over length.
The kernel itself gives the right values when run directly.

**What is missing:** the tool is stateless while design work is stateful. No projects, load cases,
check coverage, calculation chains, change tracking or a signable report. Coverage stops at
detailed design for industrial machine parts.

**Plan:**
1. **Phase 1 (weeks 0–6) — every number right and visible:** input provenance, no silent
   defaults, answer contract by question type, eval hardening, card ↔ chat sync, PDF report,
   tolerance stack-up.
2. **Phase 2 (weeks 6–18) — it knows my design:** projects, load cases, component check plans
   with a coverage map (the core differentiator), calculation chains, stale detection,
   materials v2, robotics and drone packs.
3. **Phase 3 (months 4–9) — in my workflow and team:** design review mode, image input, Onshape
   bridge, FEA sanity checks, team review and approval, automotive and aircraft packs.
4. **Phase 4 (months 9–15) — enterprise and series production:** company knowledge, private
   deployment, SolidWorks, PLM export, production-stage tools.

**Beachhead:** robotics, drone, industrial machinery teams and consultants. Automotive and
aerospace follow once traceability, team review and private deployment exist.

**Start here:** handovers H1 (provenance) and H3 (eval fixes), in parallel.
