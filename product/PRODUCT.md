# Mechanical Design Partner - Product Bible

**Version**: 2.0 (Reboot)  
**Status**: Planning Phase  
**Focus**: Web-First → CAD-Integrator  

---

## 1. Product Vision
To create a **collaborative AI partner** for mechanical engineers that evolves from a "smart handbook" (Web) to a "workflow automator" (CAD Plugin). 
The goal is **2-way collaboration**: The user brings the problem, the AI brings the method, verification, and experience.

---

## 2. Phased Roadmap

### Phase 1: The Intelligent Web Studio (Weeks 1-6)
**Objective**: Build a user base with a free, high-utility web tool that "feels" magic.

#### Core Features
1.  **The "Expert" Chat Intent**:
    *   System prompts designed for "Engineering Rigor".
    *   Differentiates between "Concept Explanation" (Student mode) and "Design Verification" (Pro mode).
2.  **Dynamic UI Generation**:
    *   Constraint: Don't hardcode 100 calculators.
    *   Solution: AI generates the calculator UI *schema* based on the user's specific problem.
    *   *Example*: User asks for "Press fit calculation for a user-defined hub". AI renders a React component with exactly those inputs.
3.  **Visual Explanations**:
    *   Charts/Graphs via Recharts or D3, generated on the fly.
4.  **Voice Mode (Nice to have)**:
    *   Web Speech API for hands-free "thinking out loud".

### Phase 2: The CAD Copilot (Weeks 7-12)
**Objective**: Integrate into the professional workflow (Monetization Driver).

#### Core Features
1.  **SolidWorks Task Pane Add-in**:
    *   Embedded Chromium browser or Native .NET UI.
    *   Connects to the same backend as the Web App.
2.  **Context Reading**:
    *   "See" the active model.
    *   Extract: Material, Mass, Volume, Center of Mass.
    *   *User Query*: "Is this material strong enough for a 5kN load?" -> AI reads material Yield Strength directly from CAD.
3.  **Proactive Alerts**:
    *   Watchdog mode: "Warning: Mass has exceeded 5kg limit."

### Phase 3: Automation & Macros (Future)
*   Text-to-CAD: "Fillet all sharp edges with 2mm radius."
*   Assembly Mating assistance.

---

## 3. Monetization & Business Model

**The Hook (Free Tier)**:
*   Access to the Web Interface.
*   Unlimited Q&A.
*   Dynamic Calculators (Session storage only).
*   *Why*: Replaces Google/WolframAlpha/EngineersEdge for the daily user.

**The Retainer (Pro Tier - $20-30/mo)**:
*   **CAD Integration Plugin**: The killer feature. Saves context switching.
*   **Project Context**: "Remember the safety factors we set for Project X".
*   **Report Generation**: "Write a PDF summary of our shaft analysis for my manager."
*   **Private RAG**: Upload "My Company Design Guide.pdf" and validate against it.

---

## 4. User Experience (UX) Principles

1.  **Trust but Verify**: Always show the formula and the source.
2.  **Proactive, not Passive**: Don't just wait for a prompt. If the user calculates a bolt stress, *ask* "Did you check for fatigue loading?"
3.  **Aesthetic Excellence**: Dark mode, crisp typography, clean inputs. Engineers appreciate precision.

---

## 5. Technical Decision Log (Live)

| Component | Choice | Rationale |
| :--- | :--- | :--- |
| **Frontend** | Next.js (React) | Standard for modern, performant web apps. Easy transition to Electron/Desktop if needed later. |
| **Styling** | TailwindCSS + Shadcn/UI | Rapid dev, professional "Vercel-like" look. |
| **Backend** | FastAPI (Python) | Best for AI/Agent orchestration. |
| **Agent State** | LangGraph / Vercel AI SDK | Need to manage conversation state + "UI Component" generation messages. |
| **CAD Bridge** | Localhost HTTP | Simplest way to talk between C# Add-in and Python Backend. |

---

## 6. Success Metrics
*   **Acquisition**: 100 Weekly Active Users (WAU) on Web App.
*   **Activation**: Users perform >3 distinct calculations/conversations per session.
*   **Retention**: User returns within 48 hours.
*   **Conversion**: 5% of active users download/waitlist the CAD Plugin.
