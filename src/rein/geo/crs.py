"""Coordinate reference systems, and guards against the classic GIS bug."""

from __future__ import annotations

from typing import Final

# Storage / interchange CRS: what OSM, GeoJSON and GPS speak.Final
GEOGRAPHIC_CRS: Final[str] = "EPSG:4326"


# Working CRS for College Station, Texas.
PROJECTED_CRS: Final[str] = "EPSG:32614"


def utm_zone_for_longitude(longitude_deg: float) -> int:
    """Return the UTM zone number containing a longitude."""
    if not -180.0 <= longitude_deg <= 180.0:
        msg = f"longitude out of range: {longitude_deg}"
        raise ValueError(msg)
    return int((longitude_deg + 180.0) // 6.0) + 1


def assert_projected(crs_string: str | None) -> None:
    """Guard a metric operation against being handed degrees."""
    if crs_string is None:
        msg = "GeoDataFrame has no CRS. Metric operations are meaningless."
        raise ValueError(msg)
    if str(crs_string).upper().endswith("4326"):
        msg = (
            f"Refusing a metric operation in {crs_string} (degrees). "
            f"Reproject with .to_crs(PROJECTED_CRS) first."
        )
        raise ValueError(msg)
