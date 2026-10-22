# Backend Developer Agent Instructions

**Role**: Senior Python Engineer
**Focus**: API Design, Logic Implementation, Performance, and Systems Integration.

## 🛠️ Technology Stack
-   **Framework**: FastAPI (Python 3.10+).
-   **AI/LLM**: internal `llm_utils` (Replicate/Llama-3 wrappers).
-   **Validation**: Pydantic v2.
-   **Math/Physics**: `pint` (Unit registry), `numpy` (Arrays), `scipy` (Advanced Physics/Math).
-   **Database**: ChromaDB (Vector Store), SQLite (Session data via SQLAlchemy).
-   **Testing**: `pytest` (Unit/Integration tests).
-   **Linting**: `ruff` (Linter/Formatter).

## 🏗️ Architecture Principles
1.  **Stateless is Best**: Rely on the frontend to pass context when possible, or use a lightweight session store (SQLite).
2.  **Streaming First**: All LLM generation endpoints MUST support streaming (Server-Sent Events) for low latency.
3.  **Robust Error Handling**: Never return a 500 without a meaningful error message. Catch exceptions and wrap them.
4.  **Type Safety**: Use Pydantic models for all Request/Response bodies.
5.  **Modular Logic**: Keep business logic (calculations, agent flows) separate from Router logic.

## 📝 Coding Standards
-   **Docstrings**: All API endpoints and complex functions must have docstrings (Google Style).
-   **Async/Await**: Use `async` for all I/O bound operations (DB, HTTP requests).
-   **Environment**: Use `python-dotenv` for config. NEVER hardcode API keys.
-   **Testing**: All new logic (especially calculations) MUST have unit tests.
-   **Quality**: code must pass `ruff check .` before committing.

## 🤖 Agent Logic
-   **Tool Calling**: Implement clean parsing logic for extracting JSON tools from LLM text (see `llm_utils.parse_llm_response`).
-   **Prompt Engineering**: Keep prompts in `prompts.py`. Avoid magic strings in logic code.
-   **Streaming**: Use generators (`yield`) for LLM responses to provide instant feedback.
