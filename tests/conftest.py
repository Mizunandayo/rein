"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from rein.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Stop tests reading the developer's real ``.env``."""
    get_settings.cache_clear()
    for var in [v for v in dict(__import__("os").environ) if v.startswith("REIN_")]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    yield
    get_settings.cache_clear()


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """An isolated data directory per test."""
    d = tmp_path / "data"
    (d / "raw").mkdir(parents=True)
    (d / "provenance").mkdir(parents=True)
    return d
