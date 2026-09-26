import math

import pytest

from geo import compute_bearing, from_local, haversine_m, square_bbox, to_local

LAT0, LON0 = 48.28646, 17.27221


@pytest.mark.parametrize("x,y", [(140, 0), (0, 140), (-140, -140), (99, -37)])
def test_local_projection_matches_haversine(x, y):
    lat, lon = from_local(x, y, LAT0, LON0)
    assert haversine_m(LAT0, LON0, lat, lon) == pytest.approx(math.hypot(x, y), abs=0.5)


def test_roundtrip():
    lat, lon = from_local(12.3, -45.6, LAT0, LON0)
    x, y = to_local(lat, lon, LAT0, LON0)
    assert x == pytest.approx(12.3, abs=1e-6)
    assert y == pytest.approx(-45.6, abs=1e-6)


def test_bearing_north_and_east():
    lat, lon = from_local(0, 1000, LAT0, LON0)
    assert compute_bearing(LAT0, LON0, lat, lon) == pytest.approx(0, abs=0.5)
    lat, lon = from_local(1000, 0, LAT0, LON0)
    assert compute_bearing(LAT0, LON0, lat, lon) == pytest.approx(90, abs=0.5)


def test_square_bbox():
    s, w, n, e = square_bbox(LAT0, LON0, 160)
    assert s < LAT0 < n and w < LON0 < e
    assert haversine_m(s, LON0, n, LON0) == pytest.approx(320, abs=0.5)
