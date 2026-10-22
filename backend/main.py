from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from agent import router as agent_router
from routers.sessions import router as sessions_router
from routers.workflow import router as workflow_router
from routers.materials import router as materials_router
from routers.reporting import router as reporting_router
from routers.compute import router as compute_router
from database import init_db

app = FastAPI(title="Mechanical Design Partner API", version="0.1.0")

# CORS (Allow Frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")
app.include_router(materials_router, prefix="/api")
app.include_router(reporting_router, prefix="/api")
app.include_router(compute_router, prefix="/api")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/")
async def root():
    return {"message": "Mechanical Design Partner API is Online"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
