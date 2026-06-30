"""Construct an :class:`~llm.base.LLMProvider` from settings, or return None.

The factory is the single gate for the LLM layer. It returns ``None`` — and the
callers fall back to deterministic behavior — whenever the layer is disabled,
the API key is missing, the provider name is unknown, or the SDK is not
installed. Failures are logged, never raised, so a misconfiguration can never
break the deterministic pipeline.
"""

from __future__ import annotations

from config import Settings
from llm.base import LLMProvider
from utils.logging import get_logger

LOGGER = get_logger(__name__)


def get_provider(settings: Settings | None = None) -> LLMProvider | None:
    """Return a configured provider, or ``None`` when the LLM layer is unavailable.

    Args:
        settings: Runtime settings. Defaults to a fresh :class:`Settings`.

    Returns:
        An ``LLMProvider`` for the selected backend, or ``None``.
    """
    resolved = settings or Settings()
    if not resolved.llm_enabled:
        return None

    provider = resolved.llm_provider.strip().lower()
    try:
        if provider == "openai":
            if not resolved.openai_api_key:
                LOGGER.warning("llm_disabled_missing_key", provider=provider)
                return None
            from llm.openai_provider import OpenAIProvider

            return OpenAIProvider(
                api_key=resolved.openai_api_key,
                model=resolved.openai_model,
                timeout=resolved.llm_timeout_seconds,
                max_output_tokens=resolved.llm_max_output_tokens,
            )
        if provider == "anthropic":
            if not resolved.anthropic_api_key:
                LOGGER.warning("llm_disabled_missing_key", provider=provider)
                return None
            from llm.anthropic_provider import AnthropicProvider

            return AnthropicProvider(
                api_key=resolved.anthropic_api_key,
                model=resolved.anthropic_model,
                timeout=resolved.llm_timeout_seconds,
                max_output_tokens=resolved.llm_max_output_tokens,
            )
    except ImportError as exc:
        LOGGER.warning("llm_disabled_sdk_missing", provider=provider, error=str(exc))
        return None

    LOGGER.warning("llm_disabled_unknown_provider", provider=provider)
    return None
