"""Tests for local API key storage in ``.env``."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from keystore import clear_saved_keys, key_status, save_key, saved_providers


def _write_env(tmp_path: Path, body: str) -> Path:
    env_path = tmp_path / ".env"
    env_path.write_text(body, encoding="utf-8")
    return env_path


def _values(env_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            name, _, value = line.partition("=")
            out[name.strip()] = value.strip()
    return out


def test_key_status_reports_nothing_for_missing_env(tmp_path: Path, monkeypatch) -> None:
    """A project with no .env and no exported keys reports no saved keys."""
    monkeypatch.delenv("PPTXA_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("PPTXA_OPENAI_API_KEY", raising=False)
    status = key_status(tmp_path / ".env")
    assert status["anthropic"] == {"present": False, "source": None, "model": None}
    assert status["openai"] == {"present": False, "source": None, "model": None}


def test_key_status_distinguishes_env_file_from_environment(tmp_path: Path, monkeypatch) -> None:
    """An exported key is reported as 'environment' so the UI can say it is not erasable."""
    monkeypatch.delenv("PPTXA_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("PPTXA_OPENAI_API_KEY", "sk-from-shell")
    env_path = _write_env(tmp_path, "PPTXA_ANTHROPIC_API_KEY=sk-ant-file\n")

    status = key_status(env_path)
    assert status["anthropic"]["source"] == "env_file"
    assert status["openai"]["source"] == "environment"


def test_both_provider_keys_can_be_saved_at_once(tmp_path: Path, monkeypatch) -> None:
    """Saving one provider's key leaves the other provider's key untouched."""
    monkeypatch.delenv("PPTXA_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("PPTXA_OPENAI_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    save_key("openai", "sk-openai-A", env_path=env_path)
    save_key("anthropic", "sk-ant-B", env_path=env_path)

    values = _values(env_path)
    assert values["PPTXA_OPENAI_API_KEY"] == "sk-openai-A"
    assert values["PPTXA_ANTHROPIC_API_KEY"] == "sk-ant-B"
    assert saved_providers(env_path) == ["anthropic", "openai"]


def test_save_key_stores_the_model_alongside_the_key(tmp_path: Path, monkeypatch) -> None:
    """The model chosen with a key is saved and reported per provider."""
    monkeypatch.delenv("PPTXA_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("PPTXA_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PPTXA_ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("PPTXA_OPENAI_MODEL", raising=False)
    env_path = tmp_path / ".env"
    save_key("anthropic", "sk-ant-B", model="claude-sonnet-5", env_path=env_path)
    save_key("openai", "sk-openai-A", model="gpt-4o", env_path=env_path)

    status = key_status(env_path)
    assert status["anthropic"]["model"] == "claude-sonnet-5"
    assert status["openai"]["model"] == "gpt-4o"


def test_save_key_without_model_keeps_the_previous_one(tmp_path: Path, monkeypatch) -> None:
    """Re-saving just a key does not wipe the model already stored with it."""
    monkeypatch.delenv("PPTXA_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("PPTXA_ANTHROPIC_MODEL", raising=False)
    env_path = tmp_path / ".env"
    save_key("anthropic", "sk-ant-B", model="claude-sonnet-5", env_path=env_path)
    save_key("anthropic", "sk-ant-rotated", env_path=env_path)

    status = key_status(env_path)
    assert _values(env_path)["PPTXA_ANTHROPIC_API_KEY"] == "sk-ant-rotated"
    assert status["anthropic"]["model"] == "claude-sonnet-5"


def test_save_key_preserves_unrelated_lines(tmp_path: Path) -> None:
    """Writes are a merge: comments and hand-added settings survive."""
    env_path = _write_env(tmp_path, "# my notes\nPPTXA_DEFAULT_LANGUAGE=fr-FR\n")
    save_key("anthropic", "sk-ant-new", env_path=env_path)

    text = env_path.read_text(encoding="utf-8")
    assert "# my notes" in text
    assert _values(env_path)["PPTXA_DEFAULT_LANGUAGE"] == "fr-FR"
    assert _values(env_path)["PPTXA_ANTHROPIC_API_KEY"] == "sk-ant-new"


def test_save_key_creates_env_with_owner_only_permissions(tmp_path: Path) -> None:
    """A newly created .env is not world- or group-readable."""
    env_path = tmp_path / ".env"
    save_key("anthropic", "sk-ant-new", env_path=env_path)

    assert _values(env_path)["PPTXA_ANTHROPIC_API_KEY"] == "sk-ant-new"
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600


def test_save_key_rejects_bad_input(tmp_path: Path) -> None:
    """Unsupported providers and blank keys are refused before any write."""
    env_path = tmp_path / ".env"
    with pytest.raises(ValueError):
        save_key("acme", "sk-x", env_path=env_path)
    with pytest.raises(ValueError):
        save_key("anthropic", "   ", env_path=env_path)
    assert not env_path.exists()


def test_clear_one_provider_leaves_the_other_saved(tmp_path: Path, monkeypatch) -> None:
    """Erasing a single provider removes only its key and model."""
    monkeypatch.delenv("PPTXA_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("PPTXA_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PPTXA_OPENAI_MODEL", raising=False)
    env_path = tmp_path / ".env"
    save_key("openai", "sk-openai-A", model="gpt-4o", env_path=env_path)
    save_key("anthropic", "sk-ant-B", model="claude-sonnet-5", env_path=env_path)

    assert clear_saved_keys(["anthropic"], env_path=env_path) == ["anthropic"]
    values = _values(env_path)
    assert "PPTXA_ANTHROPIC_API_KEY" not in values
    assert "PPTXA_ANTHROPIC_MODEL" not in values
    assert values["PPTXA_OPENAI_API_KEY"] == "sk-openai-A"
    assert values["PPTXA_OPENAI_MODEL"] == "gpt-4o"
    assert saved_providers(env_path) == ["openai"]


def test_clear_all_saved_keys_by_default(tmp_path: Path, monkeypatch) -> None:
    """With no providers given, every saved key is erased."""
    monkeypatch.delenv("PPTXA_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("PPTXA_OPENAI_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    save_key("openai", "sk-openai-A", env_path=env_path)
    save_key("anthropic", "sk-ant-B", env_path=env_path)

    assert sorted(clear_saved_keys(env_path=env_path)) == ["anthropic", "openai"]
    assert saved_providers(env_path) == []


def test_clear_saved_keys_rejects_unknown_provider(tmp_path: Path) -> None:
    """An unsupported provider name is refused rather than silently ignored."""
    env_path = tmp_path / ".env"
    save_key("openai", "sk-openai-A", env_path=env_path)
    with pytest.raises(ValueError):
        clear_saved_keys(["acme"], env_path=env_path)
    assert saved_providers(env_path) == ["openai"]


def test_clear_saved_keys_is_a_noop_when_nothing_saved(tmp_path: Path) -> None:
    """Erasing with no saved key reports nothing removed and does not fail."""
    env_path = tmp_path / ".env"
    assert clear_saved_keys(env_path=env_path) == []


def test_clear_saved_keys_cannot_remove_an_exported_key(tmp_path: Path, monkeypatch) -> None:
    """A shell-exported key survives erasure and is still reported as present."""
    monkeypatch.setenv("PPTXA_OPENAI_API_KEY", "sk-from-shell")
    env_path = _write_env(tmp_path, "PPTXA_ANTHROPIC_API_KEY=sk-ant\n")

    assert clear_saved_keys(env_path=env_path) == ["anthropic"]
    status = key_status(env_path)
    assert status["openai"]["present"] is True
    assert status["openai"]["source"] == "environment"
