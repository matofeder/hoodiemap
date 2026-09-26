import pytest

import scene_builder
from geo import from_local
from osm import OverpassError
from scene_builder import assemble_scene, build_scene, find_property, split_pois

LAT0, LON0 = 48.28646, 17.27221
R = 140
CATS = ["hospital", "supermarket", "school", "kindergarten", "pharmacy", "bus_stop", "train", "park"]


def ll(x, y):
    lat, lon = from_local(x, y, LAT0, LON0)
    return {"lat": lat, "lon": lon}


def way(pts, tags, closed=True, id=1):
    geom = [ll(*p) for p in pts]
    if closed:
        geom.append(geom[0])
    return {"type": "way", "id": id, "tags": tags, "geometry": geom}


def node(x, y, tags, id=1):
    return {"type": "node", "id": id, **ll(x, y), "tags": tags}


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def scene(elements, pois=()):
    return assemble_scene(LAT0, LON0, R, {"elements": list(elements)}, {"elements": list(pois)}, CATS)


def test_building_inside_is_kept_with_open_ring():
    s = scene([way(rect(10, 10, 30, 20), {"building": "house"})])
    b = s["buildings"][0]
    assert b["kind"] == "house" and b["height"] == 6.0
    assert len(b["footprint"]) == 4
    assert [10.0, 10.0] in b["footprint"]


def test_building_half_outside_is_clipped():
    s = scene([way(rect(130, 0, 150, 10), {"building": "yes"})])
    xs = [p[0] for p in s["buildings"][0]["footprint"]]
    assert max(xs) == pytest.approx(140, abs=0.1)


def test_mostly_outside_building_is_dropped():
    s = scene([way(rect(134, 0, 154, 10), {"building": "yes"})])
    assert s["buildings"] == []


def test_unclosed_or_tiny_building_is_skipped():
    s = scene([
        way(rect(0, 0, 10, 10), {"building": "yes"}, closed=False),
        way([(0, 0), (1, 0), (0, 1)], {"building": "yes"}),
    ])
    assert s["buildings"] == []


def test_self_intersecting_building_is_repaired():
    bowtie = [(0, 0), (20, 20), (20, 0), (0, 20)]
    s = scene([way(bowtie, {"building": "yes"})])
    assert all(len(b["footprint"]) >= 3 for b in s["buildings"])


def test_relation_multipolygon_outer_members_are_joined():
    rel = {"type": "relation", "id": 9, "tags": {"natural": "water"}, "members": [
        {"type": "way", "role": "outer", "geometry": [ll(0, 0), ll(20, 0), ll(20, 20)]},
        {"type": "way", "role": "outer", "geometry": [ll(20, 20), ll(0, 20), ll(0, 0)]},
    ]}
    s = scene([rel])
    assert len(s["areas"]["water"]) == 1


def test_road_is_clipped_to_square_and_kind_mapped():
    s = scene([way([(-300, 5), (300, 5)], {"highway": "secondary"}, closed=False)])
    road = s["roads"][0]
    assert road["kind"] == "main"
    assert road["points"][0][0] == pytest.approx(-140, abs=0.1)
    assert road["points"][-1][0] == pytest.approx(140, abs=0.1)


def test_unknown_highway_is_dropped():
    s = scene([way([(0, 0), (50, 0)], {"highway": "construction"}, closed=False)])
    assert s["roads"] == []


def test_trees_outside_square_are_dropped():
    s = scene([node(10, 10, {"natural": "tree"}, 1), node(200, 0, {"natural": "tree"}, 2)])
    assert s["trees"] == [{"x": 10.0, "y": 10.0}]


def test_park_is_clipped():
    s = scene([way(rect(100, -20, 200, 20), {"leisure": "park"})])
    xs = [p[0] for p in s["areas"]["park"][0]]
    assert max(xs) == pytest.approx(140, abs=0.1)


def test_empty_area_gives_valid_scene():
    s = scene([])
    assert s["buildings"] == [] and s["roads"] == [] and s["trees"] == []
    assert s["property"] == {"building_index": None}
    assert s["areas"] == {"park": [], "water": [], "forest": []}
    assert s["radius_m"] == R


def test_find_property_containing_nearest_and_none():
    inside = {"footprint": [[-5, -5], [5, -5], [5, 5], [-5, 5]]}
    near = {"footprint": [[10, 0], [20, 0], [20, 10], [10, 10]]}
    far = {"footprint": [[50, 0], [60, 0], [60, 10], [50, 10]]}
    assert find_property([near, inside]) == 1
    assert find_property([far, near]) == 1
    assert find_property([far]) is None


def test_split_pois_nearest_per_category_and_near_far():
    pois = [
        node(30, 40, {"amenity": "pharmacy", "name": "Near"}, 1),
        node(60, 60, {"amenity": "pharmacy", "name": "Farther"}, 2),
        {"type": "way", "id": 3, "center": ll(0, 2400), "tags": {"amenity": "hospital", "name": "Nemocnica"}},
        node(0, 0, {"amenity": "bar"}, 4),
        {"type": "way", "id": 5, "tags": {"amenity": "school"}},
    ]
    near, far = split_pois(LAT0, LON0, R, {"elements": pois}, CATS)
    assert [p["name"] for p in near] == ["Near"]
    assert near[0]["x"] == 30.0 and near[0]["distance_m"] == 50
    assert far == [{"category": "hospital", "name": "Nemocnica", "distance_m": 2400, "bearing_deg": 0.0}]


def test_poi_near_edge_goes_to_far():
    near, far = split_pois(LAT0, LON0, R, {"elements": [node(135, 0, {"amenity": "pharmacy"})]}, CATS)
    assert near == [] and far[0]["bearing_deg"] == pytest.approx(90, abs=0.5)


def test_disabled_category_is_ignored():
    near, far = split_pois(LAT0, LON0, R, {"elements": [node(10, 10, {"amenity": "pharmacy"})]}, ["hospital"])
    assert near == [] and far == []


def test_build_scene_poi_failure_adds_warning(monkeypatch, default_config):
    monkeypatch.setattr(scene_builder, "fetch_area", lambda *a: {"elements": []})

    def boom(*a):
        raise OverpassError("down")

    monkeypatch.setattr(scene_builder, "fetch_pois", boom)
    s = build_scene(LAT0, LON0, default_config)
    assert s["warnings"] == ["poi_fetch_failed"]
    assert s["far_pois"] == []


def test_build_scene_area_failure_raises(monkeypatch, default_config):
    def boom(*a):
        raise OverpassError("down")

    monkeypatch.setattr(scene_builder, "fetch_area", boom)
    monkeypatch.setattr(scene_builder, "fetch_pois", lambda *a: {"elements": []})
    with pytest.raises(OverpassError):
        build_scene(LAT0, LON0, default_config)


def test_build_scene_fetches_area_and_pois_concurrently(monkeypatch, default_config):
    import time

    def slow_area(*a):
        time.sleep(0.3)
        return {"elements": []}

    def slow_pois(*a):
        time.sleep(0.3)
        return {"elements": []}

    monkeypatch.setattr(scene_builder, "fetch_area", slow_area)
    monkeypatch.setattr(scene_builder, "fetch_pois", slow_pois)
    t0 = time.perf_counter()
    build_scene(LAT0, LON0, default_config)
    assert time.perf_counter() - t0 < 0.5
