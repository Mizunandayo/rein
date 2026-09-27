"""Dataset provenance manifest tests.

These guard the reproducible-audit claim: if a manifest's hash or size is
wrong, a third party cannot verify which data an analysis actually used.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rein import provenance
from rein.provenance import manifest_for, sha256_file


def test_sha256_matches_hashlib_across_chunk_boundary(tmp_path: Path) -> None:
    """The chunked reader must agree with a one-shot hash, even past 1 MiB."""
    payload = b"rein" * 300_000  # 1.2 MB, forces more than one read
    f = tmp_path / "sample.bin"
    f.write_bytes(payload)

    assert sha256_file(f) == hashlib.sha256(payload).hexdigest()


def test_manifest_records_size_hash_and_utc_time(tmp_path: Path) -> None:
    f = tmp_path / "buildings.gpkg"
    f.write_bytes(b"not really a geopackage")

    m = manifest_for(
        f,
        dataset_id="test-buildings",
        description="Test fixture.",
        licence="ODbL 1.0",
        attribution="(c) OpenStreetMap contributors",
        source_url="https://www.openstreetmap.org/",
    )

    assert m.file_name == "buildings.gpkg"
    assert m.file_bytes == f.stat().st_size
    assert m.sha256 == sha256_file(f)
    assert m.retrieved_at.tzinfo is not None, "timestamps must be timezone-aware"
    assert m.contains_personal_data is False
    assert m.pii_fields_dropped == []


def test_manifest_records_dropped_pii_fields(tmp_path: Path) -> None:
    """A source that carried personal data must say which fields were removed."""
    f = tmp_path / "parcels.geojson"
    f.write_text("{}", encoding="utf-8")

    m = manifest_for(
        f,
        dataset_id="test-parcels",
        description="Test fixture.",
        licence="Public record",
        attribution="Test county",
        contains_personal_data=True,
        pii_fields_dropped=["OWNER_NAME", "MAIL_ADDR"],
    )

    assert m.contains_personal_data is True
    assert m.pii_fields_dropped == ["OWNER_NAME", "MAIL_ADDR"]


def test_write_produces_sorted_json_named_by_dataset_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sorted keys keep manifest diffs stable, so a real change is visible."""
    out_dir = tmp_path / "provenance"
    monkeypatch.setattr(provenance, "DATA_PROVENANCE", out_dir)

    f = tmp_path / "data.bin"
    f.write_bytes(b"abc")
    m = manifest_for(
        f,
        dataset_id="test-write",
        description="Test fixture.",
        licence="MIT",
        attribution="Test",
    )

    out = m.write()

    assert out == out_dir / "test-write.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["sha256"] == hashlib.sha256(b"abc").hexdigest()
    assert list(data) == sorted(data)
    assert out.read_text(encoding="utf-8").endswith("\n")
