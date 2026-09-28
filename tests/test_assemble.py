import json

import pytest

import scene_builder
from geo import from_local
from osm import OverpassError
from scene_builder import assemble_scene, build_scene, find_property, split_pois
from scene_builder import TIER_CATEGORIES, select_landmarks

LAT0, LON0 = 48.28646, 17.27221
R = 140
CATS = ["hospital", "supermarket", "school", "kindergarten", "pharmacy", "bus_stop", "train", "park",
        "playground", "food", "post", "bank", "doctors", "city"]


def cats(tier):
    return [c for c in CATS + ["bus_station", "mall", "landmark"] if c in TIER_CATEGORIES[tier]]


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


def test_pedestrian_line_is_own_road_kind_and_area_becomes_plaza():
    s = scene([
        way([(-50, 0), (50, 0)], {"highway": "pedestrian"}, closed=False, id=1),
        way(rect(-30, 20, 30, 60), {"highway": "pedestrian", "area": "yes"}, id=2),
        way(rect(40, -60, 80, -20), {"place": "square"}, id=3),
    ])
    assert [r["kind"] for r in s["roads"]] == ["pedestrian"]
    assert len(s["areas"]["plaza"]) == 2


def test_empty_area_gives_valid_scene():
    s = scene([])
    assert s["buildings"] == [] and s["roads"] == [] and s["trees"] == []
    assert s["property"] == {"building_index": None}
    assert s["areas"] == {"park": [], "water": [], "forest": [], "plaza": []}
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


def test_opening_hours_are_passed_through():
    pois = [node(20, 20, {"amenity": "pharmacy", "name": "L", "opening_hours": "Mo-Fr 08:00-18:00"}, 1),
            node(-20, 20, {"shop": "supermarket"}, 2)]
    near, _ = split_pois(LAT0, LON0, R, {"elements": pois}, CATS)
    by_cat = {p["category"]: p for p in near}
    assert by_cat["pharmacy"]["opening_hours"] == "Mo-Fr 08:00-18:00"
    assert "opening_hours" not in by_cat["supermarket"]


def test_specialized_hospital_is_skipped():
    pois = [
        node(0, 1000, {"amenity": "hospital", "name": "Psychiatrická nemocnica"}, 1),
        node(0, 2000, {"amenity": "hospital", "name": "Onko", "healthcare:speciality": "oncology"}, 2),
        node(0, 3000, {"amenity": "hospital", "name": "Nemocnica"}, 3),
    ]
    _, far = split_pois(LAT0, LON0, R, {"elements": pois}, CATS)
    assert [p["name"] for p in far] == ["Nemocnica"]


def bounds(x0, y0, x1, y1):
    a, b = ll(x0, y0), ll(x1, y1)
    return {"minlat": a["lat"], "minlon": a["lon"], "maxlat": b["lat"], "maxlon": b["lon"]}


def test_small_unnamed_park_is_ignored_named_or_big_is_kept():
    pois = [
        {"type": "way", "id": 1, "bounds": bounds(-20, -20, 0, 10), "tags": {"leisure": "park"}},
        {"type": "way", "id": 2, "bounds": bounds(40, 40, 60, 60), "tags": {"leisure": "park", "name": "Sad"}},
        {"type": "way", "id": 3, "bounds": bounds(-300, 0, -200, 100), "tags": {"leisure": "park"}},
    ]
    near, _ = split_pois(LAT0, LON0, R, {"elements": pois}, CATS)
    assert [p["name"] for p in near] == ["Sad"]
    assert near[0]["x"] == pytest.approx(50, abs=0.5)
    _, far = split_pois(LAT0, LON0, R, {"elements": [pois[0], pois[2]]}, CATS)
    assert far[0]["category"] == "park" and far[0]["distance_m"] == pytest.approx(255, abs=2)


def test_playground_is_its_own_local_category():
    near, far = split_pois(LAT0, LON0, R, {"elements": [node(20, 20, {"leisure": "playground"})]}, CATS)
    assert [p["category"] for p in near] == ["playground"] and far == []


def test_local_categories_only_when_on_map():
    pois = [node(20, 20, {"amenity": "cafe", "name": "Kaviareň"}, 1), node(0, 250, {"amenity": "bank"}, 2)]
    near, far = split_pois(LAT0, LON0, R, {"elements": pois}, CATS)
    assert [p["category"] for p in near] == ["food"]
    assert far == []


def test_two_nearest_cities_are_far_badges_skipping_own_city():
    pois = [
        node(0, 2000, {"place": "city", "name": "Domov"}, 1),
        node(0, 20000, {"place": "city", "name": "Bratislava"}, 2),
        {"type": "relation", "id": 3, "center": ll(0, 20500), "tags": {"place": "city", "name": "Bratislava"}},
        node(30000, 0, {"place": "city", "name": "Trnava"}, 4),
        node(0, -60000, {"place": "city", "name": "Ďaleko"}, 5),
    ]
    near, far = split_pois(LAT0, LON0, R, {"elements": pois}, CATS)
    assert near == []
    assert [(p["category"], p["name"]) for p in far] == [("city", "Bratislava"), ("city", "Trnava")]
    assert far[1]["bearing_deg"] == pytest.approx(90, abs=0.5)


def test_near_poi_gets_its_building():
    s = scene(
        [way(rect(-5, -5, 5, 5), {"building": "house"}, id=1), way(rect(40, 40, 70, 60), {"building": "retail"}, id=2)],
        [node(50, 50, {"shop": "supermarket", "name": "Billa"}, 3), node(-100, 100, {"leisure": "park", "name": "P"}, 4)],
    )
    shop = next(p for p in s["near_pois"] if p["category"] == "supermarket")
    park = next(p for p in s["near_pois"] if p["category"] == "park")
    assert shop["building_index"] == 1
    assert "building_index" not in park


def test_poi_building_skips_property_and_far_buildings():
    from scene_builder import poi_building
    blds = [{"footprint": [[0, 0], [10, 0], [10, 10], [0, 10]], "kind": "house"},
            {"footprint": [[30, 0], [40, 0], [40, 10], [30, 10]], "kind": "house"}]
    assert poi_building({"x": 5, "y": 5}, blds, exclude=0) is None
    assert poi_building({"x": 43, "y": 5}, blds, exclude=0) == 1
    assert poi_building({"x": 60, "y": 5}, blds, exclude=None) is None


def test_build_scene_poi_failure_adds_warning(monkeypatch, default_config):
    monkeypatch.setattr(scene_builder, "fetch_area", lambda *a, **k: {"elements": []})

    def boom(*a, **k):
        raise OverpassError("down")

    monkeypatch.setattr(scene_builder, "fetch_pois", boom)
    s = build_scene(LAT0, LON0, default_config)
    assert s["warnings"] == ["poi_fetch_failed"]
    assert s["far_pois"] == []


def test_build_scene_area_failure_raises(monkeypatch, default_config):
    def boom(*a, **k):
        raise OverpassError("down")

    monkeypatch.setattr(scene_builder, "fetch_area", boom)
    monkeypatch.setattr(scene_builder, "fetch_pois", lambda *a, **k: {"elements": []})
    with pytest.raises(OverpassError):
        build_scene(LAT0, LON0, default_config)


def test_build_scene_fetches_area_and_pois_concurrently(monkeypatch, default_config):
    import time

    def slow_area(*a, **k):
        time.sleep(0.3)
        return {"elements": []}

    def slow_pois(*a, **k):
        time.sleep(0.3)
        return {"elements": []}

    monkeypatch.setattr(scene_builder, "fetch_area", slow_area)
    monkeypatch.setattr(scene_builder, "fetch_pois", slow_pois)
    t0 = time.perf_counter()
    build_scene(LAT0, LON0, default_config)
    assert time.perf_counter() - t0 < 0.5


def test_tier_categories():
    assert "school" in TIER_CATEGORIES["street"] and "food" in TIER_CATEGORIES["street"]
    assert TIER_CATEGORIES["city"] == frozenset(
        {"hospital", "train", "park", "supermarket", "bus_station", "mall", "landmark", "city"})


def test_street_distances_are_measured_to_the_street():
    street = [[(-100, 50), (100, 50)]]
    pois = [node(0, 60, {"amenity": "school", "name": "ZŠ"}, 1)]
    near, _ = split_pois(LAT0, LON0, R, {"elements": pois}, CATS, street=street)
    assert near[0]["distance_m"] == 10           # 10 m from the street, 60 m from the centre


def test_landmarks_need_wiki_are_capped_and_one_per_kind():
    wiki = {"wikidata": "Q1"}
    pois = [
        node(10, 10, {"amenity": "townhall", "name": "Radnica", **wiki}, 1),
        node(20, 0, {"amenity": "townhall", "name": "Druhá radnica", **wiki}, 2),   # same kind -> dropped
        node(-30, 0, {"building": "church", "name": "Kostol sv. Martina", **wiki}, 3),
        node(0, -40, {"tourism": "museum", "name": "Múzeum", "wikipedia": "sk:Múzeum"}, 4),
        node(5, 5, {"historic": "castle", "name": "Bez wiki"}, 5),                  # no wiki -> dropped
        node(0, 60, {"historic": "castle", "name": "Hrad", **wiki}, 6),
        node(0, 500, {"place": "square", "name": "Ďaleko", **wiki}, 7),             # outside the square
    ]
    picked = select_landmarks(LAT0, LON0, R, {"elements": pois})
    assert [(p["kind"], p["name"]) for p in picked] == [("Radnica", "Radnica"), ("Hrad", "Hrad"), ("Kostol", "Kostol sv. Martina")]
    assert all(p["category"] == "landmark" and "x" in p for p in picked)


def test_city_scene_has_no_property_and_landmarks_near():
    s = assemble_scene(LAT0, LON0, R, {"elements": [way(rect(-5, -5, 5, 5), {"building": "house"})]},
                       {"elements": [node(10, 10, {"amenity": "townhall", "name": "Radnica", "wikidata": "Q1"}, 1),
                                     node(0, 5000, {"amenity": "school"}, 2)]},
                       cats("city"), tier="city")
    assert s["tier"] == "city" and s["focus"] == {"kind": "centre"}
    assert s["property"] == {"building_index": None}
    assert [p["category"] for p in s["near_pois"]] == ["landmark"]
    assert s["far_pois"] == []                   # school is not a city-tier category


def test_street_scene_focus_lines_clipped_and_anchor():
    street = [[(-300, 20), (300, 20)]]
    s = assemble_scene(LAT0, LON0, R, {"elements": []}, {"elements": []}, cats("street"), tier="street", street=street)
    assert s["focus"]["kind"] == "street"
    xs = [x for line in s["focus"]["lines"] for x, _ in line]
    assert min(xs) == pytest.approx(-R) and max(xs) == pytest.approx(R)
    assert s["focus"]["anchor"] == pytest.approx([0, 20])
    assert s["property"] == {"building_index": None}


def test_address_scene_focus_is_building():
    s = scene([way(rect(-5, -5, 5, 5), {"building": "house"})])
    assert s["tier"] == "address" and s["focus"] == {"kind": "building"}
    assert s["property"] == {"building_index": 0}


def test_build_scene_street_tier_recentres_and_reports_timing(monkeypatch, default_config):
    street_raw = {"elements": [way([(0, 0), (200, 0)], {"highway": "residential", "name": "Záhradná"}, closed=False)]}
    seen = {}
    monkeypatch.setattr(scene_builder, "fetch_street", lambda *a, **k: street_raw)

    def fake_area(lat, lon, half_m, cache_dir, light=False, stats=None, endpoints=None, refresh=False):
        seen.update(lat=lat, lon=lon, half=half_m, light=light)
        stats.append(True)
        return {"elements": []}

    def fake_pois(lat, lon, categories, cache_dir, square_m=0.0, stats=None, endpoints=None, refresh=False):
        seen["categories"] = categories
        stats.append(True)
        return {"elements": []}

    monkeypatch.setattr(scene_builder, "fetch_area", fake_area)
    monkeypatch.setattr(scene_builder, "fetch_pois", fake_pois)
    s = build_scene(LAT0, LON0, default_config, tier="street", name="Záhradná")
    expect_lat, expect_lon = from_local(100, 0, LAT0, LON0)
    assert (seen["lat"], seen["lon"]) == pytest.approx((expect_lat, expect_lon))
    assert seen["half"] == pytest.approx(160) and seen["light"] is False
    assert "school" in seen["categories"]
    assert s["focus"]["name"] == "Záhradná" and s["focus"]["anchor"] == pytest.approx([0, 0], abs=0.2)
    assert s["cached"] is True and isinstance(s["timing_ms"], int)


def test_build_scene_city_tier_is_light_and_street_failure_is_a_warning(monkeypatch, default_config):
    seen = {}

    def fake_area(lat, lon, half_m, cache_dir, light=False, stats=None, endpoints=None, refresh=False):
        seen.update(half=half_m, light=light)
        stats.append(False)
        return {"elements": []}

    monkeypatch.setattr(scene_builder, "fetch_area", fake_area)
    monkeypatch.setattr(scene_builder, "fetch_pois", lambda *a, **k: {"elements": []})
    s = build_scene(LAT0, LON0, default_config, tier="city")
    assert seen == {"half": 450, "light": True}
    assert s["cached"] is False

    def boom(*a, **k):
        raise OverpassError("down")

    monkeypatch.setattr(scene_builder, "fetch_street", boom)
    s = build_scene(LAT0, LON0, default_config, tier="street", name="X")
    assert s["warnings"] == ["street_fetch_failed"] and s["radius_m"] == 160


def test_street_distances_use_street_clipped_to_square():
    # The street run far past the visible square; a POI near the far end must not
    # win "nearest" just because it is close to the unclipped line.
    street = [[(-1000, 0), (1000, 0)]]
    pois = [
        node(800, 5, {"amenity": "pharmacy", "name": "Dr. Max"}, 1),
        node(60, 60, {"amenity": "pharmacy", "name": "Blizka"}, 2),
    ]
    near, far = split_pois(LAT0, LON0, R, {"elements": pois}, CATS, street=street)
    assert [p["name"] for p in near] == ["Blizka"]
    assert near[0]["distance_m"] == pytest.approx(60, abs=1)
    assert all(p["distance_m"] >= 10 for p in far)


def _cfg_with_local(default_config):
    from config import OverpassConfig
    return default_config.model_copy(update={"overpass": OverpassConfig(local_url="http://local/api")})


def test_build_scene_sends_local_first_inside_slovakia(monkeypatch, default_config):
    seen = []

    def fake_area(*a, endpoints=None, **k):
        seen.append(endpoints)
        return {"elements": [way(rect(0, 0, 10, 10), {"building": "house"})]}

    monkeypatch.setattr(scene_builder, "fetch_area", fake_area)
    monkeypatch.setattr(scene_builder, "fetch_pois", lambda *a, **k: {"elements": []})
    build_scene(LAT0, LON0, _cfg_with_local(default_config))
    assert seen[0][0] == "http://local/api"


def test_empty_local_area_is_refetched_from_public(monkeypatch, default_config):
    seen = []

    def fake_area(*a, endpoints=None, **k):
        seen.append(endpoints)
        local = endpoints[0] == "http://local/api"
        return {"elements": [] if local else [way(rect(0, 0, 10, 10), {"building": "house"})]}

    monkeypatch.setattr(scene_builder, "fetch_area", fake_area)
    monkeypatch.setattr(scene_builder, "fetch_pois", lambda *a, **k: {"elements": []})
    s = build_scene(LAT0, LON0, _cfg_with_local(default_config))
    assert len(seen) == 2 and seen[1][0] != "http://local/api"
    assert len(s["buildings"]) == 1
    assert "public_fallback" in s["warnings"]


def test_no_local_configured_means_no_refetch(monkeypatch, default_config):
    calls = []
    monkeypatch.setattr(scene_builder, "fetch_area", lambda *a, **k: calls.append(1) or {"elements": []})
    monkeypatch.setattr(scene_builder, "fetch_pois", lambda *a, **k: {"elements": []})
    build_scene(LAT0, LON0, default_config)
    assert calls == [1]


def _local_poi_fails(public_pois_ok):
    def fake_pois(*a, endpoints=None, **k):
        if endpoints[0] == "http://local/api" or not public_pois_ok:
            raise OverpassError("down")
        return {"elements": []}
    return fake_pois


def test_local_pois_failed_public_pois_ok_drops_poi_warning(monkeypatch, default_config):
    monkeypatch.setattr(scene_builder, "fetch_area", lambda *a, endpoints=None, **k: {"elements": []})
    monkeypatch.setattr(scene_builder, "fetch_pois", _local_poi_fails(True))
    s = build_scene(LAT0, LON0, _cfg_with_local(default_config))
    assert "poi_fetch_failed" not in s["warnings"] and "public_fallback" in s["warnings"]


def test_local_and_public_pois_failed_keeps_one_poi_warning(monkeypatch, default_config):
    monkeypatch.setattr(scene_builder, "fetch_area", lambda *a, endpoints=None, **k: {"elements": []})
    monkeypatch.setattr(scene_builder, "fetch_pois", _local_poi_fails(False))
    s = build_scene(LAT0, LON0, _cfg_with_local(default_config))
    assert s["warnings"].count("poi_fetch_failed") == 1 and "public_fallback" in s["warnings"]


def test_public_refetch_passes_refresh(monkeypatch, default_config):
    seen = []

    def fake_area(*a, endpoints=None, refresh=False, **k):
        seen.append(("area", endpoints[0], refresh))
        return {"elements": []}

    def fake_pois(*a, endpoints=None, refresh=False, **k):
        seen.append(("pois", endpoints[0], refresh))
        return {"elements": []}

    monkeypatch.setattr(scene_builder, "fetch_area", fake_area)
    monkeypatch.setattr(scene_builder, "fetch_pois", fake_pois)
    build_scene(LAT0, LON0, _cfg_with_local(default_config))
    public = [s for s in seen if s[1] != "http://local/api"]
    assert sorted(public) == [("area", public[0][1], True), ("pois", public[0][1], True)]
    assert all(s[2] is False for s in seen if s[1] == "http://local/api")


def test_partial_local_poi_answer_does_not_shadow_public_refetch(monkeypatch, default_config, tmp_path):
    import httpx
    import osm

    def handler(request):
        local = request.url.host == "local"
        body = request.content.decode()
        if "out+geom" in body or "out%20geom" in body or "out geom" in body:
            els = [] if local else [way(rect(0, 0, 10, 10), {"building": "house"})]
        else:
            n = 1 if local else 2
            els = [{"type": "node", "id": i, "lat": LAT0, "lon": LON0, "tags": {"amenity": "pharmacy", "name": f"P{i}"}}
                   for i in range(n)]
        return httpx.Response(200, json={"elements": els})

    real_client = httpx.Client
    monkeypatch.setattr(osm.httpx, "Client",
                        lambda **kw: real_client(**{**kw, "transport": httpx.MockTransport(handler)}))
    cfg = _cfg_with_local(default_config)
    cfg = cfg.model_copy(update={"cache": cfg.cache.model_copy(update={"enabled": True, "dir": str(tmp_path)})})
    captured = {}
    real_assemble = scene_builder.assemble_scene

    def spy(lat, lon, radius, area, pois_raw, *a, **k):
        captured["pois"] = pois_raw
        return real_assemble(lat, lon, radius, area, pois_raw, *a, **k)

    monkeypatch.setattr(scene_builder, "assemble_scene", spy)
    s = build_scene(LAT0, LON0, cfg)
    assert "public_fallback" in s["warnings"]
    assert len(captured["pois"]["elements"]) == 2
    files = [json.loads(p.read_text()) for p in (tmp_path / "osm").glob("*.json")]
    assert any(len(f["data"]["elements"]) == 2 for f in files)


def test_split_pois_drops_elements_with_invalid_bounds():
    # A relation whose members lie outside the local extract (Uzhhorod from Košice) comes back with
    # Overpass's "no bbox" sentinel bounds; its midpoint is near Antarctica (13 000 km away).
    broken = {"type": "relation", "id": 7, "tags": {"place": "city", "name": "Ужгород"},
              "bounds": {"minlat": -91.0, "minlon": 22.2, "maxlat": 48.66, "maxlon": -200.0}}
    near, far = split_pois(LAT0, LON0, R, {"elements": [broken]}, ["city"])
    assert near == [] and far == []


@pytest.mark.parametrize("cat,tags,dist_m,shown", [
    ("bus_station", {"amenity": "bus_station", "name": "Autobusová stanica Senec"}, 11_800, False),
    ("bus_station", {"amenity": "bus_station", "name": "AS"}, 2_500, True),
    ("train", {"railway": "station", "name": "Far"}, 25_000, False),
    ("hospital", {"amenity": "hospital", "name": "Nemocnica"}, 25_000, True),
    ("supermarket", {"shop": "supermarket", "name": "Far"}, 4_000, False),
    ("bus_stop", {"highway": "bus_stop", "name": "Far"}, 1_500, False),
])
def test_split_pois_hides_places_too_far_to_matter(cat, tags, dist_m, shown):
    el = {"type": "node", "id": 1, "tags": tags, **ll(0, dist_m)}
    _, far = split_pois(LAT0, LON0, R, {"elements": [el]}, [cat])
    assert bool(far) == shown
