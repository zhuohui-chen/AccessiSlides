"""Anthropic (Claude) implementation of :class:`~llm.base.LLMProvider`.

Uses the Messages API with base64 image input for vision. The SDK is imported
lazily inside ``__init__`` so the package only needs to be installed when the
Anthropic provider is actually selected.
"""

from __future__ import annotations

import base64

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider:
    """Generate text and image descriptions via the Anthropic Messages API."""

    def __init__(self, *, api_key: str, model: str, timeout: int, max_output_tokens: int) -> None:
        """Construct the provider and its SDK client.

        Args:
            api_key: Anthropic API key.
            model: Vision-capable model id, e.g. ``"claude-opus-4-8"``.
            timeout: Per-request timeout in seconds.
            max_output_tokens: Upper bound on generated tokens per call.
        """
        import anthropic  # lazy: no SDK import at module load

        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self._model = model
        self._max_output_tokens = max_output_tokens
        self.name = f"anthropic:{model}"

    def _first_text(self, response: object) -> str:
        """Extract the first text block from a Messages API response."""
        for block in getattr(response, "content", []):
            if getattr(block, "type", None) == "text":
                return str(block.text).strip()
        return ""

    def generate_text(self, *, system: str, prompt: str) -> str:
        """Return a short text completion."""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_output_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._first_text(response)

    def describe_image(self, *, image_bytes: bytes, media_type: str, system: str, prompt: str) -> str:
        """Return a text description of an image using base64 vision input."""
        encoded = base64.standard_b64encode(image_bytes).decode("utf-8")
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_output_tokens,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": encoded},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return self._first_text(response)
