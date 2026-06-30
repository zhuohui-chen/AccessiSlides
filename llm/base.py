"""Provider-agnostic LLM interface.

Defines the :class:`LLMProvider` protocol that both the OpenAI and Anthropic
implementations satisfy, plus the model identifier each provider reports for
audit-trail provenance. No SDK is imported here; concrete providers import
their SDK lazily so a missing package degrades to "provider unavailable".
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """A minimal text + vision generation interface.

    Implementations wrap a single provider SDK. Methods raise provider-specific
    exceptions on failure; callers in :mod:`llm.service` catch those and fall
    back to deterministic behavior, so implementations should not swallow errors.
    """

    name: str
    """Provenance tag, e.g. ``"openai:gpt-4o-mini"`` or ``"anthropic:claude-opus-4-8"``."""

    def generate_text(self, *, system: str, prompt: str) -> str:
        """Return a short text completion for a system + user prompt."""
        ...

    def describe_image(self, *, image_bytes: bytes, media_type: str, system: str, prompt: str) -> str:
        """Return a text description of an image given system + user prompts.

        Args:
            image_bytes: Raw image bytes (e.g. ``shape.image.blob``).
            media_type: MIME type such as ``"image/png"`` or ``"image/jpeg"``.
            system: System prompt establishing the assistant's role.
            prompt: User instruction describing what to produce.
        """
        ...
