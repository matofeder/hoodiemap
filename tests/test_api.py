from unittest.mock import AsyncMock, patch

import httpx
from httpx import ASGITransport, AsyncClient

from osm import OverpassError

SCENE = {
    "center": {"lat": 48.28, "lon": 17.27}, "radius_m": 140, "buildings": [],
    "property": {"building_index": None}, "roads": [],
    "areas": {"park": [], "water": [], "forest": [], "plaza": []}, "trees": [],
    "near_pois": [], "far_pois": [], "warnings": [],
}


async def _get(url):
    from api import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(url)


async def test_health():
    r = await _get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_scene_returns_scene_with_address():
    with patch("api.build_scene", return_value=dict(SCENE)), \
         patch("api._reverse_geocode", AsyncMock(return_value="Záhradná, Pezinok")):
        r = await _get("/api/scene?lat=48.28&lon=17.27")
    assert r.status_code == 200
    body = r.json()
    assert body["address"] == "Záhradná, Pezinok"
    assert body["far_pois"] == []


async def test_scene_502_when_area_fetch_fails():
    from api import AREA_FAILED_DETAIL
    with patch("api.build_scene", side_effect=OverpassError("all down")):
        r = await _get("/api/scene?lat=48.28&lon=17.27")
    assert r.status_code == 502
    assert r.json()["detail"] == AREA_FAILED_DETAIL


async def test_scene_rejects_invalid_lat():
    r = await _get("/api/scene?lat=100&lon=17")
    assert r.status_code == 422


async def test_fixture_mode_serves_new_format():
    r = await _get("/api/scene?lat=0&lon=0&fixture=true")
    assert r.status_code == 200
    assert {"buildings", "property", "near_pois", "far_pois", "address"} <= r.json().keys()


async def test_removed_endpoints_are_gone():
    assert (await _get("/api/route?from_lat=1&from_lon=1&to_lat=2&to_lon=2")).status_code == 404
    assert (await _get("/api/scene/share?lat=1&lon=1")).status_code == 404


async def test_reverse_geocode_falls_back_to_coordinates():
    from api import _reverse_geocode
    with patch("api.httpx.AsyncClient", side_effect=httpx.ConnectError("offline")):
        assert await _reverse_geocode(48.28, 17.27) == "48.2800, 17.2700"


async def test_geocode_returns_best_match():
    hit = {"lat": 48.29, "lon": 17.27, "tier": "street", "name": "Záhradná", "label": "Záhradná, Pezinok", "place_rank": 26}
    with patch("api._get_geocoder") as g:
        g.return_value.search.return_value = hit
        r = await _get("/api/geocode?q=Záhradná%20Pezinok")
    assert r.status_code == 200 and r.json() == hit


async def test_geocode_404_and_503():
    from api import GEOCODE_DOWN, GEOCODE_NOT_FOUND
    from geocode import GeocodeUnavailable
    with patch("api._get_geocoder") as g:
        g.return_value.search.return_value = None
        r = await _get("/api/geocode?q=xyzxyz")
    assert r.status_code == 404 and r.json()["detail"] == GEOCODE_NOT_FOUND
    with patch("api._get_geocoder") as g:
        g.return_value.search.side_effect = GeocodeUnavailable("down")
        r = await _get("/api/geocode?q=Pezinok")
    assert r.status_code == 503 and r.json()["detail"] == GEOCODE_DOWN


async def test_geocode_rejects_too_short_query():
    assert (await _get("/api/geocode?q=a")).status_code == 422


async def test_scene_passes_tier_and_name_and_skips_reverse_geocode():
    calls = {}

    def fake_build(lat, lon, cfg, tier, name):
        calls.update(tier=tier, name=name)
        return dict(SCENE)

    rev = AsyncMock(return_value="x")
    with patch("api.build_scene", side_effect=fake_build), patch("api._reverse_geocode", rev):
        r = await _get("/api/scene?lat=48.28&lon=17.27&tier=street&name=Z%C3%A1hradn%C3%A1")
    assert r.status_code == 200 and r.json()["address"] is None
    assert calls == {"tier": "street", "name": "Záhradná"}
    rev.assert_not_called()


async def test_scene_rejects_unknown_tier():
    assert (await _get("/api/scene?lat=48.28&lon=17.27&tier=planet")).status_code == 422


async def test_scene_reverse_false_skips_reverse_geocode_at_address_tier():
    rev = AsyncMock(return_value="x")
    with patch("api.build_scene", return_value=dict(SCENE)), patch("api._reverse_geocode", rev):
        r = await _get("/api/scene?lat=48.28&lon=17.27&reverse=false")
    assert r.status_code == 200 and r.json()["address"] is None
    rev.assert_not_called()
