# 01 — The design engineering workflow MechCopilot must serve

**Owner:** Technical Director · **Date:** 2026-10-24 · **Status:** Baseline for all planning

This is the reference model of how mechanical design work actually happens, from first concept
to series production, across vehicles, drones, robots, aircraft and industrial machinery. Every
feature in this plan is justified against a stage and a pain point in this document.

---

## 1. The lifecycle in six stages

Industries use different names (stage-gate, APQP, V-model, PDR/CDR in aerospace), but the work is
the same. Each stage ends at a gate where someone senior signs off.

| # | Stage | Main question | Typical gate |
|---|---|---|---|
| 0 | Requirements & targets | What must this thing do, survive and cost? | Requirements review |
| 1 | Concept | Which architecture, and does it close on paper? | Concept selection |
| 2 | System layout | How do subsystems share space, load and interfaces? | PDR (preliminary design review) |
| 3 | Detailed design | Is every part sized, specified, toleranced and drawn? | CDR (critical design review), drawing release |
| 4 | Prototype & verification | Does the built thing match the calculation? | DV sign-off (DVP&R complete) |
| 5 | Industrialisation & series | Can it be made at rate, at cost, every time? | PPAP / FAI, SOP (start of production) |

### Stage 0 — Requirements & targets
**Work:** turn customer and regulatory needs into numbers. Define load cases (operating, peak,
misuse, fatigue spectrum, crash/drop), environment (temperature, corrosion, IP rating, vibration),
life, mass budget, cost target, package envelope, applicable standards.
**Calculations:** load derivation (g-factors, duty cycles, power/torque from performance targets),
mass budgets, first-order energy and power balances.
**Artifacts:** requirements spec, load case table, target cascade (vehicle → system → part).
**Where it goes wrong:** load cases are vague ("strong enough"), misuse is forgotten, fatigue
spectrum is guessed late, the target cascade is in someone's head.

### Stage 1 — Concept
**Work:** generate 2–5 architectures, size each on the back of an envelope, compare.
**Calculations:** first-order sizing (is a 20 mm or 40 mm shaft needed?), material/process choice
(Ashby-style indices), drive sizing (motor + gearbox), rough mass and cost.
**Artifacts:** trade study (Pugh or weighted matrix), concept sketches, concept FMEA, benchmark.
**Where it goes wrong:** concepts are chosen on taste, not numbers; a concept that cannot close
(bearings too big for the envelope, mass over budget) is discovered in stage 3.

### Stage 2 — System layout
**Work:** skeleton/master model, space claims, interface control (ICDs), load paths through the
assembly, joint strategy (bolted, welded, bonded, press fit), bearing arrangement (locating /
floating), first tolerance stacks, BOM v0, make-or-buy.
**Calculations:** free-body diagrams and reaction loads per load case, load distribution to
subsystems (often from multibody simulation), first-pass bearing and fastener selection,
critical stacks.
**Artifacts:** layout drawings, ICDs, DFMEA v1, mass roll-up, BOM v0.
**Where it goes wrong:** loads at interfaces are not agreed between teams; stacks are not done
until parts clash in prototype.

### Stage 3 — Detailed design
**Work:** model every part, select every standard part, run every check, specify material and
finish, apply GD&T, release drawings.
**Calculations (the core of today's MechCopilot):** bolted joints (VDI 2230), bearing life
(ISO 281), shaft fatigue, keys and fits, gears, springs, welds, buckling, pressure, plus FEA
(linear static, modal, fatigue, contact) for anything non-standard.
**Artifacts:** part models, drawings, calculation report per part/assembly, FEA report, DFMEA v2,
design review minutes.
**Where it goes wrong:** a check is simply forgotten (fatigue on a "static" bracket, thread
stripping in aluminium, bearing seat fits, thermal growth), calculations are not traceable to the
revision that was built, FEA is trusted with bad boundary conditions.

### Stage 4 — Prototype & verification
**Work:** build, test, correlate, fix. Write the DVP&R (design verification plan and report).
**Calculations:** test load derivation, strain gauge correlation, hand-calc vs FEA vs test,
root-cause analysis when something breaks, re-sizing after failure.
**Artifacts:** test specs, test reports, 8D/root-cause reports, ECRs (engineering change requests).
**Where it goes wrong:** the calculation that justified the part is not re-run when the change is
made; nobody knows which other parts were sized on the same wrong load.

### Stage 5 — Industrialisation & series production
**Work:** supplier drawings, process capability, PFMEA, control plans, PPAP/FAI, cost-down (VAVE),
change management, field issues and warranty.
**Calculations:** tolerance capability (Cpk), cost-down re-checks ("can we drop to 8.8 bolts?",
"can this be a casting?"), field failure analysis, variant checks.
**Artifacts:** PPAP pack, ECNs, cost-down proposals with re-verification.
**Where it goes wrong:** cost-down changes are approved without re-running the original checks;
the original engineer has left and the calc lives in a lost spreadsheet.

---

## 2. Junior vs senior: same job, different failure modes

| | Junior (0–3 years) | Senior / lead (10+ years) |
|---|---|---|
| Knows the formulas | Yes, from school | Yes, and their limits |
| Knows which check governs | Rarely | Instantly |
| Knows what to assume when data is missing | No, freezes or guesses silently | Yes, and writes it down |
| Typical miss | Forgets a whole failure mode (fatigue, buckling, fretting, stripping, galvanic, thermal) | Small slip under time pressure; skips documentation |
| Knows standard parts | Searches catalogues for an hour | Knows the 6206 and the M10 8.8 by heart |
| Needs from a tool | Guidance, a checklist, the *why*, confidence before review | Speed, a sanity check, a report they can sign, review of juniors' work |
| Hates | Being made to feel stupid; walls of theory | Being lectured; unverifiable numbers; extra clicks |
| Time sink | Finding the method, building the spreadsheet | Reviewing other people's calcs, writing reports |

**Product consequence:** one engine, two behaviours. For juniors the copilot leads (checklist,
explanation, what a senior would check next). For seniors it follows (terse verdict, margin,
exceptions only, export).

---

## 3. What a design engineer needs at each stage

| Need | 0 Req | 1 Concept | 2 Layout | 3 Detail | 4 Proto | 5 Series |
|---|---|---|---|---|---|---|
| Load cases with factors and duty cycles | ●●● | ●● | ●●● | ●●● | ●● | ● |
| First-order sizing, fast | ● | ●●● | ●● | ● | ●● | ● |
| Trade studies / option comparison | ● | ●●● | ●● | ● | | ●● |
| Standard part selection | | ●● | ●●● | ●●● | ● | ●● |
| Detailed standard checks | | | ●● | ●●● | ●● | ●● |
| Check coverage ("what haven't I checked?") | | ● | ●● | ●●● | ●● | ●● |
| Tolerance stacks / fits | | | ●●● | ●●● | ●● | ●●● |
| Materials and processes | ● | ●●● | ●● | ●●● | ● | ●● |
| FEA setup and sanity checks | | | ● | ●●● | ●●● | ● |
| Traceable calculation report | | ● | ●● | ●●● | ●●● | ●●● |
| Change impact ("what else does this break?") | | | ●● | ●●● | ●●● | ●●● |
| Root-cause support | | | | ● | ●●● | ●●● |
| CAD context (mass, material, dimensions) | | ● | ●●● | ●●● | ●● | ●● |

●●● = critical, ●● = important, ● = useful.

---

## 4. Domain differences that matter for the product

The mechanics are shared; the load cases, margins and dominant checks differ. These become
**domain packs** (see 06_FEATURE_SPECS, F15).

| Domain | Dominant concerns | Margin convention | Calculations missing today |
|---|---|---|---|
| **Robotics & automation** | Joint torque, gearbox and motor sizing, link stiffness and deflection, bearing moment loads, cycle life | Safety factor 1.5–3 on yield, life in cycles | Motor + gearbox sizing, crossed-roller / 4-point bearing moment load, harmonic drive check, ball screw and linear guide life, belt drives, link deflection at the tool point |
| **Drones / UAV** | Mass above everything, thrust-to-weight, vibration (prop frequencies vs arm modes), composites, bolts in carbon | Low SF (1.2–1.5) with test | Thrust/power budget, arm natural frequency vs prop rpm, CFRP tube bending/buckling, bearing stress in laminates, inserts in composites, vibration isolation |
| **Automotive** | Fatigue under road load spectra, misuse loads (pothole, kerb strike), NVH, cost at volume, joints | g-factor load cases, fatigue damage, SF by load case | Load case generator (bump/brake/corner g's), damage accumulation (Miner), spot weld/structural adhesive, bolted joint in aluminium, bushings |
| **Aircraft / eVTOL** | Certification, margin of safety, ultimate vs limit, thin-wall stability, lugs, fittings | MS = allowable / (limit × 1.5 × fitting factor) − 1 ≥ 0 | MS reporting convention, lug/clevis (Bruhn/Melcher), rivets and fastener bearing/shear-out, panel buckling, crippling, V-n diagram loads |
| **Industrial machinery** | Shaft lines, bearings, gears, frames, welded structures, long life | SF on yield + fatigue, L10h | Couplings, belt/chain drives, wire rope, brakes/clutches, frame stiffness |

---

## 5. What I would want, as the engineer using this tool

Written from the seat of the engineer doing the work. These are the asks the plan is built on.

**Abstract level (how the tool should guide the design process)**
1. **Remember my design.** Requirements, envelope, materials, safety-factor policy and load cases
   are set once per project and used by every calculation. I should never re-type a load.
2. **Know the checklist for the part I'm designing.** A shaft needs static, fatigue, deflection,
   critical speed, key or fit, bearing seats. Show me what's done, what failed, what's missing.
3. **Chain the calculations.** The torque that sized the shaft must flow into the key, the fit
   and the bearing reaction loads, and update when I change it.
4. **Tell me what you assumed.** Every input: did I give it, did you assume it, or is it a
   calculator default? Defaults must never pretend to be my design.
5. **Lead or follow depending on who I am.** Guide a junior through the method; give a senior the
   verdict and the exceptions.
6. **Hand me the deliverable.** A calculation report I can put in the design review and sign,
   tied to the drawing revision.
7. **Track change.** When a load or dimension changes, tell me which calculations are now stale.

**Micro level (details each answer and calculation needs)**
- Governing check first, with the margin as a number (SF, MS or utilisation), not adjectives.
- Units shown and switchable; imperial and metric both first-class.
- Standard designations (bolt ISO 4017 M10×40-8.8, bearing 6206-2RSH, fit H7/p6) with a link to
  the source to confirm.
- Load case named on every result ("Peak brake, 1.5 g").
- Assumptions that would change the answer, separated from those that don't.
- What was **not** checked, explicitly.
- The worked solution with formula and standard clause, collapsible.
- One clear next action.

**Tools and data I need that the product does not have yet**
- Load case manager, project memory, calculation chains, check coverage, tolerance stack-up,
  materials database with fatigue and temperature data, wider standard-part catalogues (seals,
  retaining rings, pins, linear guides, ball screws, gearboxes, motors), CAD context, FEA sanity
  checks, PDF/DOCX calculation reports with revision control, design review mode.
