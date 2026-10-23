"""Pytest path setup.

The backend mixes two import styles: package-style (`from backend.x import ...`,
used by tests) and bare (`import copilot`, used at runtime because
uvicorn runs from the backend directory). Put both the project root and the
backend directory on sys.path so either style resolves during tests.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (_ROOT, os.path.join(_ROOT, "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
