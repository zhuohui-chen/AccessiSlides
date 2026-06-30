"""OpenAI implementation of :class:`~llm.base.LLMProvider`.

Uses the Chat Completions API with a data-URI image part for vision. The SDK is
imported lazily inside ``__init__`` so the package only needs to be installed
when the OpenAI provider is actually selected.
"""

from __future__ import annotations

import base64


class OpenAIProvider:
    """Generate text and image descriptions via the OpenAI Chat Completions API."""

    def __init__(self, *, api_key: str, model: str, timeout: int, max_output_tokens: int) -> None:
        """Construct the provider and its SDK client.

        Args:
            api_key: OpenAI API key.
            model: Vision-capable model id, e.g. ``"gpt-4o-mini"``.
            timeout: Per-request timeout in seconds.
            max_output_tokens: Upper bound on generated tokens per call.
        """
        import openai  # lazy: no SDK import at module load

        self._client = openai.OpenAI(api_key=api_key, timeout=timeout)
        self._model = model
        self._max_output_tokens = max_output_tokens
        self.name = f"openai:{model}"

    def _first_text(self, response: object) -> str:
        """Extract the assistant message text from a Chat Completions response."""
        choices = getattr(response, "choices", [])
        if not choices:
            return ""
        return str(choices[0].message.content or "").strip()

    def generate_text(self, *, system: str, prompt: str) -> str:
        """Return a short text completion."""
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_output_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return self._first_text(response)

    def describe_image(self, *, image_bytes: bytes, media_type: str, system: str, prompt: str) -> str:
        """Return a text description of an image using a data-URI image part."""
        encoded = base64.standard_b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:{media_type};base64,{encoded}"
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_output_tokens,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                },
            ],
        )
        return self._first_text(response)
