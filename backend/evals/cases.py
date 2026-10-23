"""Evaluation questions with what a good answer must contain.

Reference values are hand calculations (shown in the comments), not copies of
calculator output, so a wrong calculator or a wrong input mapping shows up here.

A case may carry "history" (earlier turns) to test follow-ups.

expect keys (all optional):
  asks                  True if the copilot must ask for missing details first
                        (any other case fails when it asks)
  calculators_any       one of these calculators must run ([] = none should run)
  finds_passing_design  at least one run of those calculators passes
  answer_values         [(target, rel_tol)] numbers the answer must quote;
                        target may be a list of alternatives (e.g. mm or in)
  must_mention_any      at least one of these terms appears in the answer
  must_not_mention      none of these appear
  min_grounding         share of answer numbers traced to results (default 0.9)
  format                False to skip the bold-first-line check
"""

CASES = [
    {
        "id": "bolt_select",
        "question": "Which bolt should I use to clamp two 10 mm steel plates with a 9 kN separating load? "
                    "Give me the tightening torque.",
        "expect": {"calculators_any": ["fastener_selector", "bolted_joint"], "finds_passing_design": True,
                   "must_mention_any": ["N·m", "Nm", "N m"]},
    },
    {
        "id": "bolt_torque_m16",
        # VDI 2230 table, M16 8.8, muG = muK = 0.12: MA ≈ 206-210 N·m, FM ≈ 81 kN
        "question": "Tightening torque and preload for an M16 8.8 bolt, oiled, friction 0.12?",
        "expect": {"calculators_any": ["bolt_preload_torque", "fastener_lookup"],
                   "answer_values": [([206, 210], 0.04)]},
    },
    {
        "id": "bearing_select",
        "question": "Select a deep groove ball bearing for a 30 mm shaft: 3.5 kN radial, 0.8 kN axial, "
                    "1450 rpm, 25,000 h life.",
        "expect": {"calculators_any": ["bearing_selector", "bearing_required_c"], "finds_passing_design": True},
    },
    {
        "id": "bearing_life_6205",
        "question": "What is the L10 life of a 6205 bearing at 2 kN radial load and 3000 rpm?",
        "expect": {"calculators_any": ["bearing_life"], "must_mention_any": ["6205"]},
    },
    {
        "id": "beam_ipe200",
        # w = 12 kN/m, L = 4 m: M = wL²/8 = 24 kN·m; I = 1943 cm⁴, E = 210 GPa:
        # δ = 5wL⁴/(384EI) = 9.8 mm < L/250 = 16 mm
        "question": "Check an IPE 200 in S355, 4 m simply supported, carrying 12 kN/m. Is deflection OK for L/250?",
        "expect": {"calculators_any": ["beam_analysis", "beam_profile_selector"],
                   "answer_values": [(9.8, 0.05)]},
    },
    {
        "id": "cantilever_imperial",
        # I = 2⁴/12 = 1.333 in⁴, E = 29e6 psi, L = 72 in: δ = PL³/(3EI) = 0.644 in = 16.4 mm
        "question": "A 6 ft steel cantilever, 2 in x 2 in solid square bar, 200 lbf at the tip. Tip deflection?",
        "expect": {"calculators_any": ["beam_analysis"], "answer_values": [([0.644, 16.4], 0.05)]},
    },
    {
        "id": "column_euler",
        # d = 40 mm: I = 125 664 mm⁴, r = 10 mm, λ = 200 (Euler range for S235)
        # Pcr = π²EI/L² = 65.1 kN, so 50 kN leaves a factor of only 1.3
        "question": "Will a 2 m long, 40 mm solid round S235 bar, pinned at both ends, buckle under 50 kN?",
        "expect": {"calculators_any": ["column_buckling"], "answer_values": [(65.1, 0.03)]},
    },
    {
        "id": "vessel_hoop",
        # thin wall: σθ = pD/(2t) = 1 MPa · 500 / 16 = 31.3 MPa (30.8-31.8 with mean/outer diameter)
        "question": "Hoop stress in a 500 mm diameter tank with 8 mm wall at 10 bar?",
        "expect": {"calculators_any": ["pressure_vessel"], "answer_values": [(31.3, 0.04)]},
    },
    {
        "id": "shaft_fatigue",
        "question": "Size a C45 shaft for 350 N·m torque and 180 N·m bending with a shoulder fillet, "
                    "fatigue safety factor 2.",
        "expect": {"calculators_any": ["shaft_fatigue"], "finds_passing_design": True},
    },
    {
        "id": "press_fit",
        "question": "What fit should I use to press a steel gear onto a 40 mm shaft so it transmits 200 N·m "
                    "without a key?",
        "expect": {"calculators_any": ["interference_fit", "iso_fits"],
                   "must_mention_any": ["H7"]},
    },
    {
        "id": "key_check",
        "question": "Check a DIN 6885 parallel key on a 40 mm shaft transmitting 300 N·m, hub length 50 mm, steel hub.",
        "expect": {"calculators_any": ["parallel_key"]},
    },
    {
        "id": "weld_group",
        "question": "6 mm fillet weld all around a 100 x 100 mm square tube welded to a plate, "
                    "20 kN shear at 150 mm from the weld. Is it OK in S355?",
        "expect": {"calculators_any": ["fillet_weld"]},
    },
    {
        "id": "gear_pair",
        "question": "Spur gear pair, module 3, 20 and 60 teeth, 30 mm face width, 15 kW at 1450 rpm on the pinion. "
                    "Check bending and contact.",
        "expect": {"calculators_any": ["spur_gear"]},
    },
    {
        "id": "concept",
        "question": "Remind me how bending and torsion combine on a shaft.",
        "expect": {"must_mention_any": ["von Mises", "Tresca", "equivalent"], "format": False,
                   "min_grounding": 0.7},
    },
    {
        "id": "advice_8_8_vs_10_9",
        "question": "What's the practical difference between 8.8 and 10.9 bolts, when should I pick which?",
        "expect": {"calculators_any": ["fastener_lookup", "bolt_preload_torque"],
                   "must_mention_any": ["embrittlement", "proof", "yield"]},
    },
    {
        "id": "underspecified",
        "question": "I need a bearing for my shaft.",
        "expect": {"asks": True, "calculators_any": [], "format": False},
    },
    {
        "id": "start_bolted_joint",
        "question": "I'm working on a bolted joint.",
        "expect": {"asks": True, "calculators_any": [], "format": False},
    },
    {
        "id": "answers_after_asking",
        "question": "Radial load: 3.5 kN; Axial load: 0.8 kN; Speed: 1450 rpm; Shaft diameter: 30 mm. "
                    "Use typical values for anything else.",
        "history": [{"role": "user", "content": "I need a bearing for my shaft."},
                    {"role": "assistant", "content": "I'll select a bearing.", "tool_data": {"clarify": {
                        "questions": [{"label": "Radial load"}, {"label": "Axial load"},
                                      {"label": "Speed"}, {"label": "Shaft diameter"}]}}}],
        "expect": {"calculators_any": ["bearing_selector"], "finds_passing_design": True},
    },
    {
        "id": "price_out_of_scope",
        "question": "How much does an SKF 6206-2RSH cost?",
        "expect": {"must_not_mention": ["$", "€", "USD", "EUR", "₹"],
                   "must_mention_any": ["distributor", "supplier", "quote", "price"], "format": False},
    },
]
