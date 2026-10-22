# Mechanical Design Partner - Product Overview

**"The Expert Co-Pilot in every Design Engineer's workflow"**

---

## 🎯 Vision: From "Tool" to "Partner"

We are NOT building just another calculator or handbook lookup tool.
We are building an **AI Design Partner** that collaborates with engineers.

- **Old Way**: Engineer stops design -> Search Google/Book -> Find Formula -> Calculate in Excel -> Return to CAD.
- **New Way**: Engineer asks "Check this shaft for fatigue" -> AI interacts, understands context, spins up a dynamic calculator, verifies safety factors -> Engineer approves.

### Core Experience
1.  **Collaborative**: Two-way dialogue, not just Q&A. The AI asks clarifying questions.
2.  **Dynamic**: The UI isn't static forms. It *generates* the right interface for the specific problem at hand (e.g., "Here is a custom stress calculator for your tapered shaft").
3.  **Context-Aware**: Understands the user's level (Student vs. Senior Engineer) and the project scale.

---

## 🗺️ Strategic Roadmap

### **Phase 1: The Design Studio (Web App)**
*Goal: User Acquisition & "Wow" Factor*
A web-based "One-Stop Solution" for design engineering.
- **Features**:
    - **Expert Chat**: Physics-aware reasoning (not just text generation).
    - **Dynamic Workspace**: AI generates interactive cards/calculators on the fly.
    - **Proactive Suggestions**: "Have you considered stress concentration at that fillet?"
- **Tech**: Next.js (React), Tailwind, Framer Motion, FastAPI, OpenAI.

### **Phase 2: The CAD Copilot (Integration)**
*Goal: Deep Workflow Integration & Pro Retention*
A companion window inside SolidWorks/Onshape.
- **Features**:
    - **Sidecar Interface**: "GitHub Copilot for Mechanical Design".
    - **Context Awareness**: Reads active CAD file properties (materials, mass, mate references).
    - **Macro Generation**: Automates repetitive CAD modeling tasks.
- **Tech**: SolidWorks API (.NET), Localhost Bridge.

---

## 👥 Target Audience & Personas

**Primary: "The Design Engineer" (Sarah)**
- 3-7 years experience.
- Needs verification/confidence in her decisions.
- **Pain**: Wasted time switching contexts (CAD <-> Excel <-> Handbook).
- **Gain**: "An expert looking over my shoulder."

**Secondary: "The Student/Junior" (Alex)**
- Needs guidance and explanation.
- **Gain**: Accelerated learning curve.

---

## 💰 Monetization Strategy (Freemium)

| Tier | Value Proposition | Features |
| :--- | :--- | :--- |
| **Free (Growth)** | "Better than Google/Handbooks" | • General Engineering Q&A<br>• Dynamic Calculators (Session based)<br>• Public Standards/Material generic data |
| **Pro (Revenue)** | "Your Personal Senior Engineer" | • **SolidWorks/CAD Integration**<br>• Project "Memory" (Context retention)<br>• Company Specific Standards (RAG)<br>• Export Calculation Reports (PDF/Excel) |

---

## 🛠️ Tech Stack Upgrade

To achieve the "Intuitive/Premium" feel:
- **Frontend**: **Next.js + React** (Speed, SEO) + **Framer Motion** (Smooth animations).
- **Backend**: **FastAPI** (Python) + **LangChain/Masters** (Orchestration).
- **AI**: **GPT-4o** (Reasoning) + **Vision** (For analyzing sketches/screenshots).
- **Database**: **Supabase/Postgres** (User data) + **ChromaDB** (Vector RAG).

---

## 📚 Documentation Links
- **[PRODUCT.md](PRODUCT.md)**: Detailed Roadmap & Specs.
- **[REQUIREMENTS.md](REQUIREMENTS.md)**: Functional Requirements.
- **[Implementation Plan](../projects/implementation_plan.md)**: Dev steps.
