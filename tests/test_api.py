import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def sample_scene():
    return {
        "center": {"lat": 48.28646, "lon": 17.27221},
        "bbox_m": 600,
        "roads": [{"points": [[0, 0], [100, 0]], "type": "residential"}],
        "buildings": [{"footprint": [[10, 10], [30, 10], [30, 30], [10, 30]], "height": 8.0, "type": "residential"}],
        "pois": [{"x": 50.0, "y": 80.0, "lat": 48.287, "lon": 17.273, "category": "grocery", "name": "Kaufland", "distance_m": 320}],
        "trees": [{"x": 20.0, "y": 20.0, "radius": 3.0, "height": 10.0}],
    }


@pytest.mark.asyncio
async def test_health_endpoint():
    from api import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_scene_endpoint_returns_scene_json(sample_scene):
    from api import app
    with patch("api.build_scene", return_value=sample_scene):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/scene?lat=48.28646&lon=17.27221")
    assert response.status_code == 200
    data = response.json()
    assert data["center"]["lat"] == 48.28646
    assert "roads" in data and "buildings" in data


@pytest.mark.asyncio
async def test_scene_endpoint_rejects_bad_coords():
    from api import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/scene?lat=999&lon=17.27221")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_geocode_endpoint_returns_results():
    from api import app
    from unittest.mock import AsyncMock, MagicMock
    mock_nominatim = [{"lat": "48.2865", "lon": "17.2722", "display_name": "Pezinok, Slovakia"}]
    with patch("api.httpx.AsyncClient") as mock_client_cls:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_nominatim
        mock_resp.raise_for_status = MagicMock()
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/geocode?q=Pezinok")
    assert response.status_code == 200
    assert response.json() == mock_nominatim


@pytest.mark.asyncio
async def test_share_endpoint_returns_id():
    from api import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/scene/share?lat=48.28646&lon=17.27221")
    assert response.status_code == 200
    data = response.json()
    assert {"id", "view_url", "embed_url"} <= data.keys()
    assert data["view_url"].startswith("/view/")
    assert data["embed_url"].startswith("/embed")


@pytest.mark.asyncio
async def test_share_endpoint_same_coords_same_id():
    from api import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.get("/api/scene/share?lat=48.28646&lon=17.27221")
        r2 = await client.get("/api/scene/share?lat=48.28646&lon=17.27221")
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_view_redirect_follows_to_embed():
    from api import app, _share_store
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        share = await client.get("/api/scene/share?lat=48.28646&lon=17.27221")
        scene_id = share.json()["id"]
        response = await client.get(f"/view/{scene_id}", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert "lat=" in location and "lon=" in location


@pytest.mark.asyncio
async def test_view_unknown_id_returns_404():
    from api import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/view/deadbeef")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_route_endpoint_returns_osrm_response():
    from api import app
    from unittest.mock import AsyncMock, MagicMock
    mock_osrm = {
        "routes": [{
            "geometry": {"type": "LineString", "coordinates": [[17.272, 48.286], [17.273, 48.287]]},
            "distance": 1200,
        }]
    }
    with patch("api.httpx.AsyncClient") as mock_cls:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_osrm
        mock_resp.raise_for_status = MagicMock()
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/route?from_lat=48.286&from_lon=17.272&to_lat=48.290&to_lon=17.275"
            )
    assert response.status_code == 200
    assert "routes" in response.json()


@pytest.mark.asyncio
async def test_route_endpoint_osrm_failure_returns_502():
    from api import app, _route_cache
    import httpx as real_httpx
    _route_cache.clear()
    with patch("api.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=real_httpx.RequestError("timeout"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/route?from_lat=48.286&from_lon=17.272&to_lat=48.290&to_lon=17.275"
            )
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_route_endpoint_cached_on_second_call():
    from api import app, _route_cache
    _route_cache.clear()
    mock_osrm = {"routes": [{"geometry": {"type": "LineString", "coordinates": []}, "distance": 500}]}
    call_count = 0
    with patch("api.httpx.AsyncClient") as mock_cls:
        async def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            m = MagicMock()
            m.json.return_value = mock_osrm
            m.raise_for_status = MagicMock()
            return m
        from unittest.mock import MagicMock
        mock_http = AsyncMock()
        mock_http.get = fake_get
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/api/route?from_lat=48.28600&from_lon=17.27200&to_lat=48.29000&to_lon=17.27500")
            await client.get("/api/route?from_lat=48.28600&from_lon=17.27200&to_lat=48.29000&to_lon=17.27500")
    assert call_count == 1
