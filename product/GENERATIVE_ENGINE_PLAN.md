# Generative Engineering Engine — Analysis & Plan

**Status**: Proposal · **Date**: 2026-10-22
**Goal**: On-the-fly calculators, stackable calculations, data-driven selectors (bearings/fasteners), load calculators, and visuals — a composable "design canvas" for mechanical engineers.

---

## Part 1 — How ChatGPT's generative UI actually works

The single most important finding: **ChatGPT does not generate UI code on the fly.** It is not the model writing HTML/JS per response. Two paradigms exist, and both share one pattern.

### A. OpenAI Apps SDK (the ChatGPT "Apps")
- A developer ships an **MCP server** that registers a **widget resource** (`ui://…`, MIME `text/html+skybridge`) and links it to a tool via `openai/outputTemplate` metadata.
- When the model calls the tool, it returns three parts:
  - `structuredContent` — model-readable data that hydrates the widget
  - `content` — narration text
  - `_meta` — widget-only data the model never sees (keeps bulky data out of context)
- The widget is a **pre-built, compiled React bundle**. The model chooses *which* widget and supplies *data*. It never authors the UI.

### B. Vercel AI SDK "Generative UI"
- Model tool-calls map to an **allowlisted catalog of React components**, streamed into chat. Model picks a component + fills **typed props** (Zod/JSON-schema validated). Still no raw markup from the model.

### The shared pattern (this is the whole lesson)
> **Model selects from a component registry and fills typed, validated props. The server does the compute. Rendering is sandboxed. No codegen.**

This buys **determinism** (same inputs → same UI/result), **safety** (no arbitrary code), and **correctness** (engineering math runs in trusted server code, not model-authored JS).

### Rendering & sandbox
- Widgets render in a **sandboxed iframe** under strict CSP (no `alert`/`clipboard`/network escape).
- Bridge (`window.openai`): widget reads `toolOutput`, persists small state via `setWidgetState` (<4k tokens — it's shown to the model), calls server tools via `callTool`, can send follow-up chat messages.
- MCP transport is stateless → heavy state lives server-side and streams over SSE.

### Production notes from the research
- `streamText` + `useChat` is the recommended production path.
- RSC `streamUI` is **experimental/paused** (flicker on `.done()`, no server-action abort) — avoid.
- **RJSF** (react-jsonschema-form) is a viable schema→form renderer. **Zod** for typed tool I/O.
- Always validate model-supplied inputs server-side; gate irreversible actions behind human confirmation.

Sources: OpenAI Apps SDK (security-privacy, build/chatgpt-ui), Vercel AI SDK 3 Generative UI, AI SDK RSC→UI migration notes, Alpic/MCPJam/Agnost teardowns.

---

## Part 2 — Current Mech Copilot teardown (objective critique)

The code and the product docs disagree badly. The docs describe an aspirational stack; the code is something else.

### What the docs claim vs. what exists
| Docs say | Code actually uses |
| :-- | :-- |
| GPT-4o + Vision | Replicate **Llama 3 8B / 70B** |
| LangGraph / Vercel AI SDK orchestration | Hand-rolled SSE + regex JSON extraction |
| Supabase/Postgres + ChromaDB RAG | SQLite (`database.py`), no vector store |
| Structured tool calling | Prompt-and-pray JSON with 4 repair strategies |

### Critical problems

**1. Arbitrary LLM code execution in the browser (security).**
`ToolCard.tsx` runs `new Function(...tool.formula_js)` — raw JavaScript authored by the model, executed in the user's browser. This is a remote-code-execution surface and a determinism hole. The return value is sniffed by guessing variable names (`stress`/`result`/`output`). **This must be removed entirely**, not patched.

**2. Four calculation engines, mutually inconsistent.**
- `formula_js` → browser `new Function()` (unit-blind `parseFloat`)
- `calculations.py::perform_calculation` → **fuzzy string-match** over 4 hardcoded functions — directly violates FR-02.1 ("shall NOT rely on hardcoded forms")
- `physics_kernel.py` → SymPy + Pint over 12 `RELATIONS` (the *good* one), used by `/workflow/step`
- The manifest the LLM sees comes from the kernel, but the LLM is told to emit `formula_js` — so the trustworthy engine and the model output are **disconnected**.

**3. Unit propagation is broken in the one good engine.**
`physics_kernel.solve()` returns raw SI magnitude and the workflow router hardcodes `unit: "SI_derived"` / `"SI_base"` (TODOs admit it). So stacked results carry no real units — fatal for engineering trust (NFR-02).

**4. Fragile model contract.**
`llm_utils.parse_llm_response` brace-balances and regex-repairs JSON because an 8B model emits malformed output. The entire dynamic-UI feature rests on scraping JSON from a chatty small model with **no structured-output or tool-calling guarantee**.

**5. Wiring bug.**
`chat/[id]/page.tsx` fetches `localhost:8000`; `main.py` serves `8001`; `ToolCard` fetches `8001`; CORS allows `3000`. The chat path points at the wrong port.

**6. Generative-UI scope is one card.**
Only a single calculator widget + a linear workflow. No charts, no selectors, no composable canvas. Bearing/fastener "selectors" aren't formulas at all — they're **data-driven lookups with constraint filtering**, which the current formula-centric design can't express.

### What's actually good (keep & build on)
- `physics_kernel` symbolic solve (SymPy) — solve-for-any-variable is the right primitive.
- Pint unit registry already in the dependency set.
- Workflow "steps reference prior step output" is the seed of a real DAG.
- Clean Tailwind/Shadcn UI, dark mode, KaTeX formula rendering, SSE streaming scaffold.

---

## Part 3 — Target architecture

Adopt the ChatGPT/Vercel pattern, specialized for engineering.

```
User ↔ Chat (Next.js)
          │  SSE
          ▼
   Orchestrator (LLM, TOOL-CALLING)         ← picks widgets, fills typed props
          │  emits UISpec (validated)
          ▼
   Widget Registry (frontend)               ← fixed catalog, renders by `type`
          │  user edits inputs
          ▼
   Compute Kernel (backend, authoritative)  ← SymPy + Pint, deterministic
          │
   Data Services: bearings, fasteners, materials, standards (RAG)
```

### Three hard rules
1. **Model never authors executable code or markup.** It only emits a validated `UISpec` (JSON) choosing a registry component + typed props. Kill `formula_js`.
2. **All compute is server-side and unit-correct.** One kernel. SymPy for symbolic solve, Pint for units end-to-end (fix the unit-output bug first — it blocks everything downstream).
3. **Everything is a node on a canvas.** A calculator, a selector, a chart, a load case — all are typed nodes. Nodes can wire outputs→inputs. "Stacking calculations" = a DAG of nodes.

### The widget registry (initial catalog)
- `calculator` — inputs + governing formula (LaTeX) + unit-aware result
- `workflow` / `canvas` — DAG of calculator/selector nodes with wired dependencies
- `selector` — data-driven table with constraint filters (bearings, fasteners)
- `chart` — Recharts line/bar/scatter (e.g. S-N curve, load vs. deflection)
- `comparison` — side-by-side option table with a recommendation
- `load-case` — combine forces/moments → reactions → feed downstream nodes

Frontend renders strictly by `spec.type`. Unknown type → graceful fallback, never `eval`.

### The UISpec contract (replaces `DynamicTool`)
A single discriminated-union schema (Zod on the client, Pydantic on the server), e.g.:
```jsonc
{ "type": "calculator",
  "title": "Tapered Shaft Bending Stress",
  "relation": "bending_stress",          // MUST reference a kernel relation, not JS
  "inputs": [{ "name": "M", "label": "Moment", "unit_type": "torque", "default": 500 }],
  "solve_for": "sigma",
  "output_unit": "MPa",
  "citations": ["Shigley §3-10"],
  "suggestions": ["Check fatigue (S-N) at the fillet"] }
```

### Model layer
- Move to a **tool-calling / structured-output capable model** (hosted GPT-4-class or a local model with grammar-constrained JSON). Delete the regex-repair parser.
- Orchestrator tools: `propose_widget`, `lookup_bearing`, `lookup_fastener`, `lookup_material`, `solve_relation`, `add_relation` (register a new vetted formula).
- Extensibility without hardcoding 100 calculators: the kernel exposes a **relation library**; the model composes existing relations or proposes a new relation *definition* (symbolic equation + variables + units) that the kernel validates and runs — the model still never executes code.

---

## Part 4 — Subsystems

### 4.1 Generative calculator (on the go)
Model emits a `calculator` UISpec referencing a kernel relation (existing or newly-proposed-and-validated). Server solves with Pint units. Formula shown in LaTeX, result unit-correct, source cited.

### 4.2 Stacking engine (the differentiator)
Promote the linear workflow to a **node graph**:
- Each node = {relation, inputs, solve_for, output as a typed Quantity}.
- Edges wire `nodeA.output → nodeB.input`; units checked at the edge (dimension mismatch = explicit error, not silent).
- Re-evaluation is topological; editing any input recomputes downstream.
- Example chain: *load case → bending moment → bending stress → factor of safety → fatigue check*, all live.

### 4.3 Selectors (bearings, fasteners) — data, not formulas
- Seed catalog tables (SKF/ISO bearing designations with C/C0 ratings; ISO metric fastener grades with proof/tensile).
- `selector` widget = filter by constraints (bore, dynamic load, life target) → ranked candidates → selected part's properties flow into downstream nodes (e.g. bearing basic rating life L10, bolt preload).
- This is a lookup + constraint-satisfaction service, wired into the same canvas.

### 4.4 Load calculators & visuals
- Load-case node composes forces/moments → reactions.
- `chart` widget renders S-N curves, load-deflection, interaction diagrams via Recharts.

---

## Part 5 — Phased implementation

**Phase 0 — Stabilize & de-risk (small, do first)**
- Remove `formula_js` + `new Function()` from `ToolCard`. (security)
- Fix the `:8000`/`:8001` port mismatch. (wiring)
- Fix Pint unit output in `physics_kernel.solve()` + `/workflow/step` (return real units). (trust)
- Collapse `calculations.py` fuzzy dispatch into the kernel — one engine.

**Phase 1 — Typed contract**
- Define `UISpec` discriminated union (Pydantic + Zod, shared shape).
- Swap model layer to tool-calling / structured output; delete regex JSON repair.
- Frontend renders from the registry by `type`.

**Phase 2 — Node canvas (stacking)**
- Generalize workflow → DAG with unit-checked edges, topological recompute.
- Canvas UI: drag/wire nodes, live downstream updates.

**Phase 3 — Selectors + data**
- Bearing & fastener catalogs + `selector` widget + constraint filtering.
- Materials service hardened; standards RAG (the Pro-tier hook).

**Phase 4 — Visuals & reports**
- `chart` + `comparison` widgets.
- Export canvas → PDF/Excel calc report (Pro tier).

---

## Part 6 — Open questions for you
1. **Model**: hosted GPT-4-class (best tool-calling, cost) vs. local/Replicate (privacy, cheaper, weaker JSON)? This decision gates Phase 1.
2. **Compute authority**: all server-side (recommended, trustworthy) vs. some client-side for latency? Recommend server-authoritative.
3. **Selector data source**: license real SKF/ISO catalogs, or start with generic representative data + clear "estimated" labeling?
4. **Canvas vs. cards**: full node-graph canvas (ambitious) vs. stacked-card list (faster to ship)? Recommend stacked cards in Phase 2, graph later.

---

## Part 7 — The libraries we build (inventory)

The core bet: mechanical design is a **finite, well-defined set of primitives** (formulas, figures, render types, selectors) that the LLM *composes*. We build the primitives once; the model mixes and matches. Four libraries.

### 7.1 Formula / Relation Library (the trusted kernel)
Strength-of-materials + mechanics is a bounded set (~30-40 relations cover undergrad + most practical design). Each relation = a symbolic equation + per-variable physical dimension + LaTeX + category. Solve-for-any-variable, unit-correct, server-side. This is the thing everything else stacks on.

**Stress**
- Axial/normal `σ = F/A` · direct shear `τ = F/A` · bearing/crushing `σ = F/(d·t)`
- Bending `σ = M·y/I`, `σ = M/Z` · transverse shear `τ = V·Q/(I·b)`
- Torsion (solid shaft) `τ = 16T/(πd³)`, general `τ = T·r/J` · angle of twist `θ = T·L/(G·J)`
- Thin pressure vessel: hoop `σ = p·d/2t`, longitudinal `σ = p·d/4t`
- Thermal `σ = E·α·ΔT`

**Section properties** (feed the stress relations)
- Area, centroid · `I` (rect `b·h³/12`, solid circle `πd⁴/64`, hollow, I-beam) · `J` (circle `πd⁴/32`) · section modulus `Z = I/c`

**Deflection / stiffness**
- Axial `δ = F·L/(A·E)` · beam cases (cantilever & simply-supported, point & UDL) · torsional twist (above)

**Combined loading** (explicit ask — bending+torsion etc.)
- Superposition (bending + axial) · plane-stress transform / principal `σ₁,₂ = (σx+σy)/2 ± √(((σx−σy)/2)²+τxy²)` · max shear `τmax = √(((σx−σy)/2)²+τxy²)` · von Mises `σ' = √(σx²−σxσy+σy²+3τxy²)` · equivalent stress on shaft (bending+torsion) `σ' = √(σb²+3τt²)`

**Failure / safety**
- Factor of safety `n = S/σ'` · Euler buckling `Pcr = π²EI/(Le)²`, slenderness · fatigue: endurance limit w/ Marin factors, stress-concentration `Kt`, Goodman/Soderberg

**Material relations**
- Hooke `σ = E·ε` · shear modulus `G = E/(2(1+ν))` · Poisson

> Novel formula path: when the model needs something outside the set, it proposes a *relation definition* (equation + variable dimensions), the kernel parses (SymPy) and dimensionally validates it before use. The model still never executes code.

### 7.2 Component / Widget Library (render types)
Fixed catalog the frontend renders by `type`; model only fills typed props.
1. `calculator` — one relation, unit-aware inputs/result, LaTeX
2. `canvas` / `stack` — DAG of nodes, outputs wired to inputs (the "solve complex problem by stacking")
3. `selector` — data table + constraint filter (bearing, fastener)
4. `chart` — parametric sweep / S-N / load-deflection (Recharts)
5. `figure` — annotated engineering diagram (see 7.3)
6. `comparison` — options table + recommendation
7. `load-case` — forces/moments → reactions, feeds downstream
8. `material-card` — property lookup

### 7.3 Figure / Diagram Library (concept revisit — key ask)
Canonical **annotated SVG diagrams** so "remind me how bending+torsion combine on a shaft" returns *figure + annotations + formula + calculator + minimal theory* in one scannable block. Finite reusable set (~20-25): shaft under bending+torsion, stress element / Mohr's circle, beam loading cases & BMD/SFD, bolted joint (preload/shear), bearing arrangement & load zones, pressure vessel stresses, column buckling modes, fillet stress concentration, weld joints, gear tooth loads.
- Authored once as parameterized SVG; the model references a `figure_id` and may overlay the user's values on annotation anchors. Not AI-drawn (determinism + correctness).

### 7.4 Selector services (data-driven, not formulas)
- **Bearing**: **Verified — SKF has no public self-serve API and no embeddable widget.** The only SKF API is bound to Ansys Mechanical (stiffness for FEA, not selection/life); KISSsoft/MESYS access SKF data only under partnership. So "just integrate SKF's API" is not viable without a partner agreement. **Decision: build ISO 281 ourselves.** Public & implementable: `L10 = (C/P)^p` (p=3 ball, 10/3 roller), modified life `Lnm = a1·aISO·L10`, `L10h = 10⁶/(60n)·L10`, equiv. load `P = X·Fr + Y·Fa`, static safety `s0 = C0/P0`. Proprietary (cannot reproduce): SKF's `aSKF` curves and per-designation `C/C0/Pu` catalog values → ingest from user input or a licensed/seeded catalog, and label SKF-specific results "estimated." Pursue an SKF partnership later only if bearing selection becomes a headline feature.
- **Fastener**: fully buildable ourselves (ISO metric). Preload `Fi = 0.9·At·Sp` (or 0.75), torque `T = K·Fi·d` (K≈0.2), stress area `At`, proof/yield/tensile checks, shear & combined. Input load type + force → recommend grade/size.

### 7.5 How the LLM selects & composes (the contract)
1. **Manifest** given to the model: relation IDs (+ variables, dimensions), widget types, figure IDs, selector services, material keys.
2. Model emits a **validated `UISpec`** (tool-call or JSON) = a *composition*, e.g. "shaft bending+torsion" →
   `{ figure: "shaft_bending_torsion", stack: [bending_stress, torsional_stress, shaft_equiv_stress, factor_of_safety] wired, chart: sweep σ' over d }`.
3. **Server validates** every relation/figure/selector ref against the libraries, computes with units, returns a hydrated spec. Unknown ref → error, never `eval`.
4. Model orchestrates *which* primitives and *how wired*; the libraries own *what they do*. New capability = add a primitive, not new codegen.

**Library size estimate**: ~35 relations, 8 widget types, ~22 figures, 2 selector services (+ catalog data), ~1 materials table. Bounded and buildable.
