"""Settings: the user's own key is written to their .env, checked with the provider, never returned."""
import os

import pytest
from fastapi import HTTPException

import appdata
from routers import settings


@pytest.fixture
def data(tmp_path, monkeypatch):
    """A fresh data folder with no key in the environment."""
    monkeypatch.setenv("MECH_DATA_DIR", str(tmp_path))
    for var in ("REPLICATE_API_TOKEN", "OPENAI_API_KEY", "MECH_DEMO_MODE",
                "REPLICATE_MODEL", "REPLICATE_MODEL_REVIEW", "REPLICATE_MODEL_DEEP"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(settings, "check_key", lambda provider, key: True)
    yield tmp_path
    for var in ("REPLICATE_API_TOKEN", "OPENAI_API_KEY", "REPLICATE_MODEL"):
        os.environ.pop(var, None)


def _env(path):
    return (path / ".env").read_text(encoding="utf-8")


def test_data_dir_follows_override_and_installed_app(tmp_path, monkeypatch):
    monkeypatch.setenv("MECH_DATA_DIR", str(tmp_path / "x"))
    assert appdata.data_dir() == str(tmp_path / "x") and os.path.isdir(tmp_path / "x")
    monkeypatch.delenv("MECH_DATA_DIR")
    monkeypatch.setattr(appdata, "frozen", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert appdata.data_dir() == os.path.join(str(tmp_path), "MechCopilot")


def test_save_writes_key_and_never_returns_it(data):
    out = settings.save_settings(settings.SettingsUpdate(provider="replicate", api_key="r8_secretvalue1234"))
    assert "REPLICATE_API_TOKEN=r8_secretvalue1234" in _env(data)
    assert out["configured"] and out["provider"] == "replicate"
    assert out["key_hint"] == "…1234" and "r8_secretvalue1234" not in str(out)


def test_save_keeps_other_lines_and_switching_provider_clears_the_other_key(data):
    (data / ".env").write_text("# my notes\nREPLICATE_API_TOKEN=r8_old\nSOMETHING_ELSE=1\n", encoding="utf-8")
    os.environ["REPLICATE_API_TOKEN"] = "r8_old"
    settings.save_settings(settings.SettingsUpdate(provider="openai", api_key="sk-newkey123456"))
    text = _env(data)
    assert "# my notes" in text and "SOMETHING_ELSE=1" in text
    assert "OPENAI_API_KEY=sk-newkey123456" in text and "REPLICATE_API_TOKEN" not in text
    assert "REPLICATE_API_TOKEN" not in os.environ


def test_empty_key_keeps_the_saved_one_and_default_models_are_not_written(data):
    settings.save_settings(settings.SettingsUpdate(provider="replicate", api_key="r8_first1234567"))
    settings.save_settings(settings.SettingsUpdate(provider="replicate", api_key="", models={
        "plan": settings.MODEL_DEFAULTS["plan"], "review": "anthropic/claude-4.5-haiku"}))
    text = _env(data)
    assert "REPLICATE_API_TOKEN=r8_first1234567" in text
    assert "REPLICATE_MODEL=" not in text and "REPLICATE_MODEL_REVIEW=anthropic/claude-4.5-haiku" in text


def test_calculators_only_removes_keys(data):
    settings.save_settings(settings.SettingsUpdate(provider="replicate", api_key="r8_first1234567"))
    out = settings.save_settings(settings.SettingsUpdate(provider="none"))
    assert not out["configured"] and "REPLICATE_API_TOKEN" not in _env(data)


@pytest.mark.parametrize("provider,key,message", [
    ("replicate", "abc", "start with r8_"), ("openai", "r8_x", "start with sk-"), ("replicate", "", "Paste"),
    ("gemini", "x", "Choose"),
])
def test_rejects_bad_input_without_writing(data, provider, key, message):
    with pytest.raises(HTTPException) as e:
        settings.save_settings(settings.SettingsUpdate(provider=provider, api_key=key))
    assert message in e.value.detail and not (data / ".env").exists()


def test_key_rejected_by_provider_is_not_saved(data, monkeypatch):
    monkeypatch.setattr(settings, "check_key", lambda provider, key: False)
    with pytest.raises(HTTPException) as e:
        settings.save_settings(settings.SettingsUpdate(provider="replicate", api_key="r8_wrong12345678"))
    assert "rejected" in e.value.detail and not (data / ".env").exists()


def test_unverifiable_key_is_saved_with_a_flag(data, monkeypatch):
    monkeypatch.setattr(settings, "check_key", lambda provider, key: None)   # no internet
    out = settings.save_settings(settings.SettingsUpdate(provider="replicate", api_key="r8_offline123456"))
    assert out["verified"] is None and "r8_offline123456" in _env(data)
