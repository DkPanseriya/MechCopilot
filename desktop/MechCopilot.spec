# PyInstaller spec for the MechCopilot desktop app (one folder: dist/MechCopilot/).
# Build with desktop/build.ps1, which first builds the frontend into frontend/out.
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
BACKEND = os.path.join(ROOT, "backend")
WEB = os.path.join(ROOT, "frontend", "out")
if not os.path.isdir(WEB):
    raise SystemExit("frontend/out is missing: build the frontend first (desktop/build.ps1).")

# Backend modules are imported by name at runtime (routers, calculators), so collect them all.
hidden = ["main", "copilot", "database", "appdata"]
for pkg in ("engineering", "routers", "services", "uvicorn", "replicate", "openai", "webview"):
    hidden += collect_submodules(pkg)

a = Analysis(
    [os.path.join(SPECPATH, "launcher.py")],
    pathex=[BACKEND],
    datas=[
        (os.path.join(BACKEND, "data", "materials.json"), "data"),  # read via engineering/../data
        (WEB, "web"),
        *collect_data_files("pint"),
        *collect_data_files("webview"),
    ],
    hiddenimports=hidden,
    excludes=["pytest", "evals", "tests", "IPython", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MechCopilot",
    console=False,
    icon=os.path.join(SPECPATH, "icon.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="MechCopilot")
