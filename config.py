"""Runtime configuration for the PowerPoint accessibility agent.

**This file is the place to change behavior.** Every non-secret setting lives
here as a plain default you can edit directly. ``.env`` is reserved for API keys
and the model saved with each key (see :mod:`keystore`), so a secrets file never
doubles as a config file and nothing tunable is hidden in a git-ignored place.

Any field can still be overridden for a single run without editing this file, by
exporting a ``PPTXA_``-prefixed environment variable::

    PPTXA_DEFAULT_LANGUAGE=fr-FR uv run python cli.py fix --input deck.pptx ...

The CLI's ``--llm`` / ``--provider`` flags override the LLM fields the same way.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Values are read in this order, first match winning: an explicit keyword
    argument (used by the CLI flags and the web app), then a ``PPTXA_``-prefixed
    environment variable, then ``.env``, then the defaults below.
    """

    # --- General behavior ---
    default_language: str = "en-US"  # language metadata injected when missing
    default_ledger_name: str = "ledger.json"
    snapshot_dir_name: str = "snapshots"
    auto_title_prefix: str = "Slide"  # prefix for auto-generated slide titles
    fail_on_unknown_auto_fix: bool = False

    # --- Optional LLM layer (OFF by default) ---
    # When disabled — or when no API key or SDK is available — the tool runs the
    # deterministic rules and template suggestions only. Turn it on per run with
    # `cli.py fix --llm`, or per upload with the web app's "Use AI" toggle.
    llm_enabled: bool = False
    llm_provider: str = "openai"  # "openai" or "anthropic"
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-opus-4-8"
    llm_timeout_seconds: int = 30  # per-request timeout
    llm_max_output_tokens: int = 300  # cap on generated suggestion length

    # --- Secrets: set these in .env, never here ---
    # Managed by `keystore` and the web app's "save key" prompt. Both providers
    # can have a key saved at once; the web app asks which to use. Committing a
    # key here would leak it — .env is git-ignored, this file is not.
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PPTXA_")
