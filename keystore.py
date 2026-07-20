"""Local credential storage: per-provider API keys (and their models) in ``.env``.

The web app lets a user paste an API key for one analysis run and then opt in to
saving it so they do not have to paste it again. This module owns that on-disk
side, deliberately kept next to :mod:`config` because it writes the very file
``Settings`` reads — the CLI and the web app therefore see the same saved keys
with no second code path.

What lives here:

* **A key per provider.** OpenAI and Anthropic keys coexist; saving or erasing
  one never disturbs the other. Which one a run uses is an explicit choice in
  the web app, not something inferred from what happens to be on disk.
* **The model chosen alongside each key**, so a saved credential restores the
  model it was used with. Everything else stays in :mod:`config`.
* **Nothing else.** Writes are a merge, so unrecognized lines and comments in a
  hand-edited ``.env`` are preserved untouched.

Only ``.env`` is ever written. A key exported in the real environment outranks
``.env`` in ``pydantic-settings`` and cannot be erased by editing a file, so it
is reported with source ``"environment"`` and left alone.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"

#: Provider name -> the ``.env`` variable holding its API key.
KEY_VARS: dict[str, str] = {
    "anthropic": "PPTXA_ANTHROPIC_API_KEY",
    "openai": "PPTXA_OPENAI_API_KEY",
}

#: Provider name -> the ``.env`` variable holding the model saved with its key.
MODEL_VARS: dict[str, str] = {
    "anthropic": "PPTXA_ANTHROPIC_MODEL",
    "openai": "PPTXA_OPENAI_MODEL",
}

_HEADER = (
    "# .env — API keys and the model saved with each, written by the app.\n"
    "# Every other setting lives in config.py. This file is git-ignored.\n"
)


def _split_assignment(line: str) -> tuple[str, str] | None:
    """Split one ``.env`` line into ``(name, value)``, or ``None`` if it is not one.

    Tolerates a leading ``export`` and surrounding quotes; comments and blank
    lines return ``None`` so callers can preserve them verbatim.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    name, _, value = stripped.partition("=")
    name = name.strip()
    if name.startswith("export "):
        name = name[len("export ") :].strip()
    if not name:
        return None
    # A trailing `# comment` is not part of the value in files we write, but a
    # hand-edited file may have one; keys and model ids contain no whitespace.
    return name, value.split("#", 1)[0].strip().strip("'\"")


def _read_lines(env_path: Path) -> list[str]:
    """Return the ``.env`` file's lines, or the header when it does not exist."""
    if not env_path.exists():
        return _HEADER.splitlines()
    return env_path.read_text(encoding="utf-8").splitlines()


def _env_file_values(env_path: Path) -> dict[str, str]:
    """Return the ``name -> value`` pairs currently present in ``.env``."""
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _split_assignment(line)
        if parsed is not None:
            values[parsed[0]] = parsed[1]
    return values


def _apply_updates(env_path: Path, updates: dict[str, str | None]) -> None:
    """Merge ``updates`` into ``.env``, where a ``None`` value deletes the line.

    Existing lines keep their position and formatting; only the named variables
    are rewritten. Anything not named — comments, blank lines, settings a user
    added by hand — is preserved exactly. New variables are appended.
    """
    remaining = dict(updates)
    kept: list[str] = []
    for line in _read_lines(env_path):
        parsed = _split_assignment(line)
        if parsed is None or parsed[0] not in remaining:
            kept.append(line)
            continue
        new_value = remaining.pop(parsed[0])
        if new_value is not None:
            kept.append(f"{parsed[0]}={new_value}")
        # else: drop the line entirely

    additions = [f"{name}={value}" for name, value in remaining.items() if value is not None]
    if additions:
        if kept and kept[-1].strip():
            kept.append("")
        kept.extend(additions)

    env_path.write_text("\n".join(kept).rstrip("\n") + "\n", encoding="utf-8")
    try:
        env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:  # exotic filesystem (e.g. a Windows share) — content still wrote
        pass


def key_status(env_path: Path | None = None) -> dict[str, dict[str, object]]:
    """Report, per provider, whether a key is saved, from where, and with what model.

    Args:
        env_path: ``.env`` file to inspect. Defaults to the project's.

    Returns:
        ``{provider: {"present": bool, "source": str | None, "model": str | None}}``.
        ``source`` is ``"env_file"``, or ``"environment"`` when the key is exported
        in the process environment and therefore cannot be erased by
        :func:`clear_saved_keys`.
    """
    file_values = _env_file_values(env_path or ENV_PATH)
    status: dict[str, dict[str, object]] = {}
    for provider, key_var in KEY_VARS.items():
        if (os.environ.get(key_var) or "").strip():
            source: str | None = "environment"
        elif (file_values.get(key_var) or "").strip():
            source = "env_file"
        else:
            source = None
        model_var = MODEL_VARS[provider]
        model = (file_values.get(model_var) or os.environ.get(model_var) or "").strip()
        status[provider] = {
            "present": source is not None,
            "source": source,
            "model": model or None,
        }
    return status


def saved_providers(env_path: Path | None = None) -> list[str]:
    """Return the providers that currently have a saved key, in a stable order."""
    status = key_status(env_path)
    return [name for name in KEY_VARS if status[name]["present"]]


def save_key(
    provider: str,
    api_key: str,
    *,
    model: str | None = None,
    env_path: Path | None = None,
) -> None:
    """Save one provider's API key, and optionally the model chosen with it.

    Only that provider's lines are written: a key already saved for the other
    provider is left exactly as it was, so both can coexist.

    Args:
        provider: ``"anthropic"`` or ``"openai"``.
        api_key: The key to store. Must be non-empty.
        model: Model id to store alongside the key. When omitted or blank, any
            previously saved model for this provider is left unchanged.
        env_path: ``.env`` file to write. Defaults to the project's.

    Raises:
        ValueError: If ``provider`` is unsupported or ``api_key`` is blank.
        OSError: If the file cannot be written.
    """
    normalized = (provider or "").strip().lower()
    if normalized not in KEY_VARS:
        raise ValueError(f"Unsupported provider: {provider!r}")
    cleaned = (api_key or "").strip()
    if not cleaned:
        raise ValueError("Cannot save an empty API key")

    updates: dict[str, str | None] = {KEY_VARS[normalized]: cleaned}
    chosen_model = (model or "").strip()
    if chosen_model:
        updates[MODEL_VARS[normalized]] = chosen_model
    _apply_updates(env_path or ENV_PATH, updates)


def clear_saved_keys(
    providers: list[str] | None = None, *, env_path: Path | None = None
) -> list[str]:
    """Erase the saved key (and its model) for the given providers.

    Args:
        providers: Providers to erase. Defaults to every supported provider.
        env_path: ``.env`` file to write. Defaults to the project's.

    Returns:
        The providers whose keys were actually removed from ``.env``. A key that
        is only set in the process environment is *not* listed, because editing
        a file cannot remove it — see :func:`key_status`.

    Raises:
        ValueError: If any requested provider is unsupported.
    """
    targets = list(KEY_VARS) if providers is None else [p.strip().lower() for p in providers]
    unknown = [p for p in targets if p not in KEY_VARS]
    if unknown:
        raise ValueError(f"Unsupported provider(s): {', '.join(unknown)}")

    resolved = env_path or ENV_PATH
    values = _env_file_values(resolved)
    removed = [p for p in targets if (values.get(KEY_VARS[p]) or "").strip()]

    updates: dict[str, str | None] = {}
    for provider in targets:
        updates[KEY_VARS[provider]] = None
        updates[MODEL_VARS[provider]] = None
    if any(name in values for name in updates):
        _apply_updates(resolved, updates)
    return removed
