import os

from dotenv import load_dotenv

from appdata import env_path  # noqa: E402

load_dotenv(env_path())

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

import copilot  # noqa: E402
from database import init_db  # noqa: E402
from routers.calculators import router as calculators_router  # noqa: E402
from routers.materials import router as materials_router  # noqa: E402
from routers.reporting import router as reporting_router  # noqa: E402
from routers.sessions import router as sessions_router  # noqa: E402
from routers.settings import router as settings_router  # noqa: E402

app = FastAPI(title="MechCopilot API", version="1.0.0")

_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router, prefix="/api")
app.include_router(calculators_router, prefix="/api")
app.include_router(materials_router, prefix="/api")
app.include_router(reporting_router, prefix="/api")
app.include_router(settings_router, prefix="/api")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/status")
def api_status():
    """Which language model is active (shown in the UI)."""
    return copilot.status()


# The desktop app serves the built frontend from the same address as the API (one process,
# no separate web server). Mounted last so every API route above takes precedence.
WEB_DIR = os.getenv("MECH_WEB_DIR")
if WEB_DIR and os.path.isdir(WEB_DIR):
    from fastapi.staticfiles import StaticFiles  # noqa: E402

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
else:
    @app.get("/")
    async def root():
        return {"message": "MechCopilot API is online", "docs": "/docs"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8001")))
