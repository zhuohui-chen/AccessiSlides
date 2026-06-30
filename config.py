"""Runtime configuration for the PowerPoint accessibility agent."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or `.env`.

    Environment variables use the `PPTXA_` prefix, for example
    `PPTXA_DEFAULT_LANGUAGE=en-US`.
    """

    default_language: str = "en-US"
    default_ledger_name: str = "ledger.json"
    snapshot_dir_name: str = "snapshots"
    auto_title_prefix: str = "Slide"
    fail_on_unknown_auto_fix: bool = False

    # Optional LLM layer. Off by default: when disabled (or when no API key/SDK is
    # available) the tool runs the deterministic rules and template suggestions only.
    llm_enabled: bool = False
    llm_provider: str = "openai"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-opus-4-8"
    llm_timeout_seconds: int = 30
    llm_max_output_tokens: int = 300

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PPTXA_")
