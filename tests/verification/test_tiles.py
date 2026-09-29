"""V1 tile-coverage tests, run against a fake tileset."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import structlog

from rein.config import get_settings
from rein.verification import tiles
from rein.verification.tiles import (
    ProbePoint,
    Vec3,
    _absolutise,
    _Budget,
    _ecef,
    _probe,
    _region_contains,
    _segment_hits_box,
    _segment_hits_sphere,
    _target,
    _verdict,
    run_probes,
)

KEY = "test-key-123"
POINT = ProbePoint("target", 30.6280, -96.3344)

# A region (radians) around the target point, and one far away from it.
_LAT, _LON = math.radians(POINT.lat), math.radians(POINT.lon)
HERE = [_LON - 0.01, _LAT - 0.01, _LON + 0.01, _LAT + 0.01, 0.0, 500.0]
ELSEWHERE = [_LON + 1.0, _LAT + 1.0, _LON + 1.1, _LAT + 1.1, 0.0, 500.0]

Handler = Callable[[httpx.Request], httpx.Response]


def _tileset(leaf_error: float) -> dict[str, dict[str, Any]]:
    """Root -> external sub-tileset -> one mesh leaf at ``leaf_error`` metres."""
    root = {
        "root": {
            "boundingVolume": {"region": HERE},
            "geometricError": 5000.0,
            "children": [
                {
                    "boundingVolume": {"region": HERE},
                    "geometricError": 500.0,
                    "content": {"uri": "/v1/3dtiles/datasets/x/files/sub.json?session=s1"},
                },
                {
                    # Does not contain the point: must never be fetched.
                    "boundingVolume": {"region": ELSEWHERE},
                    "geometricError": 500.0,
                    "content": {"uri": "/v1/3dtiles/datasets/x/files/far.json?session=s1"},
                },
            ],
        }
    }
    sub = {
        "root": {
            "boundingVolume": {"region": HERE},
            "geometricError": leaf_error,
            "content": {"uri": "leaf.glb"},
        }
    }
    return {"root.json": root, "sub.json": sub}


def _handler(docs: dict[str, dict[str, Any]], seen: list[httpx.URL]) -> Handler:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        name = request.url.path.rsplit("/", 1)[-1]
        if name in docs:
            return httpx.Response(200, json=docs[name])
        return httpx.Response(404)

    return handle


def _client(handler: Handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _reset_structlog() -> Iterator[None]:
    yield
    structlog.reset_defaults()


# ── Geometry ──────────────────────────────────────────────────────────


def test_region_contains_point_inside_and_rejects_outside() -> None:
    assert _region_contains(HERE, _LAT, _LON)
    assert not _region_contains(ELSEWHERE, _LAT, _LON)


def test_region_crossing_the_antimeridian() -> None:
    """A region from 179 E to 179 W wraps; 180 is inside it, 0 is not."""
    wrap = [math.radians(179), -0.1, math.radians(-179), 0.1, 0.0, 0.0]
    assert _region_contains(wrap, 0.0, math.radians(180))
    assert not _region_contains(wrap, 0.0, 0.0)


# ── URL handling ──────────────────────────────────────────────────────


def test_absolutise_resolves_each_uri_form() -> None:
    parent = "https://tile.googleapis.com/v1/a/b/root.json?session=abc&key=k"
    assert _absolutise("https://x.test/t.glb", parent) == "https://x.test/t.glb?session=abc"
    assert _absolutise("/v1/c.json", parent) == "https://tile.googleapis.com/v1/c.json?session=abc"
    assert _absolutise("d.glb", parent) == "https://tile.googleapis.com/v1/a/b/d.glb?session=abc"


def test_absolutise_keeps_an_existing_session_token() -> None:
    parent = "https://tile.googleapis.com/v1/root.json?session=old"
    assert _absolutise("/v1/c.json?session=new", parent).endswith("session=new")


# ── Tree walking ──────────────────────────────────────────────────────


def test_building_level_mesh_counts_as_covered() -> None:
    seen: list[httpx.URL] = []
    with _client(_handler(_tileset(leaf_error=2.0), seen)) as client:
        r = _probe(client, KEY, POINT, _Budget(limit=50))

    assert r.covered
    assert r.content_nodes == 1
    assert r.min_geometric_error_m == 2.0
    assert r.requests_made == 2, "the far-away child must not be fetched"
    assert all(u.params.get("key") == KEY for u in seen), "every request needs the key"
    assert seen[1].params.get("session") == "s1", "the session token must be forwarded"


def test_coarse_mesh_only_is_not_covered() -> None:
    """Mesh exists, but too coarse to show a house: not building-level."""
    with _client(_handler(_tileset(leaf_error=50.0), [])) as client:
        r = _probe(client, KEY, POINT, _Budget(limit=50))

    assert r.content_nodes == 1
    assert not r.covered


def test_request_budget_stops_the_walk() -> None:
    with _client(_handler(_tileset(leaf_error=2.0), [])) as client:
        r = _probe(client, KEY, POINT, _Budget(limit=1))

    assert r.requests_made == 1
    assert not r.covered


def test_empty_budget_records_an_error() -> None:
    with _client(_handler(_tileset(leaf_error=2.0), [])) as client:
        r = _probe(client, KEY, POINT, _Budget(limit=0))

    assert r.error is not None
    assert not r.covered


def test_http_error_is_recorded_without_leaking_the_key() -> None:
    def forbidden(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text=f"key {KEY} is not authorised")

    with _client(forbidden) as client:
        r = _probe(client, KEY, POINT, _Budget(limit=5))

    assert r.error is not None
    assert r.error.startswith("HTTP 403")
    assert KEY not in r.error
    assert not r.covered


def test_malformed_response_is_recorded_as_an_error() -> None:
    def no_root(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with _client(no_root) as client:
        r = _probe(client, KEY, POINT, _Budget(limit=5))

    assert r.error is not None
    assert r.error.startswith("KeyError")


# ── Google-style box volumes ──────────────────────────────────────────
#
# Google's tileset uses oriented boxes in Earth-centred coordinates, not
# regions. These tests build boxes the same way, around the target point.


def _box(east_m: float = 0.0, up_m: float = 80.0, half_m: float = 300.0) -> list[float]:
    """A box centred ``east_m`` east of the target, aligned east/north/up."""
    lat, lon = _LAT, _LON
    east: Vec3 = (-math.sin(lon), math.cos(lon), 0.0)
    north: Vec3 = (-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat))
    up: Vec3 = (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))
    c = _ecef(lat, lon, up_m)
    centre = [c[i] + east[i] * east_m for i in range(3)]
    return [*centre, *(v * half_m for v in east), *(v * half_m for v in north)] + [
        v * 100.0 for v in up
    ]


def _box_tileset(*children_errors: float) -> dict[str, dict[str, Any]]:
    """Root box -> one external sub-tileset per error, plus one far-away child."""
    near = [
        {
            "boundingVolume": {"box": _box()},
            "geometricError": 500.0,
            "content": {"uri": f"/v1/3dtiles/datasets/x/files/sub{i}.json?session=s1"},
        }
        for i in range(len(children_errors))
    ]
    far = {
        "boundingVolume": {"box": _box(east_m=5_000.0)},
        "geometricError": 500.0,
        "content": {"uri": "/v1/3dtiles/datasets/x/files/far.json?session=s1"},
    }
    docs: dict[str, dict[str, Any]] = {
        "root.json": {
            "root": {
                "boundingVolume": {"box": _box(half_m=20_000.0)},
                "geometricError": 5000.0,
                "children": [far, *near],
            }
        }
    }
    for i, err in enumerate(children_errors):
        docs[f"sub{i}.json"] = {
            "root": {
                "boundingVolume": {"box": _box()},
                "geometricError": err,
                "content": {"uri": "leaf.glb"},
            }
        }
    return docs


def test_box_contains_the_point_and_rejects_a_neighbour() -> None:
    t = _target(POINT)
    assert _segment_hits_box(_box(), t.bottom, t.top)
    assert not _segment_hits_box(_box(east_m=5_000.0), t.bottom, t.top)


def test_box_far_above_the_point_is_rejected() -> None:
    t = _target(POINT)
    assert not _segment_hits_box(_box(up_m=5_000.0), t.bottom, t.top)


def test_sphere_volumes() -> None:
    t = _target(POINT)
    here = [*_ecef(_LAT, _LON, 80.0), 300.0]
    away = [*_box(east_m=5_000.0)[:3], 300.0]
    assert _segment_hits_sphere(here, t.bottom, t.top)
    assert not _segment_hits_sphere(away, t.bottom, t.top)


def test_box_tileset_is_walked_along_one_path() -> None:
    """The real-world failure: box volumes must prune, not crawl the tree."""
    seen: list[httpx.URL] = []
    with _client(_handler(_box_tileset(2.0), seen)) as client:
        r = _probe(client, KEY, POINT, _Budget(limit=50))

    assert r.covered
    assert r.requests_made == 2, "the far-away box must not be fetched"
    assert all("far.json" not in str(u) for u in seen)


def test_walk_stops_once_building_detail_is_found() -> None:
    with _client(_handler(_box_tileset(2.0, 2.0, 2.0), [])) as client:
        r = _probe(client, KEY, POINT, _Budget(limit=50))

    assert r.covered
    assert r.requests_made == 2, "no request is spent after the answer is known"


def test_each_point_gets_its_own_share_of_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REIN_GOOGLE_MAPS_API_KEY", KEY)
    monkeypatch.setenv("REIN_HTTP_MAX_REQUESTS", "4")
    get_settings.cache_clear()

    transport = httpx.MockTransport(_handler(_box_tileset(2.0), []))
    report = run_probes([POINT, POINT], transport=transport)

    assert report["requests_per_point_limit"] == 2
    assert report["points_covered"] == 2, "the first point must not starve the second"


# ── Verdicts and the full run ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("covered", "total", "expected"),
    [(4, 4, "COVERED"), (2, 4, "PARTIAL"), (0, 4, "NOT_COVERED"), (0, 0, "NOT_COVERED")],
)
def test_verdict(covered: int, total: int, expected: str) -> None:
    assert _verdict(covered, total) == expected


def test_run_probes_builds_a_serialisable_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REIN_GOOGLE_MAPS_API_KEY", KEY)
    get_settings.cache_clear()

    transport = httpx.MockTransport(_handler(_tileset(leaf_error=2.0), []))
    report = run_probes([POINT], transport=transport)

    assert report["verdict"] == "COVERED"
    assert report["points_covered"] == 1
    assert KEY not in json.dumps(report), "the key must never reach the saved artifact"


def test_run_probes_without_a_key_raises() -> None:
    with pytest.raises(RuntimeError, match="REIN_GOOGLE_MAPS_API_KEY"):
        run_probes([POINT])


def test_main_writes_the_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = {"verdict": "PARTIAL", "points_covered": 1, "points_total": 2}
    monkeypatch.setattr(tiles, "run_probes", lambda: fake)
    monkeypatch.setattr(tiles, "DATA_PROCESSED", tmp_path)

    assert tiles.main() == 0
    saved = json.loads((tmp_path / "v1_tiles_coverage.json").read_text(encoding="utf-8"))
    assert saved["verdict"] == "PARTIAL"


def test_main_returns_1_when_nothing_is_covered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = {"verdict": "NOT_COVERED", "points_covered": 0, "points_total": 4}
    monkeypatch.setattr(tiles, "run_probes", lambda: fake)
    monkeypatch.setattr(tiles, "DATA_PROCESSED", tmp_path)

    assert tiles.main() == 1


def test_main_returns_2_on_missing_key() -> None:
    assert tiles.main() == 2
