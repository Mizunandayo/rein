"""Secret-redaction tests for the structured logger.

The redaction processor is a security control. A security control without a
test is only a hope, so each leak path it claims to close is exercised here.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
import structlog
from pydantic import SecretStr

from rein.logging import _redact, configure_logging, get_logger

MASK = "***REDACTED***"


@pytest.fixture(autouse=True)
def _reset_structlog() -> Iterator[None]:
    """Keep one test's logging configuration from leaking into the next."""
    yield
    structlog.reset_defaults()


def test_redacts_values_under_secret_key_names() -> None:
    out = _redact(None, "info", {"event": "call", "api_key": "AIzaLEAK", "depth": 4})

    assert out["api_key"] == MASK
    assert out["depth"] == 4, "non-secret values must pass through untouched"


def test_key_name_match_is_case_insensitive() -> None:
    out = _redact(None, "info", {"event": "call", "API_KEY": "AIzaLEAK", "Token": "t"})

    assert out["API_KEY"] == MASK
    assert out["Token"] == MASK


def test_redacts_secretstr_under_an_innocent_name() -> None:
    """The second mechanism: a secret smuggled in under a harmless key."""
    out = _redact(None, "info", {"event": "call", "payload": SecretStr("hunter2")})

    assert out["payload"] == MASK


def test_secret_never_reaches_rendered_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    """End to end: configure, log a secret, inspect what actually got printed."""
    configure_logging("INFO", "json")

    get_logger("test").info("fetch", api_key="AIzaLEAK", session="s3ss10n", depth=3)

    printed = capsys.readouterr().out
    assert "AIzaLEAK" not in printed
    assert "s3ss10n" not in printed
    assert MASK in printed
    assert '"depth": 3' in printed


def test_console_format_also_redacts(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", "console")

    # A deliberately fake secret: the test proves it gets redacted.
    get_logger("test").info("fetch", password="pa55word")  # noqa: S106

    assert "pa55word" not in capsys.readouterr().out


def test_level_filter_drops_lower_levels(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("WARNING", "json")

    get_logger("test").info("should_not_appear")

    assert "should_not_appear" not in capsys.readouterr().out


def test_http_client_request_urls_are_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """The httpx library logs each request URL at INFO; a URL can carry a key."""
    caplog.set_level(logging.INFO)
    configure_logging("INFO", "json")

    logging.getLogger("httpx").info("HTTP Request: GET https://x.test/root.json?key=AIzaLEAK")

    assert "AIzaLEAK" not in caplog.text
