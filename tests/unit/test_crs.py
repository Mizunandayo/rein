"""Projection guard tests."""

from __future__ import annotations

import pytest

from rein.geo.crs import PROJECTED_CRS, assert_projected, utm_zone_for_longitude
from rein.geo.town import TARGET_TOWN


def test_target_town_falls_in_the_declared_utm_zone() -> None:
    """The hardcoded PROJECTED_CRS must actually match the town.

    This test is the reason the constant is safe to hardcode: if the town
    ever changes, this fails immediately rather than silently distorting
    every distance in the project.
    """
    assert utm_zone_for_longitude(TARGET_TOWN.centre_lon) == 14
    assert PROJECTED_CRS == "EPSG:32614"


@pytest.mark.parametrize(
    ("lon", "zone"),
    [(-177.0, 1), (-96.3344, 14), (-95.9, 15), (0.5, 31), (177.0, 60)],
)
def test_utm_zone_boundaries(lon: float, zone: int) -> None:
    assert utm_zone_for_longitude(lon) == zone


def test_rejects_geographic_crs_for_metric_work() -> None:
    with pytest.raises(ValueError, match="Refusing a metric operation"):
        assert_projected("EPSG:4326")


def test_rejects_missing_crs() -> None:
    with pytest.raises(ValueError, match="no CRS"):
        assert_projected(None)


def test_accepts_projected_crs() -> None:
    assert_projected(PROJECTED_CRS)  # must not raise
