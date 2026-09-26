import pytest

from geo import from_local
from street import street_anchor, street_frame, street_lines

LAT0, LON0 = 48.28646, 17.27221


def way(pts, id=1):
    return {"type": "way", "id": id, "geometry": [dict(zip(("lat", "lon"), from_local(x, y, LAT0, LON0))) for x, y in pts]}


def test_joins_connected_ways_and_drops_same_name_far_away():
    raw = {"elements": [
        way([(0, 0), (100, 0)], 1),
        way([(110, 5), (200, 5)], 2),          # 10 m gap -> same street
        way([(900, 0), (1000, 0)], 3),         # another village, same name
        {"type": "node", "id": 4, "lat": LAT0, "lon": LON0},
    ]}
    lines = street_lines(raw, LAT0, LON0)
    assert len(lines) == 2
    assert max(x for line in lines for x, _ in line) == pytest.approx(200, abs=0.5)


def test_no_ways_gives_no_lines():
    assert street_lines({"elements": []}, LAT0, LON0) == []
    assert street_lines({"elements": [{"type": "way", "id": 1, "geometry": []}]}, LAT0, LON0) == []


def test_frame_centres_on_midpoint_with_margin():
    f = street_frame([[(0, 0), (200, 0)]], 160, 300)
    assert (f["x"], f["y"]) == pytest.approx((100, 0))
    assert f["radius_m"] == pytest.approx(160)       # 200/2 + 60 = 160
    f = street_frame([[(0, 0), (400, 0)]], 160, 300)
    assert f["radius_m"] == pytest.approx(260)


def test_frame_long_street_stays_on_point():
    f = street_frame([[(-3000, 0), (1000, 0)]], 160, 300)
    assert (f["x"], f["y"], f["radius_m"]) == (0.0, 0.0, 300)
    assert f["length_m"] == pytest.approx(4000)


def test_frame_branching_street_uses_bbox_centre():
    f = street_frame([[(0, 0), (100, 0)], [(50, -40), (50, 40)]], 160, 300)
    assert (f["x"], f["y"]) == pytest.approx((50, 0))


def test_frame_without_lines_is_minimal_on_point():
    assert street_frame([], 160, 300) == {"x": 0.0, "y": 0.0, "radius_m": 160, "length_m": 0.0}


def test_anchor_is_nearest_point_on_street():
    assert street_anchor([[(-50, 20), (50, 20)]]) == pytest.approx((0, 20))
    assert street_anchor([]) == (0.0, 0.0)
