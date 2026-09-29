"""V1 — Google Photorealistic 3D Tiles coverage verification."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from rein.config import DATA_PROCESSED, get_settings
from rein.geo.town import TARGET_TOWN
from rein.logging import configure_logging, get_logger

log = get_logger(__name__)

TILES_ROOT = "https://tile.googleapis.com/v1/3dtiles/root.json"
_BASE = "https://tile.googleapis.com"

# A node whose geometric error is at or below this, carrying real mesh
# content, indicates building-level detail. Chosen because a suburban house
# is ~8 m tall: an error budget above that cannot represent one.
BUILDING_DETAIL_ERROR_M = 8.0

# Safety bound on tree depth. Google's tree nests many external tilesets, so
# this is generous; the request budget is the real ceiling.
MAX_DEPTH = 64

# WGS 84 ellipsoid, for converting latitude/longitude to Earth-centred XYZ.
_WGS84_A = 6_378_137.0
_WGS84_E2 = 6.694_379_990_14e-3

# The vertical line tested against each volume, in metres above the ellipsoid.
# College Station's ground sits near 80 m; the range leaves wide margins.
_LINE_BOTTOM_M = -200.0
_LINE_TOP_M = 1_000.0

Vec3 = tuple[float, float, float]


@dataclass(slots=True)
class ProbePoint:
    """One coordinate to test."""

    label: str
    lat: float
    lon: float


@dataclass(slots=True)
class ProbeResult:
    """Evidence gathered for a single coordinate."""

    label: str
    lat: float
    lon: float
    max_depth: int = 0
    min_geometric_error: float = math.inf
    content_nodes: int = 0
    requests_made: int = 0
    error: str | None = None

    @property
    def covered(self) -> bool:
        """True if building-level mesh detail was reachable."""
        return (
            self.error is None
            and self.content_nodes > 0
            and self.min_geometric_error <= BUILDING_DETAIL_ERROR_M
        )

    @property
    def min_geometric_error_m(self) -> float | None:
        """Smallest geometric error reached, or None if no mesh was found."""
        if math.isinf(self.min_geometric_error):
            return None
        return round(self.min_geometric_error, 3)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable record of this probe."""
        return {
            "label": self.label,
            "lat": self.lat,
            "lon": self.lon,
            "max_depth": self.max_depth,
            "min_geometric_error_m": self.min_geometric_error_m,
            "content_nodes": self.content_nodes,
            "requests_made": self.requests_made,
            "covered": self.covered,
            "error": self.error,
        }


@dataclass(slots=True)
class _Budget:
    """Hard ceiling on requests, so a bug cannot become a metered crawl."""

    limit: int
    used: int = 0
    _warned: bool = field(default=False, repr=False)

    def spend(self) -> bool:
        if self.used >= self.limit:
            if not self._warned:
                log.warning("request_budget_exhausted", limit=self.limit)
                self._warned = True
            return False
        self.used += 1
        return True


@dataclass(frozen=True, slots=True)
class _Target:
    """The point being probed, in the two forms bounding volumes need."""

    lat_rad: float
    lon_rad: float
    bottom: Vec3
    top: Vec3


def _ecef(lat_rad: float, lon_rad: float, height_m: float) -> Vec3:
    """Convert latitude, longitude and ellipsoid height to Earth-centred XYZ."""
    sin_lat = math.sin(lat_rad)
    n = _WGS84_A / math.sqrt(1.0 - _WGS84_E2 * sin_lat * sin_lat)
    xy = (n + height_m) * math.cos(lat_rad)
    return (
        xy * math.cos(lon_rad),
        xy * math.sin(lon_rad),
        (n * (1.0 - _WGS84_E2) + height_m) * sin_lat,
    )


def _target(point: ProbePoint) -> _Target:
    lat, lon = math.radians(point.lat), math.radians(point.lon)
    return _Target(lat, lon, _ecef(lat, lon, _LINE_BOTTOM_M), _ecef(lat, lon, _LINE_TOP_M))


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _region_contains(region: list[float], lat_rad: float, lon_rad: float) -> bool:
    """Test a 3D Tiles ``region`` bounding volume, which is in RADIANS.

    Args:
        region: [west, south, east, north, min_h, max_h] in radians/metres.
        lat_rad: Latitude of the point, in radians.
        lon_rad: Longitude of the point, in radians.
    """
    west, south, east, north = region[0], region[1], region[2], region[3]
    if not south <= lat_rad <= north:
        return False
    if west <= east:
        return west <= lon_rad <= east
    # The region crosses the antimeridian (180 degrees), so longitude wraps.
    return lon_rad >= west or lon_rad <= east


def _segment_hits_box(box: list[float], start: Vec3, end: Vec3) -> bool:
    """Test whether a line segment passes through a 3D Tiles ``box`` volume.

    A box is a centre plus three half-axis vectors. Each end of the segment is
    expressed in the box's own axes, where the box is the cube -1..1 on every
    axis, and the segment is clipped against each pair of faces in turn (the
    "slab" method). Anything left over lies inside the box.
    """
    centre: Vec3 = (box[0], box[1], box[2])
    t_enter, t_exit = 0.0, 1.0
    for i in range(3):
        axis: Vec3 = (box[3 + 3 * i], box[4 + 3 * i], box[5 + 3 * i])
        length_sq = _dot(axis, axis)
        if length_sq == 0.0:
            continue  # a flat box: this axis cannot exclude anything
        s0 = _dot(_sub(start, centre), axis) / length_sq
        s1 = _dot(_sub(end, centre), axis) / length_sq
        if s0 == s1:
            if abs(s0) > 1.0:
                return False
            continue
        t_a, t_b = (-1.0 - s0) / (s1 - s0), (1.0 - s0) / (s1 - s0)
        t_enter = max(t_enter, min(t_a, t_b))
        t_exit = min(t_exit, max(t_a, t_b))
        if t_enter > t_exit:
            return False
    return True


def _segment_hits_sphere(sphere: list[float], start: Vec3, end: Vec3) -> bool:
    """Test whether a line segment passes through a ``sphere`` volume."""
    centre: Vec3 = (sphere[0], sphere[1], sphere[2])
    direction = _sub(end, start)
    t = _dot(_sub(centre, start), direction) / _dot(direction, direction)
    t = min(1.0, max(0.0, t))
    closest: Vec3 = (
        start[0] + t * direction[0],
        start[1] + t * direction[1],
        start[2] + t * direction[2],
    )
    offset = _sub(closest, centre)
    return _dot(offset, offset) <= sphere[3] * sphere[3]


def _volume_contains(volume: dict[str, Any], target: _Target) -> bool:
    """Decide whether a node's bounding volume can contain the target point.

    An unknown or missing volume is followed rather than skipped: a wasted
    request is cheap, a missed tile is a false "not covered".
    """
    if "region" in volume:
        return _region_contains(volume["region"], target.lat_rad, target.lon_rad)
    if "box" in volume:
        return _segment_hits_box(volume["box"], target.bottom, target.top)
    if "sphere" in volume:
        return _segment_hits_sphere(volume["sphere"], target.bottom, target.top)
    return True


def _absolutise(uri: str, parent_url: str) -> str:
    """Resolve a tile URI against its parent, preserving the session token."""
    if uri.startswith("http"):
        base = uri
    elif uri.startswith("/"):
        base = _BASE + uri
    else:
        base = f"{parent_url.split('?', 1)[0].rsplit('/', 1)[0]}/{uri}"
    # Google issues a session token on the root response; every subsequent
    # request must carry it or the service rejects the call.
    if "session=" not in base:
        session = parse_qs(urlparse(parent_url).query).get("session", [""])[0]
        if session:
            base += ("&" if "?" in base else "?") + f"session={session}"
    return base


def _with_key(url: str, key: str) -> str:
    return url + ("&" if "?" in url else "?") + f"key={key}"


def _scrub(text: str, key: str) -> str:
    """Remove the API key from any text that might be logged or saved."""
    return text.replace(key, "***") if key else text


def _probe(
    client: httpx.Client,
    key: str,
    point: ProbePoint,
    budget: _Budget,
    max_depth: int = MAX_DEPTH,
) -> ProbeResult:
    """Descend the tileset toward one coordinate, recording evidence.

    The walk stops as soon as building-level mesh is found: the question is
    whether that detail exists here, and every further request costs quota.
    """
    res = ProbeResult(label=point.label, lat=point.lat, lon=point.lon)
    target = _target(point)
    start_requests = budget.used

    try:
        if not budget.spend():
            res.error = "request budget exhausted before start"
            return res
        r = client.get(_with_key(TILES_ROOT, key))
        r.raise_for_status()
        stack: list[tuple[dict[str, Any], str, int]] = [(r.json()["root"], str(r.url), 0)]

        while stack and not res.covered:
            node, node_url, depth = stack.pop()
            if depth > max_depth:
                continue
            if not _volume_contains(node.get("boundingVolume", {}), target):
                continue

            res.max_depth = max(res.max_depth, depth)
            content = node.get("content") or {}
            uri = content.get("uri") or content.get("url")

            if uri:
                full = _absolutise(uri, node_url)
                if full.split("?", 1)[0].endswith(".json"):
                    # External tileset: fetch it and keep descending.
                    if not budget.spend():
                        break
                    sub = client.get(_with_key(full, key))
                    if sub.status_code == httpx.codes.OK:
                        sub_root = sub.json().get("root")
                        if sub_root:
                            stack.append((sub_root, str(sub.url), depth + 1))
                else:
                    # Real mesh content at this node.
                    res.content_nodes += 1
                    ge = float(node.get("geometricError", math.inf))
                    res.min_geometric_error = min(res.min_geometric_error, ge)

            stack.extend((child, node_url, depth + 1) for child in node.get("children") or [])

    except httpx.HTTPStatusError as exc:
        res.error = _scrub(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}", key)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        res.error = _scrub(f"{type(exc).__name__}: {exc}", key)

    res.requests_made = budget.used - start_requests
    return res


def _verdict(covered: int, total: int) -> str:
    """Summarise per-point results as COVERED, PARTIAL or NOT_COVERED."""
    if total > 0 and covered == total:
        return "COVERED"
    if covered > 0:
        return "PARTIAL"
    return "NOT_COVERED"


def default_points() -> list[ProbePoint]:
    """The four College Station locations sampled by default."""
    t = TARGET_TOWN
    return [
        ProbePoint("town centre", t.centre_lat, t.centre_lon),
        ProbePoint("residential subdivision", 30.6009, -96.3140),
        ProbePoint("Texas A&M campus", 30.6120, -96.3400),
        ProbePoint("commercial corridor", 30.6280, -96.3100),
    ]


def run_probes(
    points: list[ProbePoint] | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Probe several coordinates and return a JSON-serialisable evidence bundle.

    Each point gets an equal share of the request ceiling, so one point that
    needs many requests cannot starve the others.

    Args:
        points: Coordinates to test. Defaults to ``default_points()``.
        transport: Optional httpx transport. Tests pass a mock here so the
            logic can be verified without network access or API quota.
    """
    settings = get_settings()
    key = settings.require_google_key()
    points = points if points is not None else default_points()

    share = max(1, settings.http_max_requests // max(1, len(points)))
    results: list[ProbeResult] = []

    with httpx.Client(
        transport=transport,
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    ) as client:
        for p in points:
            log.info("probing", label=p.label, lat=p.lat, lon=p.lon)
            r = _probe(client, key, p, _Budget(limit=share))
            log.info(
                "probed",
                label=r.label,
                covered=r.covered,
                depth=r.max_depth,
                min_ge=r.min_geometric_error_m,
                content_nodes=r.content_nodes,
                requests=r.requests_made,
            )
            results.append(r)

    covered = sum(1 for r in results if r.covered)
    return {
        "check": "V1-google-3d-tiles-coverage",
        "town": TARGET_TOWN.name,
        "run_at": datetime.now(UTC).isoformat(),
        "threshold_geometric_error_m": BUILDING_DETAIL_ERROR_M,
        "requests_per_point_limit": share,
        "total_requests": sum(r.requests_made for r in results),
        "points": [r.as_dict() for r in results],
        "points_covered": covered,
        "points_total": len(results),
        "verdict": _verdict(covered, len(results)),
        "caveat": (
            "Geometric-error threshold is a heuristic, not a Google-published "
            "definition of coverage. Must be corroborated by visual inspection."
        ),
    }


def main() -> int:
    """CLI entry point: ``uv run rein-verify-tiles``.

    Returns:
        0 if at least one point is covered, 1 if none is, 2 on a
        configuration error such as a missing API key.
    """
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    try:
        report = run_probes()
    except RuntimeError as exc:
        log.error("configuration_error", detail=str(exc))
        return 2

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out = DATA_PROCESSED / "v1_tiles_coverage.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    log.info(
        "verdict",
        result=report["verdict"],
        covered=f"{report['points_covered']}/{report['points_total']}",
        artifact=str(out),
    )
    return 0 if report["verdict"] != "NOT_COVERED" else 1


if __name__ == "__main__":
    sys.exit(main())
