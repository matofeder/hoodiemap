import pytest
from unittest.mock import patch
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
