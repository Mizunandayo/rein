"""Dataset provenance manifests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl

from rein.config import DATA_PROVENANCE

_CHUNK = 1 << 20  # 1 MiB


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file, read in chunks.

    Chunked so that a multi-gigabyte extract does not have to fit in memory.
    """
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


class DatasetManifest(BaseModel):
    """An auditable record of one ingested dataset."""

    dataset_id: str = Field(description="Stable slug, e.g. 'osm-buildings-cstat'.")
    description: str
    source_url: HttpUrl | None = None
    source_note: str = Field(
        default="",
        description="How it was obtained when a URL is insufficient — an API "
        "query, a portal export, a manual download.",
    )
    licence: str = Field(description="e.g. 'ODbL 1.0' for OpenStreetMap.")
    attribution: str = Field(description="Exact attribution text required by the licence.")
    retrieved_at: datetime
    file_name: str
    file_bytes: int
    sha256: str
    contains_personal_data: bool = Field(
        description="True if the ORIGINAL contained owner names, mailing "
        "addresses or similar. If true, pii_fields_dropped must list them.",
    )
    pii_fields_dropped: list[str] = Field(default_factory=list)
    notes: str = ""

    def write(self) -> Path:
        """Write this manifest as JSON into ``data/provenance``."""
        DATA_PROVENANCE.mkdir(parents=True, exist_ok=True)
        out = DATA_PROVENANCE / f"{self.dataset_id}.json"
        out.write_text(
            json.dumps(json.loads(self.model_dump_json()), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return out


def manifest_for(
    path: Path,
    *,
    dataset_id: str,
    description: str,
    licence: str,
    attribution: str,
    source_url: str | None = None,
    source_note: str = "",
    contains_personal_data: bool = False,
    pii_fields_dropped: list[str] | None = None,
    notes: str = "",
) -> DatasetManifest:
    """Build a manifest by hashing a file that is already on disk."""
    return DatasetManifest(
        dataset_id=dataset_id,
        description=description,
        source_url=source_url,  # type: ignore[arg-type]
        source_note=source_note,
        licence=licence,
        attribution=attribution,
        retrieved_at=datetime.now(UTC),
        file_name=path.name,
        file_bytes=path.stat().st_size,
        sha256=sha256_file(path),
        contains_personal_data=contains_personal_data,
        pii_fields_dropped=pii_fields_dropped or [],
        notes=notes,
    )
