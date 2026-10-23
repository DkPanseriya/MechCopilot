import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

import copilot  # noqa: E402
from database import init_db  # noqa: E402
from routers.calculators import router as calculators_router  # noqa: E402
from routers.materials import router as materials_router  # noqa: E402
from routers.reporting import router as reporting_router  # noqa: E402
from routers.sessions import router as sessions_router  # noqa: E402

app = FastAPI(title="MechPartner API", version="1.0.0")

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


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
async def root():
    return {"message": "MechPartner API is online", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/status")
def api_status():
    """Which language model is active (shown in the UI)."""
    return copilot.status()


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8001")))
