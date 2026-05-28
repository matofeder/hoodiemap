import asyncio
import hashlib
import json
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import load_config
from scene_builder import build_scene

_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "pezinok-centrum.json"

app = FastAPI(title="genmap API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_cfg = None
_share_store: dict[str, tuple[float, float]] = {}
_route_cache: dict[str, dict] = {}


def _get_cfg():
    global _cfg
    if _cfg is None:
        config_path = Path(__file__).parent.parent / "config.yaml"
        _cfg = load_config(str(config_path))
    return _cfg


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/scene")
async def scene(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    fixture: bool = False,
):
    if fixture:
        if not _FIXTURE_PATH.exists():
            raise HTTPException(
                status_code=404,
                detail="Fixture file not found. Run scripts/capture_fixture.py first.",
            )
        try:
            return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=500, detail="Fixture JSON is malformed.") from exc
    cfg = _get_cfg()
    try:
        data = await asyncio.to_thread(build_scene, lat, lon, cfg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "jsonv2"},
                headers={"User-Agent": "genmap/1.0 (neighbourhood-map)"},
            )
            resp.raise_for_status()
            rg = resp.json()
            addr = rg.get("address", {})
            road = addr.get("road") or addr.get("pedestrian") or addr.get("suburb") or ""
            city = addr.get("city") or addr.get("town") or addr.get("village") or ""
            data["address"] = ", ".join(p for p in [road, city] if p) or f"{lat:.4f}, {lon:.4f}"
    except Exception:
        data["address"] = f"{lat:.4f}, {lon:.4f}"

    return data


@app.get("/api/geocode")
async def geocode(q: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": q, "format": "json", "limit": 5, "addressdetails": 0}
    headers = {"User-Agent": "genmap/1.0 (neighbourhood-map)"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params, headers=headers)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail="Geocode upstream error") from exc
    return resp.json()


@app.get("/api/scene/share")
async def scene_share(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
):
    scene_id = hashlib.sha256(f"{lat:.6f},{lon:.6f}".encode()).hexdigest()[:8]
    _share_store[scene_id] = (lat, lon)
    return {
        "id": scene_id,
        "view_url": f"/view/{scene_id}",
        "embed_url": f"/embed?lat={lat}&lon={lon}",
    }


@app.get("/api/route")
async def route_hint(
    from_lat: Annotated[float, Query(ge=-90, le=90)],
    from_lon: Annotated[float, Query(ge=-180, le=180)],
    to_lat: Annotated[float, Query(ge=-90, le=90)],
    to_lon: Annotated[float, Query(ge=-180, le=180)],
):
    cache_key = f"{from_lat:.5f},{from_lon:.5f},{to_lat:.5f},{to_lon:.5f}"
    if cache_key in _route_cache:
        return _route_cache[cache_key]
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{from_lon:.6f},{from_lat:.6f};{to_lon:.6f},{to_lat:.6f}"
        f"?overview=full&geometries=geojson"
    )
    headers = {"User-Agent": "genmap/1.0 (neighbourhood-map)"}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise HTTPException(status_code=502, detail="Routing upstream error") from exc
    data = resp.json()
    _route_cache[cache_key] = data
    return data


@app.get("/view/{scene_id}")
async def view_scene(scene_id: str):
    coords = _share_store.get(scene_id)
    if coords is None:
        raise HTTPException(status_code=404, detail="Scene not found")
    lat, lon = coords
    return RedirectResponse(f"/embed?lat={lat}&lon={lon}", status_code=302)


# Serve frontend build if it exists (production mode)
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    cfg = _get_cfg()
    uvicorn.run("api:app", host=cfg.api.host, port=cfg.api.port, reload=True)
