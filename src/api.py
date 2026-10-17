import asyncio
import json
from pathlib import Path
from typing import Annotated, Literal

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import get_config
from geocode import GeocodeUnavailable, Geocoder
from osm import AREA_FAILED_DETAIL, USER_AGENT, OverpassError
from presentation_api import router as presentation_router
from scene_builder import build_scene

_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "pezinok-centrum.json"
GEOCODE_NOT_FOUND = "No place matches the query."
GEOCODE_DOWN = "Geocoding is temporarily unavailable."

app = FastAPI(title="HoodieMap API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(presentation_router)

# Presentations are shared by link only (demos are built from other people's listings): keep them out of search engines.
_PRIVATE_PREFIXES = ("/p/", "/novy", "/upravit/", "/api/presentations")


@app.middleware("http")
async def noindex_private_pages(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(_PRIVATE_PREFIXES):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


_geocoder = None


def _get_cfg():
    return get_config()


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
    tier: Literal["address", "street", "city"] = "address",
    name: Annotated[str | None, Query(max_length=200)] = None,
    reverse: bool = True,
):
    if fixture:
        if not _FIXTURE_PATH.exists():
            raise HTTPException(status_code=404, detail="Fixture file not found. Run scripts/capture_fixture.py first.")
        try:
            return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=500, detail="Fixture JSON is malformed.") from exc

    try:
        data = await asyncio.to_thread(build_scene, lat, lon, _get_cfg(), tier, name)
    except OverpassError as exc:
        raise HTTPException(status_code=502, detail=AREA_FAILED_DETAIL) from exc
    data["address"] = await _reverse_geocode(lat, lon) if tier == "address" and reverse else None
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
    @app.api_route("/p/{pid}", methods=["GET", "HEAD"], include_in_schema=False)
    async def presentation_page(pid: str):
        return FileResponse(_frontend_dist / "presentation.html")

    @app.api_route("/novy", methods=["GET", "HEAD"], include_in_schema=False)
    @app.api_route("/upravit/{pid}", methods=["GET", "HEAD"], include_in_schema=False)
    async def editor_page(pid: str | None = None):
        return FileResponse(_frontend_dist / "editor.html")

    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    cfg = _get_cfg()
    uvicorn.run("api:app", host=cfg.api.host, port=cfg.api.port, reload=True)
