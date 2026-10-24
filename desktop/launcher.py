"""MechCopilot desktop app: start the backend on a free local port and open the app window.

One process: the FastAPI backend also serves the pre-built frontend (MECH_WEB_DIR), so the
app needs no Python, Node or terminal on the user's machine. Settings, chats and logs live in
%LOCALAPPDATA%\\MechCopilot (see backend/appdata.py).

Run from source for testing (after building the frontend with desktop/build.ps1 or
`MECH_STATIC_EXPORT=1 npx next build` in frontend/):  python desktop/launcher.py
"""
import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    BUNDLE = sys._MEIPASS  # type: ignore[attr-defined]
    WEB_DIR = os.path.join(BUNDLE, "web")
else:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    WEB_DIR = os.path.join(ROOT, "frontend", "out")
os.environ.setdefault("MECH_WEB_DIR", WEB_DIR)

from appdata import data_dir  # noqa: E402  (needs the backend on sys.path)

DATA = data_dir()
LOG_DIR = os.path.join(DATA, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
INSTANCE_FILE = os.path.join(DATA, "instance.json")

# A windowed app has no console: send everything to a log file the user can attach to a bug report.
_log = open(os.path.join(LOG_DIR, "mechcopilot.log"), "a", encoding="utf-8", buffering=1)
if sys.stdout is None or FROZEN:
    sys.stdout = _log
if sys.stderr is None or FROZEN:
    sys.stderr = _log
logging.basicConfig(stream=_log, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mechcopilot")


def _healthy(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=timeout) as r:
            return r.status == 200
    except OSError:
        return False


def _running_instance() -> str | None:
    """The address of an already running MechCopilot, so a second launch opens a window on it."""
    try:
        with open(INSTANCE_FILE, encoding="utf-8") as f:
            url = json.load(f)["url"]
    except (OSError, ValueError, KeyError):
        return None
    return url if _healthy(url) else None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server():
    import uvicorn
    from main import app

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                                           log_config=None))
    thread = threading.Thread(target=server.run, name="backend", daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 60
    while not _healthy(url):
        if not thread.is_alive() or time.time() > deadline:
            raise RuntimeError("The MechCopilot backend did not start. See the log in " + LOG_DIR)
        time.sleep(0.2)
    with open(INSTANCE_FILE, "w", encoding="utf-8") as f:
        json.dump({"url": url, "pid": os.getpid()}, f)
    log.info("backend running at %s", url)
    return server, thread, url


def _open_window(url: str) -> bool:
    """The app window (Edge WebView2). Returns False if it cannot be shown on this machine."""
    # pywebview's Windows backend needs WinForms from the .NET Framework that ships with
    # Windows; without this pythonnet may pick a .NET (Core) runtime that has no WinForms.
    os.environ.setdefault("PYTHONNET_RUNTIME", "netfx")
    try:
        import webview
    except Exception:
        log.exception("pywebview unavailable")
        return False
    try:
        webview.create_window("MechCopilot", url, width=1440, height=920, min_size=(1024, 640))
        webview.start()
        return True
    except Exception:
        log.exception("app window failed")
        return False


def _edge_app_window(url: str) -> bool:
    """Microsoft Edge in app mode: its own window, no tabs or address bar. Edge ships with
    Windows 10 and 11. A separate profile makes it a separate process, so this returns when
    the user closes the window. Returns False if Edge is not installed."""
    import subprocess

    candidates = [os.path.join(os.environ.get(v, ""), "Microsoft", "Edge", "Application", "msedge.exe")
                  for v in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
    edge = next((p for p in candidates if os.path.isfile(p)), None)
    if not edge:
        return False
    profile = os.path.join(DATA, "window")
    try:
        subprocess.run([edge, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run",
                        "--no-default-browser-check", "--window-size=1440,920"], check=False)
        return True
    except OSError:
        log.exception("Edge app window failed")
        return False


def _browser_fallback(url: str, stop) -> None:
    """No WebView2: open the default browser and keep a small window to reopen or quit."""
    webbrowser.open(url)
    try:
        import tkinter as tk
    except Exception:
        while True:  # nothing to show a window with: keep serving until the process is ended
            time.sleep(3600)
    root = tk.Tk()
    root.title("MechCopilot")
    root.resizable(False, False)
    tk.Label(root, text="MechCopilot is running in your web browser.", padx=24, pady=16).pack()
    row = tk.Frame(root, pady=12)
    row.pack()
    tk.Button(row, text="Open MechCopilot", width=18, command=lambda: webbrowser.open(url)).pack(side="left", padx=6)
    tk.Button(row, text="Quit", width=10, command=root.destroy).pack(side="left", padx=6)
    root.mainloop()
    stop()


def main() -> None:
    existing = _running_instance()
    if existing:
        if not (_open_window(existing) or _edge_app_window(existing)):
            webbrowser.open(existing)
        return
    try:
        server, thread, url = _start_server()
    except Exception as e:
        log.exception("startup failed")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, str(e), "MechCopilot could not start", 0x10)
        except Exception:
            pass
        raise SystemExit(1)

    def stop():
        server.should_exit = True
        thread.join(timeout=10)
        try:
            os.remove(INSTANCE_FILE)
        except OSError:
            pass

    if _open_window(url) or _edge_app_window(url):
        stop()
    else:
        _browser_fallback(url, stop)


if __name__ == "__main__":
    main()
