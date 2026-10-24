# Build the Windows app and installer:
#   1. frontend as static files (frontend/out)
#   2. PyInstaller app folder (dist/MechCopilot)
#   3. Inno Setup installer (dist/MechCopilot-Setup-<version>.exe), if Inno Setup 6 is installed
#
# Usage (repo root, PowerShell):  .\desktop\build.ps1 -Version 1.2.0
# Needs: Python 3.10+ with backend/requirements.txt and desktop/requirements.txt, Node.js 20+.
param(
    [string]$Version = "1.0.0",
    [string]$Python = "python"
)
# Not "Stop": Windows PowerShell 5.1 turns any stderr output of npm/PyInstaller into a fatal
# error. Every native step below checks $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
$Version = $Version.TrimStart("v")
$root = Split-Path $PSScriptRoot -Parent

Write-Host "== Frontend (static export)"
Push-Location (Join-Path $root "frontend")
try {
    $env:MECH_STATIC_EXPORT = "1"
    if (-not (Test-Path node_modules)) { npm ci; if ($LASTEXITCODE) { throw "npm ci failed" } }
    npx next build
    if ($LASTEXITCODE) { throw "frontend build failed" }
} finally {
    Remove-Item Env:MECH_STATIC_EXPORT -ErrorAction SilentlyContinue
    Pop-Location
}

Write-Host "== App folder (PyInstaller)"
& $Python -m PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot "MechCopilot.spec") `
    --distpath (Join-Path $root "dist") --workpath (Join-Path $root "build")
if ($LASTEXITCODE) { throw "PyInstaller failed" }

Write-Host "== Installer (Inno Setup)"
$iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
              "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $iscc) {
    Write-Warning "Inno Setup 6 not found: skipped the installer. The app is in dist\MechCopilot\MechCopilot.exe."
    exit 0
}
& $iscc "/DAppVersion=$Version" (Join-Path $PSScriptRoot "installer.iss")
if ($LASTEXITCODE) { throw "Inno Setup failed" }
Write-Host "Installer: dist\MechCopilot-Setup-$Version.exe"
