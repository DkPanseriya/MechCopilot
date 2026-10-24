"""Settings: the user's own language-model key and model choices, kept in their .env file.

The key never leaves this machine except to the provider it belongs to (to check it), and the
API never returns it: only the last four characters, so the user can see which key is set.
"""
import os
from typing import Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import copilot
from appdata import data_dir, env_path

router = APIRouter(prefix="/settings", tags=["settings"])

KEY_VARS = {"replicate": "REPLICATE_API_TOKEN", "openai": "OPENAI_API_KEY"}
MODEL_VARS = {"plan": "REPLICATE_MODEL", "review": "REPLICATE_MODEL_REVIEW", "deep": "REPLICATE_MODEL_DEEP"}
MODEL_DEFAULTS = {"plan": copilot.DEFAULT_MODEL, "review": copilot.DEFAULT_REVIEW_MODEL,
                  "deep": copilot.DEFAULT_DEEP_MODEL}


def _hint(key: str) -> str:
    return f"…{key[-4:]}" if len(key) > 8 else "set"


def read_settings() -> Dict:
    provider = copilot.provider()
    key = os.getenv(KEY_VARS.get(provider, ""), "") if provider in KEY_VARS else ""
    return {
        "provider": provider,
        "configured": provider != "offline",
        "key_hint": _hint(key) if key else None,
        "models": {role: os.getenv(var) or MODEL_DEFAULTS[role] for role, var in MODEL_VARS.items()},
        "model_defaults": MODEL_DEFAULTS,
        "settings_file": env_path(),
        "data_dir": data_dir(),
    }


def write_env(updates: Dict[str, Optional[str]]) -> None:
    """Set (value) or remove (None) variables in the .env file and in this process,
    keeping every other line of the file as it was."""
    for k, v in updates.items():
        if v is not None and ("\n" in v or "\r" in v):
            raise ValueError(f"{k}: a value cannot contain a line break")
    path = env_path()
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    out, done = [], set()
    for line in lines:
        name = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if name in updates:
            done.add(name)
            if updates[name] is not None:
                out.append(f"{name}={updates[name]}")
            continue
        out.append(line)
    out += [f"{k}={v}" for k, v in updates.items() if k not in done and v is not None]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    for k, v in updates.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def check_key(provider: str, key: str) -> Optional[bool]:
    """True if the provider accepts the key, False if it rejects it, None if it can't be reached."""
    url = {"replicate": "https://api.replicate.com/v1/account", "openai": "https://api.openai.com/v1/models"}[provider]
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=10)
    except httpx.HTTPError:
        return None
    if r.status_code == 200:
        return True
    return False if r.status_code in (401, 403) else None


class SettingsUpdate(BaseModel):
    provider: str                      # "replicate" | "openai" | "none" (calculators only)
    api_key: Optional[str] = None      # empty: keep the key already saved for this provider
    models: Optional[Dict[str, str]] = None


@router.get("")
def get_settings():
    return read_settings()


@router.post("")
def save_settings(update: SettingsUpdate):
    provider = update.provider
    if provider not in ("replicate", "openai", "none"):
        raise HTTPException(status_code=422, detail="Choose Replicate, OpenAI or calculators only.")
    changes: Dict[str, Optional[str]] = {}
    verified = None
    if provider == "none":
        changes = {var: None for var in KEY_VARS.values()}
    else:
        key = (update.api_key or "").strip() or os.getenv(KEY_VARS[provider], "")
        if not key:
            raise HTTPException(status_code=422, detail="Paste your API key.")
        if provider == "replicate" and not key.startswith("r8_"):
            raise HTTPException(status_code=422, detail="Replicate API tokens start with r8_.")
        if provider == "openai" and not key.startswith("sk-"):
            raise HTTPException(status_code=422, detail="OpenAI API keys start with sk-.")
        verified = check_key(provider, key)
        if verified is False:
            raise HTTPException(status_code=422, detail=f"{provider.capitalize()} rejected this key. "
                                                        "Check that you copied all of it.")
        # Only one provider is active: Replicate wins when both keys are set, so clear the other.
        changes = {KEY_VARS[provider]: key,
                   **{var: None for p, var in KEY_VARS.items() if p != provider}}
    for role, model in (update.models or {}).items():
        if role in MODEL_VARS:
            model = model.strip()
            changes[MODEL_VARS[role]] = None if not model or model == MODEL_DEFAULTS[role] else model
    try:
        write_env(changes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {**read_settings(), "verified": verified}
