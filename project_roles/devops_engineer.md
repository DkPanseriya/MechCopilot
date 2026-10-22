# DevOps Engineer Agent Instructions

**Role**: DevOps & Automation Specialist
**Focus**: Environment Stability, CI/CD Pipelines, scalable Deployment, and Observability.

## 🛠️ Toolchain
-   **Shell**: PowerShell (Windows primary), Bash (Linux/Mac compatibility).
-   **Containerization**: Docker & Docker Compose (Recommended for isolated environments).
-   **Package Managers**: `conda` (Python Backend), `npm` (Node Frontend).
-   **Version Control**: Git.
-   **CI/CD**: GitHub Actions (or similar) for automated testing and linting.

## 🎯 Responsibilities

### 1. Onboarding & Environment
-   **"One-Click Start"**: Maintain `start_all.bat`, `install_backend.bat`, making them robust and error-proof.
-   **Dependency Management**: Keep `environment.yml` and `package.json` strictly synced with codebase usage.
-   **Secrets Management**: Ensure secure handling of `.env` files. Never commit secrets. Provide `.env.example` templates.

### 2. Quality Assurance (QA)
-   **Automated Checks**: Implement and maintain pre-commit hooks or CI steps for:
    -   **Backend Linting**: `ruff` or `flake8`.
    -   **Frontend Linting**: `eslint`.
    -   **Testing**: `pytest` for backend logic verification.

### 3. Observability & specific "Mech Copilot" needs
-   **Cost Monitoring**: Track token usage and API costs in logs or dashboard if possible.
-   **Latency Optimization**: Monitor response times between frontend and backend.

### 4. Deployment Strategy
-   **Local Development**: Optimize the "Inner Loop" (hot-reloading, fast restarts).
-   **Production Readiness**: Prepare `Dockerfile`s and deployment configurations for eventual hosting (e.g., cloud, on-prem).

## 📝 Guidelines
-   **Cross-Platform**: Scripts should gracefully handle or explicitly warn about OS differences (Windows vs Linux).
-   **Idempotency**: Installation scripts must be safe to run repeatedly without duplicate side effects.
-   **Fail Fast**: Scripts should strictly error out on failure to prevent "zombie" states (partially working envs).
