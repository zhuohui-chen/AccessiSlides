"""Checker orchestration for PowerPoint accessibility issues."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx import Presentation

from checker import triage
from checker.rules import (
    alt_text,
    complex_objects,
    contrast,
    contrast_image,
    generic_links,
    metadata,
    missing_title,
)
from config import Settings
from models import Finding

RULE_MODULES = (
    metadata,
    missing_title,
    generic_links,
    alt_text,
    complex_objects,
    contrast,
    contrast_image,
)


def run_checks_on_presentation(
    prs: Any,
    settings: Settings | None = None,
    *,
    provider: Any | None = None,
) -> list[Finding]:
    """Run all configured checks against a loaded presentation.

    Deterministic rules run first and remain the authoritative source of
    findings. When the LLM layer is enabled, an additive semantic pass appends
    further findings tagged with their provenance; everything then flows through
    the same triage so risk levels stay centralized.

    Args:
        prs: Loaded python-pptx presentation.
        settings: Runtime settings.
        provider: Pre-built LLM provider. When omitted and ``llm_enabled`` is set,
            one is created via the factory. Passing an explicit provider (e.g. a
            test fake) bypasses the factory.
    """
    resolved_settings = settings or Settings()
    findings: list[Finding] = []
    for module in RULE_MODULES:
        findings.extend(module.check(prs, resolved_settings))

    if resolved_settings.llm_enabled:
        from llm import service
        from llm.factory import get_provider

        resolved_provider = provider or get_provider(resolved_settings)
        if resolved_provider is not None:
            findings.extend(service.detect_weak_titles(resolved_provider, prs=prs))
            findings.extend(service.detect_semantic_issues(resolved_provider, prs=prs))

    for finding in findings:
        finding.risk_level = triage.classify(finding)
    return findings


def run_checks(pptx_path: Path, settings: Settings | None = None) -> list[Finding]:
    """Load a `.pptx` and run all configured accessibility checks."""
    prs = Presentation(pptx_path)
    return run_checks_on_presentation(prs, settings)
