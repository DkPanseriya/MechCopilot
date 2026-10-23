@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
echo.
echo   MechPartner - mechanical design copilot
echo   ---------------------------------------

where python >nul 2>nul || (echo Python 3.10+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
where npm >nul 2>nul || (echo Node.js 20+ is required: https://nodejs.org/ & pause & exit /b 1)

if not exist backend\.env (
    copy backend\.env.example backend\.env >nul
    echo.
    echo   Paste your Replicate API token ^(starts with r8_^) and press Enter.
    echo   Get one at https://replicate.com/account/api-tokens
    echo   Or just press Enter to run in offline mode ^(calculators only^).
    set "TOKEN="
    set /p "TOKEN=  Token: "
    if defined TOKEN (
        powershell -NoProfile -Command "$t='!TOKEN!'.Trim(); (Get-Content backend/.env) -replace 'REPLICATE_API_TOKEN=.*', ('REPLICATE_API_TOKEN=' + $t) | Set-Content -Encoding utf8 backend/.env"
        echo   Saved to backend\.env
    )
)

if not exist .venv (
    echo Creating Python environment...
    python -m venv .venv || (echo Could not create the virtual environment. & pause & exit /b 1)
)
echo Checking Python packages...
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r backend\requirements.txt || (echo pip install failed. & pause & exit /b 1)

if not exist frontend\node_modules (
    echo Installing frontend packages ^(first run only^)...
    pushd frontend
    call npm install || (popd & echo npm install failed. & pause & exit /b 1)
    popd
)

rem Production frontend by default (fast page loads). "start.bat dev" runs the hot-reload dev server.
set "MODE=prod"
if /i "%~1"=="dev" set "MODE=dev"

if "%MODE%"=="prod" (
    powershell -NoProfile -Command "$b='frontend/.next/BUILD_ID'; if (-not (Test-Path $b)) { exit 1 }; $t=(Get-Item $b).LastWriteTime; $changed=Get-ChildItem frontend/app,frontend/components,frontend/lib,frontend/types -Recurse -File | Where-Object { $_.LastWriteTime -gt $t } | Select-Object -First 1; if ($changed -or (Get-Item frontend/package.json).LastWriteTime -gt $t -or (Get-Item frontend/next.config.ts).LastWriteTime -gt $t) { exit 1 } else { exit 0 }"
    if errorlevel 1 (
        echo Building the frontend ^(first run or code changed, about a minute^)...
        pushd frontend
        call npm run build || (popd & echo Frontend build failed. & pause & exit /b 1)
        popd
    )
)

echo Starting backend on http://127.0.0.1:8001 and frontend on http://localhost:3000 ...
start "MechPartner backend" cmd /k "cd /d "%~dp0backend" && ..\.venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8001"
if "%MODE%"=="prod" (
    start "MechPartner frontend" cmd /k "cd /d "%~dp0frontend" && npm start"
) else (
    start "MechPartner frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
)
timeout /t 8 /nobreak >nul
start "" http://localhost:3000
echo.
echo   Running. Close the two server windows to stop MechPartner.
endlocal
