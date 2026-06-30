"""Logging helpers with an optional structlog dependency."""

from __future__ import annotations

import logging
from typing import Any


class StdlibStructuredAdapter:
    """Small adapter that accepts structlog-style keyword arguments."""

    def __init__(self, name: str) -> None:
        """Create the adapter for a stdlib logger."""
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
        self._logger = logging.getLogger(name)

    def info(self, event: str, **kwargs: Any) -> None:
        """Log an informational event."""
        self._logger.info(self._format(event, kwargs))

    def warning(self, event: str, **kwargs: Any) -> None:
        """Log a warning event."""
        self._logger.warning(self._format(event, kwargs))

    def error(self, event: str, **kwargs: Any) -> None:
        """Log an error event."""
        self._logger.error(self._format(event, kwargs))

    @staticmethod
    def _format(event: str, kwargs: dict[str, Any]) -> str:
        """Format an event and structured fields for stdlib logging."""
        if not kwargs:
            return event
        fields = " ".join(f"{key}={value}" for key, value in sorted(kwargs.items()))
        return f"{event} {fields}"


def get_logger(name: str) -> Any:
    """Return a structured logger when available, otherwise a compatible adapter."""
    try:
        import structlog
    except ModuleNotFoundError:
        return StdlibStructuredAdapter(name)
    return structlog.get_logger(name)
