import time

import httpx
import pytest

import osm
from osm import OverpassError, build_area_query, build_poi_query, categorize_poi, run_query


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


def test_poi_query_only_enabled_categories_with_radii():
    q = build_poi_query(48.0, 17.0, ["hospital", "pharmacy"])
    assert 'nwr["amenity"="hospital"](around:30000,48.000000,17.000000);' in q
    assert 'nwr["amenity"="pharmacy"](around:5000,48.000000,17.000000);' in q
    assert "supermarket" not in q
    assert q.rstrip().endswith("out center tags;")


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
    ({"leisure": "playground"}, "park"),
    ({"amenity": "bar"}, None),
    ({}, None),
])
def test_categorize_poi(tags, expected):
    assert categorize_poi(tags) == expected
