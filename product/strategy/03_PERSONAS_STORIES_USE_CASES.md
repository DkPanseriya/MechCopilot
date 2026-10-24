# 03 — Personas, user stories and use cases

**Owner:** Technical Director · **Date:** 2026-10-24

---

## 1. Personas

### P1 — Priya, junior design engineer (primary user)
1.5 years at a 40-person robotics company. Owns the design of a gripper and two brackets. Knows
Shigley, has never sized a crossed-roller bearing. Builds a new spreadsheet for every calc.
- **Goal:** get designs through review without embarrassing misses.
- **Pain:** doesn't know which checks are needed; afraid to ask the lead the same question twice;
  hours lost finding methods and catalogue data.
- **Success with MechCopilot:** walks into the design review with a complete check list and a
  report, and the lead finds nothing new.

### P2 — Marco, lead design engineer (primary user, key influencer)
14 years, automotive tier-1, chassis brackets and joints. Reviews four engineers' work. Signs off
calculations.
- **Goal:** faster, safer reviews; consistent calcs across the team; documentation done.
- **Pain:** every engineer's spreadsheet is different; reviews take hours; cost-down requests
  arrive with no re-verification; the person who did the original calc has left.
- **Success:** reviews a junior's calc package in 15 minutes because inputs, assumptions,
  coverage and margins are in one standard report.

### P3 — Sam, mechanical lead at a drone / eVTOL startup (beachhead buyer)
The only senior mechanical engineer in a team of six. Covers structures, propulsion mounts,
fasteners, composites, thermal. Weight is everything.
- **Goal:** breadth without a specialist per domain; move fast without a field failure.
- **Pain:** no one to review their work; aerospace margins and composite rules are outside
  comfortable expertise; investors want test evidence.
- **Success:** has a second opinion on every load path and a report trail for the certification
  conversation.

### P4 — Elena, chief engineer / engineering manager (enterprise buyer)
Runs a 60-engineer department. Buys tools.
- **Goal:** consistent method, auditability, faster onboarding, fewer late-stage failures.
- **Pain:** knowledge walks out the door; quality depends on who did the calc; IP must not leave
  the company.
- **Success:** company design rules are enforced in every calc; audit trail per release; data
  stays on company infrastructure.

### P5 — Freelance / consulting design engineer
Delivers sized designs and calc reports to clients. Bills by the hour.
- **Goal:** produce client-ready calculation reports quickly.
- **Success:** a calc report with their name, revision and references, exported in minutes.

### P6 — Student / graduate (growth channel, not revenue)
Learns methods, uses the library for coursework and capstone projects (Formula Student, drone
teams, robotics competitions). Becomes P1 in two years.

---

## 2. Epics and user stories

Priority: **M** must (next release), **S** should, **C** could. IDs are referenced by the
feature specs (04) and handovers (06).

### E1 — Trustworthy answers
| ID | Story | Pri |
|---|---|---|
| US-1.1 | As **Priya**, I want every input in an answer marked as *given by me*, *assumed* or *default*, so that I never mistake a demo value for my design. | M |
| US-1.2 | As **Marco**, I want the copilot to refuse to compute when a governing input is unknown, rather than use a default, so that wrong answers never look right. | M |
| US-1.3 | As any engineer, I want every number in the answer traced to a calculation or to my message, so that I can verify it. | M |
| US-1.4 | As **Marco**, I want the answer to say plainly what was **not** checked, so that I know where the risk is. | M |
| US-1.5 | As any engineer, I want each result to show the standard and clause it follows, so that I can defend it in a review. | S |
| US-1.6 | As **Elena**, I want measured answer quality (eval pass rate per release), so that I can trust the tool across the team. | S |

### E2 — Answers that fit the question and the person
| ID | Story | Pri |
|---|---|---|
| US-2.1 | As **Marco**, I want a lookup ("torque for M12 10.9 oiled") answered in two lines, so that I'm not reading a report for a number. | M |
| US-2.2 | As **Priya**, I want a concept question answered with the method, the formula, a pitfall and a clearly labelled example, so that I learn without being confused by fake numbers. | M |
| US-2.3 | As **Priya**, I want the answer to end with "what a senior would check next", so that I build the habit. | S |
| US-2.4 | As **Marco**, I want to switch to terse mode per message, so that I get only the verdict and exceptions. | S |
| US-2.5 | As **Sam**, I want option comparisons as a short table with a recommendation, so that I can decide in one read. | S |

### E3 — Design project memory
| ID | Story | Pri |
|---|---|---|
| US-3.1 | As any engineer, I want to set requirements, envelope, materials, SF policy and standards once per project, so that every calculation uses them. | M |
| US-3.2 | As **Marco**, I want named load cases with factors (operating, peak, misuse, fatigue), so that every result says which case it covers. | M |
| US-3.3 | As **Sam**, I want load cases generated from a domain template (g-factors for vehicles, thrust/crash for drones, V-n for aircraft), so that I don't forget misuse cases. | S |
| US-3.4 | As any engineer, I want sessions grouped by project and component, so that I can find past work. | M |

### E4 — Component check plans and coverage
| ID | Story | Pri |
|---|---|---|
| US-4.1 | As **Priya**, when I say "I'm designing an output shaft", I want the copilot to show the full list of checks it needs, so that nothing is forgotten. | M |
| US-4.2 | As **Marco**, I want a coverage view per component (passed / failed / not run / not applicable with reason), so that I can review completeness at a glance. | M |
| US-4.3 | As **Elena**, I want to add company-specific checks to a component template, so that our rules are enforced. | C |

### E5 — Chained, live calculations
| ID | Story | Pri |
|---|---|---|
| US-5.1 | As any engineer, when I edit a calculator card, I want the copilot to know the new values, so that I can ask "is it still OK?". | M |
| US-5.2 | As **Priya**, I want the torque sizing the shaft to flow into the key, fit and bearing calcs automatically, so that the chain stays consistent. | S |
| US-5.3 | As **Marco**, when a load case or dimension changes, I want dependent results flagged stale with a one-click re-run, so that no calc is out of date. | S |
| US-5.4 | As **Sam**, I want a sweep ("plot safety factor vs wall thickness 1–3 mm"), so that I can find the lightest option. | C |

### E6 — Deliverables
| ID | Story | Pri |
|---|---|---|
| US-6.1 | As **Priya**, I want a PDF/DOCX calculation report with inputs and their provenance, assumptions, checks, worked solutions and references, so that I can take it to the design review. | M |
| US-6.2 | As **Marco**, I want report revision, author, checker and approval fields, so that the report fits our release process. | S |
| US-6.3 | As **P5 consultant**, I want my logo and project fields on the report, so that I can deliver it to a client. | C |
| US-6.4 | As **Marco**, I want a delta report between two revisions, so that I review only what changed. | C |

### E7 — Design review mode
| ID | Story | Pri |
|---|---|---|
| US-7.1 | As **Marco**, I want to give the copilot a design description (or calc package) and get findings ranked by severity, so that the first review pass is automated. | S |
| US-7.2 | As **Priya**, I want to self-review before I hand in, so that the lead's review is quick. | S |
| US-7.3 | As **Sam**, I want a failure-mode checklist (DFMEA seed) per component, so that I have a structured second opinion. | S |

### E8 — Library breadth and domain packs
| ID | Story | Pri |
|---|---|---|
| US-8.1 | As **Sam**, I want composites, aluminium, titanium and plastics with fatigue and temperature data, so that I can design light structures. | M |
| US-8.2 | As **Priya**, I want tolerance stack-up (worst case and RSS), so that I can check bearing preload and assembly clearances. | M |
| US-8.3 | As a robotics engineer, I want motor + gearbox sizing and moment-load bearing checks, so that I can size a joint end to end. | S |
| US-8.4 | As an aircraft engineer, I want margin-of-safety reporting, lugs and fastener bearing/shear-out, so that results use aerospace conventions. | S |
| US-8.5 | As any engineer, I want seals, retaining rings, pins, linear guides and ball screws with designations, so that more of my BOM comes out of the tool. | S |

### E9 — Context from CAD, images and company knowledge
| ID | Story | Pri |
|---|---|---|
| US-9.1 | As any engineer, I want to pull mass, material and key dimensions from my CAD model, so that I stop re-typing. | S |
| US-9.2 | As any engineer, I want to upload a sketch, drawing or FEA contour plot and have it read, so that I can ask about what I'm looking at. | S |
| US-9.3 | As **Marco**, I want hand-calc sanity checks for my FEA result, so that bad boundary conditions are caught. | S |
| US-9.4 | As **Elena**, I want the copilot to use our design guide and preferred parts list, so that answers follow company rules. | C |

### E10 — Team and enterprise
| ID | Story | Pri |
|---|---|---|
| US-10.1 | As **Marco**, I want to share a project and assign myself as checker, so that review happens in the tool. | S |
| US-10.2 | As **Elena**, I want SSO, roles and an audit log, so that IT approves the tool. | C |
| US-10.3 | As **Elena**, I want a self-hosted or private-model deployment, so that IP never leaves our network. | C |

---

## 3. Use cases (end-to-end scenarios)

Each use case is a test script for the product: if it cannot be completed, the roadmap is not
done. Steps marked ✱ need features that do not exist yet.

### UC-1 — Size a robot joint (robotics, junior)
**Actor:** Priya · **Trigger:** "Design the elbow joint: 3 kg payload at 600 mm, 90°/s, 20 000 h."
1. ✱ Copilot creates the component "Elbow joint" with its check plan: joint torque, motor +
   gearbox, output bearing (moment load), output shaft/flange, bolts to link, link deflection.
2. ✱ Derives joint torque from payload, link mass and acceleration (load case "peak") and
   continuous torque (load case "RMS duty").
3. ✱ Sizes motor + gearbox; selects crossed-roller bearing for the moment load.
4. Runs bolted joint for the output flange; shaft check at the gearbox output.
5. ✱ Coverage view shows link deflection at tool point still open; Priya runs it.
6. ✱ Exports the calculation report for the design review.

### UC-2 — Drone arm and motor mount (drone, mid-level)
**Actor:** Sam · **Trigger:** "Carbon arm, 22 mm OD tube, 350 mm, 2.1 kg thrust motor at 7000 rpm."
1. ✱ Load cases: hover, max thrust, hard landing (g-factor), crash (sacrificial).
2. ✱ CFRP tube bending and buckling; tip deflection.
3. ✱ Arm first natural frequency vs blade-pass frequency; flags resonance margin.
4. ✱ Motor mount bolts into carbon: bearing stress in laminate, insert pull-out.
5. Answer: verdict per load case with margins, the lightest wall thickness that passes all.

### UC-3 — Suspension bracket (automotive, senior)
**Actor:** Marco · **Trigger:** "Check bracket rev C for the 3 g bump / 1 g brake / 0.8 g corner cases."
1. ✱ Load cases pulled from the vehicle project.
2. Weld group and bolted joint checks per case; fatigue for the bump spectrum.
3. ✱ Coverage view: bushing seat fit and thread engagement in the aluminium knuckle not run.
4. ✱ Delta against rev B: which results changed.
5. ✱ Marco signs the report as checker.

### UC-4 — Wing-to-fuselage fitting (aircraft)
**Actor:** aerospace stress engineer · **Trigger:** "Lug, 7075-T6, 6 mm thick, Ø10 pin, 12 kN limit load."
1. ✱ Applies FS 1.5 ultimate and fitting factor 1.15 from the project's policy.
2. ✱ Lug net-tension, shear-out and bearing (Bruhn/Melcher); pin double shear and bending.
3. ✱ Reports margin of safety per mode, lowest MS first.

### UC-5 — Review a junior's design (review)
**Actor:** Marco · **Trigger:** opens Priya's shared project.
1. ✱ Sees coverage per component; two checks missing, one failing with an accepted deviation.
2. ✱ Runs review mode; gets findings ranked by severity with the calc that supports each.
3. ✱ Leaves comments; approves the report.

### UC-6 — Shaft line for a conveyor (industrial, junior)
**Actor:** Priya · **Trigger:** "Drive shaft, 5.5 kW at 90 rpm, sprocket overhung 80 mm, two bearings 400 mm apart."
1. ✱ Reactions from the layout → bearing loads.
2. Shaft fatigue at shoulder and keyway; key; bearing selection (works today, unchained).
3. ✱ Chain: torque and reactions flow automatically; editing power updates everything.

### UC-7 — Load change in rev B (change management)
**Actor:** Marco · **Trigger:** "Peak load goes up 20 %."
1. ✱ Updates the load case once.
2. ✱ All dependent results flagged stale; one click re-runs; three checks now fail.
3. ✱ Delta report lists what changed and what now fails.

### UC-8 — Bolt loosening in the field (series, root cause)
**Actor:** quality / design engineer · **Trigger:** "M8 bolts on the motor bracket are loosening after 200 h."
1. Copilot lists likely root causes ranked (insufficient preload, transverse slip, embedding,
   short clamp length, missing locking) and the discriminating checks.
2. Runs bolted joint with the actual joint; shows residual clamp vs transverse load (slip).
3. Recommends fix options with computed margins (larger size, higher class, longer clamp, dowel).

### UC-9 — Cost-down request (series)
**Actor:** Marco · **Trigger:** "Purchasing wants 8.8 instead of 10.9 on all bracket bolts."
1. ✱ Finds every calc in the project using those bolts.
2. Re-runs each with 8.8; reports which still pass and their new margins.
3. ✱ Exports a re-verification report for the change request.

### UC-10 — Tolerance stack for bearing preload (detail)
**Actor:** Priya · **Trigger:** "Housing, two bearings, spacer and circlip: will axial play be 0.05–0.15 mm?"
1. ✱ Builds the stack from the dimensions given, worst case and RSS.
2. ✱ Shows contributors ranked; suggests which tolerance to tighten.
