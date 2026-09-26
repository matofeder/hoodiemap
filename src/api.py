import asyncio
import json
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import load_config
from geocode import GeocodeUnavailable, Geocoder
from osm import USER_AGENT, OverpassError
from scene_builder import build_scene

_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "pezinok-centrum.json"
AREA_FAILED_DETAIL = "Could not load map data from OpenStreetMap. Try again in a minute."
GEOCODE_NOT_FOUND = "No place matches the query."
GEOCODE_DOWN = "Geocoding is temporarily unavailable."

app = FastAPI(title="HoodieMap API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_cfg = None
_geocoder = None


def _get_cfg():
    global _cfg
    if _cfg is None:
        _cfg = load_config(Path(__file__).parent.parent / "config.yaml")
    return _cfg


def _get_geocoder() -> Geocoder:
    global _geocoder
    if _geocoder is None:
        cfg = _get_cfg()
        _geocoder = Geocoder(cfg.geocode.countrycodes, cfg.cache.dir if cfg.cache.enabled else None)
    return _geocoder


async def _reverse_geocode(lat: float, lon: float) -> str:
    fallback = f"{lat:.4f}, {lon:.4f}"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "jsonv2"},
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            addr = resp.json().get("address", {})
    except Exception:
        return fallback
    road = addr.get("road") or addr.get("pedestrian") or addr.get("suburb") or ""
    city = addr.get("city") or addr.get("town") or addr.get("village") or ""
    return ", ".join(p for p in [road, city] if p) or fallback


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
            raise HTTPException(status_code=404, detail="Fixture file not found. Run scripts/capture_fixture.py first.")
        try:
            return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=500, detail="Fixture JSON is malformed.") from exc

    try:
        data = await asyncio.to_thread(build_scene, lat, lon, _get_cfg())
    except OverpassError as exc:
        raise HTTPException(status_code=502, detail=AREA_FAILED_DETAIL) from exc
    data["address"] = await _reverse_geocode(lat, lon)
    return data


@app.get("/api/geocode")
async def geocode(q: Annotated[str, Query(min_length=2, max_length=200)]):
    try:
        result = await asyncio.to_thread(_get_geocoder().search, q)
    except GeocodeUnavailable as exc:
        raise HTTPException(status_code=503, detail=GEOCODE_DOWN) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=GEOCODE_NOT_FOUND)
    return result


# Serve frontend build if it exists (production mode)
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    cfg = _get_cfg()
    uvicorn.run("api:app", host=cfg.api.host, port=cfg.api.port, reload=True)
