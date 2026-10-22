@echo off
echo Starting Services...

start cmd /k "conda activate mech_copilot_v2 && cd backend && python -m uvicorn main:app --reload --port 8001"
start cmd /k "cd frontend && npm run dev"

echo Servers starting...
echo Frontend: http://localhost:3000
echo Backend: http://localhost:8001
