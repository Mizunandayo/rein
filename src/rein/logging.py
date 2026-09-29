"""Structured logging with automatic secret redaction."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from pydantic import SecretStr

# Keys whose values are scrubbed regardless of where they appear.
_REDACT_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "key",
        "token",
        "secret",
        "password",
        "authorization",
        "access_key",
        "session",
        "credential",
    }
)
_MASK = "***REDACTED***"


def _redact(
    _logger: object, _name: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Mask secret-looking values before anything reaches an output stream.

    Two mechanisms, because either alone leaks:
      * key-name matching catches ``log.info("call", api_key=k)``
      * SecretStr detection catches a secret passed under an innocent name
    """
    for k, v in list(event_dict.items()):
        if isinstance(v, SecretStr) or k.lower() in _REDACT_KEYS:
            event_dict[k] = _MASK
    return event_dict


def configure_logging(level: str = "INFO", fmt: str = "console") -> None:
    """Configure structlog once, at process start.

    Args:
        level: Standard logging level name.
        fmt: ``console`` for human-readable dev output, ``json`` for machines.
    """
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact,  # MUST precede any renderer
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    processors.append(
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    # httpx and httpcore log every request URL at INFO, and a URL can carry an
    # API key as a query parameter. Their logs stay at WARNING and above.
    for library in ("httpx", "httpcore"):
        logging.getLogger(library).setLevel(logging.WARNING)
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level]),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger for a module."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
