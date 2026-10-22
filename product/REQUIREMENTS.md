# Requirements Specification
**Project**: Mechanical Design Partner (AI Copilot)

---

## 1. Functional Requirements (Phase 1: Web)

### FR-01: Expert Chat & Context
*   **FR-01.1**: User shall interact via natural language (Text/Voice).
*   **FR-01.2**: System must classify user intent.
*   **FR-01.3**: System must be able to adopt specific personas.

### FR-02: Dynamic Calculator Generation
*   **FR-02.1**: System shall NOT rely solely on hardcoded forms.
*   **FR-02.2**: Upon identifying a calculation request, System must generate a UI Schema.
*   **FR-02.3**: Frontend must render this schema as a functional, interactive card.
*   **FR-02.4**: User must be able to edit parameters and see real-time updates.

### FR-03: Proactive Suggestion Engine
*   **FR-03.1**: System must analyze user queries for missing safety checks.
*   **FR-03.2**: Example: If user checks 'Static Stress', System must suggest 'Fatigue Check'.

### FR-04: Session Persistence
*   **FR-04.1**: (Free) History retained for active browser session.
*   **FR-04.2**: (Pro) History saved to user account database.

---

## 2. Functional Requirements (Phase 2: CAD Integration)

### FR-CAD-01: SolidWorks Connect
*   **FR-CAD-01.1**: Add-in must load in SolidWorks Task Pane.
*   **FR-CAD-01.2**: Add-in must authenticate with User Account.

### FR-CAD-02: Read-Only Context
*   **FR-CAD-02.1**: System must be able to read active Part/Assembly properties.
*   **FR-CAD-02.2**: System must be able to read basic feature tree data.

---

## 3. Non-Functional Requirements

### NFR-01: Experience & Latency
*   **NFR-01.1**: 'Thinking' state must be visible and encouraging.
*   **NFR-01.2**: Dynamic UI generation should take < 3 seconds.
*   **NFR-01.3**: Voice-to-Text latency should be < 500ms.

### NFR-02: Accuracy & Trust
*   **NFR-02.1**: All generated calculations MUST display the governing formula in LaTeX.
*   **NFR-02.2**: All data assertions MUST cite a source.
*   **NFR-02.3**: If AI is uncertain, it must state 'Estimated'.

### NFR-03: Design Aesthetics
*   **NFR-03.1**: UI must follow modern 'Dark Mode' aesthetic.
*   **NFR-03.2**: Smooth animations for state transitions.

---

## 4. Technical Constraints
*   **TC-01**: Web App must be responsive.
*   **TC-02**: CAD Plugin must support SolidWorks 2022+.
