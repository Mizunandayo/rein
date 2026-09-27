"""The town under study."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class Town:
    """A study area."""

    name: str
    osm_query: str
    centre_lat: float
    centre_lon: float
    timezone: str

    @property
    def centre_lonlat(self) -> tuple[float, float]:
        """Centre as (lon, lat) — the order shapely and GeoJSON expect."""
        return (self.centre_lon, self.centre_lat)


COLLEGE_STATION: Final[Town] = Town(
    name="College Station, Texas",
    osm_query="College Station, Texas, USA",
    centre_lat=30.6280,
    centre_lon=-96.3344,
    timezone="America/Chicago",
)

TARGET_TOWN: Final[Town] = COLLEGE_STATION
