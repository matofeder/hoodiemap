import time

import httpx
import pytest

import osm
from config import OverpassConfig
from geo import square_bbox
from osm import OverpassError, build_area_query, build_poi_query, categorize_poi, endpoints_for, run_query


def _transport(responses, calls):
    def handler(request):
        calls.append(str(request.url))
        status, body = responses[len(calls) - 1]
        if isinstance(body, dict):
            return httpx.Response(status, json=body)
        return httpx.Response(status, text=body)
    return httpx.MockTransport(handler)


def test_area_query_contains_bbox_and_layers():
    q = build_area_query(48.1, 17.1, 48.2, 17.2)
    assert "(48.100000,17.100000,48.200000,17.200000)" in q
    for part in ['way["building"]', 'relation["building"]', 'way["highway"]', 'node["natural"="tree"]',
                 '"leisure"~"^(park|garden|playground)$"', '"natural"~"^(water|wood)$"', '"waterway"="riverbank"']:
        assert part in q
    assert q.rstrip().endswith("out geom;")


def test_poi_query_uses_bbox_per_category_radius():
    # bbox filters are index-backed; large around: filters time out on busy Overpass servers
    q = build_poi_query(48.0, 17.0, ["hospital", "pharmacy"])
    s, w, n, e = square_bbox(48.0, 17.0, 30_000)
    assert f'nwr["amenity"="hospital"]({s:.6f},{w:.6f},{n:.6f},{e:.6f});' in q
    s, w, n, e = square_bbox(48.0, 17.0, 5_000)
    assert f'nwr["amenity"="pharmacy"]({s:.6f},{w:.6f},{n:.6f},{e:.6f});' in q
    assert "around" not in q
    assert "supermarket" not in q
    assert q.rstrip().endswith("out bb tags;")


def test_falls_back_to_next_endpoint_on_406():
    calls = []
    t = _transport([(406, "Not Acceptable"), (200, {"elements": [1]})], calls)
    assert run_query("q", cache_dir=None, transport=t) == {"elements": [1]}
    assert calls[0].startswith(osm.ENDPOINTS[0])
    assert calls[1].startswith(osm.ENDPOINTS[1])


def test_timeout_falls_back():
    n = {"i": 0}

    def handler(request):
        n["i"] += 1
        if n["i"] == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"elements": [3]})

    assert run_query("q", None, transport=httpx.MockTransport(handler)) == {"elements": [3]}


def test_sends_user_agent():
    seen = {}

    def handler(request):
        seen["ua"] = request.headers["user-agent"]
        return httpx.Response(200, json={"elements": []})

    run_query("q", None, transport=httpx.MockTransport(handler))
    assert seen["ua"] == osm.USER_AGENT


def test_raises_when_all_endpoints_fail():
    calls = []
    t = _transport([(429, "busy")] * len(osm.ENDPOINTS), calls)
    with pytest.raises(OverpassError):
        run_query("q", None, transport=t)
    assert len(calls) == len(osm.ENDPOINTS)


def test_runtime_error_remark_counts_as_failure():
    calls = []
    t = _transport([(200, {"remark": "runtime error: Query timed out", "elements": []}),
                    (200, {"elements": [2]})], calls)
    assert run_query("q", None, transport=t) == {"elements": [2]}


def test_cache_hit_skips_network(tmp_path):
    calls = []
    t = _transport([(200, {"elements": [4]})], calls)
    run_query("q", str(tmp_path), transport=t)
    assert run_query("q", str(tmp_path), transport=t) == {"elements": [4]}
    assert len(calls) == 1


def test_cache_expires(tmp_path, monkeypatch):
    calls = []
    t = _transport([(200, {"elements": [5]}), (200, {"elements": [6]})], calls)
    run_query("q", str(tmp_path), transport=t)
    later = time.time() + osm.CACHE_TTL_S + 1
    monkeypatch.setattr(osm.time, "time", lambda: later)
    assert run_query("q", str(tmp_path), transport=t) == {"elements": [6]}


def test_corrupt_cache_is_ignored(tmp_path):
    p = osm._cache_file("q", str(tmp_path))
    p.parent.mkdir(parents=True)
    p.write_text("{not json", encoding="utf-8")
    t = _transport([(200, {"elements": [7]})], [])
    assert run_query("q", str(tmp_path), transport=t) == {"elements": [7]}


def test_cache_disabled_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_query("q", None, transport=_transport([(200, {"elements": []})], []))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "hospital"}, "hospital"),
    ({"shop": "supermarket"}, "supermarket"),
    ({"amenity": "school"}, "school"),
    ({"amenity": "kindergarten"}, "kindergarten"),
    ({"amenity": "pharmacy"}, "pharmacy"),
    ({"highway": "bus_stop"}, "bus_stop"),
    ({"railway": "station"}, "train"),
    ({"railway": "halt"}, "train"),
    ({"leisure": "park"}, "park"),
    ({"leisure": "playground"}, "playground"),
    ({"amenity": "cafe"}, "food"),
    ({"amenity": "restaurant"}, "food"),
    ({"amenity": "post_office"}, "post"),
    ({"amenity": "bank"}, "bank"),
    ({"amenity": "dentist"}, "doctors"),
    ({"place": "city"}, "city"),
    ({"place": "town"}, None),
    ({"amenity": "bar"}, None),
    ({}, None),
])
def test_categorize_poi(tags, expected):
    assert categorize_poi(tags) == expected


def test_cache_write_failure_still_returns_data(tmp_path, monkeypatch):
    def broken(*a):
        raise OSError("read-only file system")

    monkeypatch.setattr(osm, "_cache_write", broken)
    t = _transport([(200, {"elements": [8]})], [])
    assert run_query("q", str(tmp_path), transport=t) == {"elements": [8]}


def test_cache_write_is_atomic(tmp_path):
    osm._cache_write("q", {"elements": [9]}, str(tmp_path))
    assert [p.name for p in osm._cache_file("q", str(tmp_path)).parent.iterdir()] == [osm._cache_file("q", str(tmp_path)).name]


def test_street_query_escapes_name_and_uses_around():
    from osm import build_street_query
    q = build_street_query('Nám. "SNP" \\ 1', 48.1, 17.1)
    assert '["name"="Nám. \\"SNP\\" \\\\ 1"]' in q
    assert "(around:1500,48.100000,17.100000)" in q
    assert q.startswith("[out:json][timeout:25];way[\"highway\"]") and q.rstrip().endswith("out geom;")


def test_run_query_reports_cache_hits_in_stats(tmp_path):
    stats = []
    t = _transport([(200, {"elements": [1]})], [])
    run_query("q", str(tmp_path), transport=t, stats=stats)
    run_query("q", str(tmp_path), transport=t, stats=stats)
    assert stats == [False, True]


def test_run_query_passes_timeout(monkeypatch):
    seen = {}
    real = httpx.Client

    def spy(*a, **kw):
        seen["timeout"] = kw.get("timeout")
        return real(*a, **kw)

    monkeypatch.setattr(osm.httpx, "Client", spy)
    run_query("q", None, transport=_transport([(200, {"elements": []})], []), timeout_s=70)
    assert seen["timeout"].read == 70 and seen["timeout"].connect == 2.0


@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "townhall", "wikidata": "Q1"}, (1, "Radnica")),
    ({"place": "square", "name": "Hlavné námestie"}, (2, "Námestie")),
    ({"highway": "pedestrian", "area": "yes", "name": "Radničné námestie"}, (2, "Námestie")),
    ({"highway": "pedestrian", "area": "yes"}, None),
    ({"historic": "castle"}, (3, "Hrad")),
    ({"historic": "castle", "castle_type": "palace"}, (3, "Palác")),
    ({"historic": "castle", "castle_type": "stately"}, (3, "Palác")),
    ({"historic": "castle", "castle_type": "manor"}, (3, "Kaštieľ")),
    ({"historic": "manor"}, (3, "Kaštieľ")),
    ({"building": "church"}, (4, "Kostol")),
    ({"amenity": "place_of_worship"}, (4, "Kostol")),
    ({"tourism": "museum"}, (5, "Múzeum")),
    ({"tourism": "attraction"}, (5, "Pamiatka")),
    ({"shop": "bakery"}, None),
])
def test_landmark_kind(tags, expected):
    from osm import landmark_kind
    assert landmark_kind(tags) == expected


@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "bus_station"}, "bus_station"),
    ({"shop": "mall"}, "mall"),
    ({"amenity": "townhall"}, "landmark"),
    ({"amenity": "pharmacy", "tourism": "attraction"}, "pharmacy"),  # existing categories win
])
def test_categorize_city_tier_tags(tags, expected):
    assert categorize_poi(tags) == expected


def test_poi_query_landmarks_use_the_map_square():
    q = build_poi_query(48.0, 17.0, ["landmark", "mall"], square_m=450)
    s, w, n, e = square_bbox(48.0, 17.0, 450)
    bbox = f"({s:.6f},{w:.6f},{n:.6f},{e:.6f})"
    for sel in ['["amenity"="townhall"]', '["place"="square"]', '["historic"~"^(castle|manor)$"]',
                '["building"~"^(church|cathedral)$"]', '["amenity"="place_of_worship"]',
                '["tourism"~"^(museum|attraction)$"]']:
        assert f"nwr{sel}{bbox};" in q
    s, w, n, e = square_bbox(48.0, 17.0, 15_000)
    assert f'nwr["shop"="mall"]({s:.6f},{w:.6f},{n:.6f},{e:.6f});' in q


def test_light_area_query_skips_footways_and_trees():
    q = build_area_query(48.1, 17.1, 48.2, 17.2, light=True)
    assert q.startswith("[out:json][timeout:60];")
    assert 'way["highway"]["highway"!~"^(footway|path|steps|track|cycleway)$"]' in q
    assert '"natural"="tree"' not in q
    assert build_area_query(48.1, 17.1, 48.2, 17.2).startswith("[out:json][timeout:25];")


LOCAL = "http://localhost:12345/api/interpreter"


def test_endpoints_local_first_inside_coverage_public_only_outside():
    ocfg = OverpassConfig(local_url=LOCAL)
    assert endpoints_for(48.2865, 17.2722, ocfg) == [LOCAL, *ocfg.public_endpoints]   # Pezinok
    assert endpoints_for(49.1951, 16.6068, ocfg) == ocfg.public_endpoints             # Brno
    assert endpoints_for(48.2865, 17.2722, OverpassConfig()) == OverpassConfig().public_endpoints


def test_run_query_uses_given_endpoints_and_falls_through_a_refused_local():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if str(request.url).startswith(LOCAL):
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json={"elements": [1]})

    out = run_query("q", None, transport=httpx.MockTransport(handler), endpoints=[LOCAL, "https://pub.example/api"])
    assert out == {"elements": [1]}
    assert calls == [LOCAL, "https://pub.example/api"]


def test_run_query_treats_an_importing_local_instance_as_failed():
    def handler(request):
        if str(request.url).startswith(LOCAL):
            return httpx.Response(200, json={"remark": "runtime error: database not ready", "elements": []})
        return httpx.Response(200, json={"elements": [2]})

    assert run_query("q", None, transport=httpx.MockTransport(handler),
                     endpoints=[LOCAL, "https://pub.example/api"]) == {"elements": [2]}


def test_empty_answers_are_not_cached(tmp_path):
    calls = []
    t = _transport([(200, {"elements": []}), (200, {"elements": [3]})], calls)
    assert run_query("q", str(tmp_path), transport=t) == {"elements": []}
    assert run_query("q", str(tmp_path), transport=t) == {"elements": [3]}   # second call went to the network
    assert len(calls) == 2


def test_fetchers_pass_endpoints_through(monkeypatch):
    seen = []
    monkeypatch.setattr(osm, "run_query", lambda q, cache, **kw: seen.append(kw.get("endpoints")) or {"elements": []})
    osm.fetch_area(48.0, 17.0, 140, None, endpoints=["x"])
    osm.fetch_pois(48.0, 17.0, ["pharmacy"], None, endpoints=["y"])
    osm.fetch_street("Hlavná", 48.0, 17.0, None, endpoints=["z"])
    assert seen == [["x"], ["y"], ["z"]]


def test_refresh_skips_cache_read_and_overwrites_entry(tmp_path):
    cache = str(tmp_path)
    assert run_query("q", cache, transport=_transport([(200, {"elements": [1]})], [])) == {"elements": [1]}
    calls = []
    fresh = run_query("q", cache, transport=_transport([(200, {"elements": [1, 2]})], calls),
                      endpoints=["http://public/api"], refresh=True)
    assert fresh == {"elements": [1, 2]} and calls == ["http://public/api"]
    assert run_query("q", cache, transport=_transport([], [])) == {"elements": [1, 2]}  # cache holds the new answer


def test_fetch_helpers_pass_refresh(monkeypatch):
    seen = []
    monkeypatch.setattr(osm, "run_query", lambda q, cache, **kw: seen.append(kw.get("refresh")) or {"elements": []})
    osm.fetch_area(48.0, 17.0, 140, None, refresh=True)
    osm.fetch_pois(48.0, 17.0, ["pharmacy"], None, refresh=True)
    assert seen == [True, True]


def test_endpoints_is_config_public_list():
    from config import PUBLIC_OVERPASS
    assert osm.ENDPOINTS == PUBLIC_OVERPASS
