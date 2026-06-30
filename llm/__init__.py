"""Optional, provider-pluggable LLM layer for detection and fix suggestions.

This package is imported lazily by the checker and fixer modules. It supports
both OpenAI and Anthropic (Claude) providers behind a common protocol, and is
gated entirely by ``Settings.llm_enabled`` — when disabled, the deterministic
rules and template suggestions are used unchanged.
"""

from __future__ import annotations

from llm.base import LLMProvider
from llm.factory import get_provider

__all__ = ["LLMProvider", "get_provider"]
