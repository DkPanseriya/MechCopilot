"""Where MechCopilot keeps its writable files: settings (.env), the chat database and user data.

From source (start.bat / start.sh) this is the backend folder, as it always was. The installed
Windows app runs from a read-only program folder, so it keeps them in the user's profile
(%LOCALAPPDATA%\\MechCopilot). MECH_DATA_DIR overrides both.
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))


def frozen() -> bool:
    """True inside the packaged desktop app (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def data_dir() -> str:
    path = os.getenv("MECH_DATA_DIR")
    if not path:
        if frozen():
            base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
            path = os.path.join(base, "MechCopilot")
        else:
            path = BACKEND_DIR
    os.makedirs(path, exist_ok=True)
    return path


def env_path() -> str:
    """The settings file: API keys and model choices."""
    return os.path.join(data_dir(), ".env")


def user_data_dir() -> str:
    """User catalogue imports (e.g. bearings.csv)."""
    return os.path.join(data_dir(), "data", "user")
