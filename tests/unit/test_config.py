"""Configuration and secret-handling tests."""

from __future__ import annotations

import pytest

from rein.config import Settings


def test_secret_never_appears_in_repr() -> None:
    """A secret must not leak through repr/str — the commonest accidental leak."""
    s = Settings(google_maps_api_key="AIzaSyREALLOOKINGSECRET")  # type: ignore[arg-type]

    assert "AIzaSyREALLOOKINGSECRET" not in repr(s)
    assert "AIzaSyREALLOOKINGSECRET" not in str(s)
    assert "AIzaSyREALLOOKINGSECRET" not in s.model_dump_json()
    assert s.require_google_key() == "AIzaSyREALLOOKINGSECRET"


def test_unknown_env_var_is_rejected() -> None:
    """A typo'd setting must fail loudly, not be silently ignored."""
    with pytest.raises(ValueError, match=r"extra_forbidden|Extra inputs"):
        Settings(gogle_maps_api_key="x")  # type: ignore[call-arg]


def test_placeholder_key_rejected() -> None:
    """Copying .env.example without editing must not look like success."""
    with pytest.raises(ValueError, match="placeholder"):
        Settings(google_maps_api_key="changeme")  # type: ignore[arg-type]


def test_missing_key_raises_actionable_error() -> None:
    s = Settings()
    with pytest.raises(RuntimeError, match="Map Tiles API"):
        s.require_google_key()
