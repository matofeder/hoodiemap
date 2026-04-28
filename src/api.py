import asyncio
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import load_config
from scene_builder import build_scene

app = FastAPI(title="genmap API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_cfg = None


def _get_cfg():
    global _cfg
    if _cfg is None:
        _cfg = load_config("config.yaml")
    return _cfg


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/scene")
async def scene(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
):
    cfg = _get_cfg()
    try:
        data = await asyncio.to_thread(build_scene, lat, lon, cfg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return data


@app.get("/api/geocode")
async def geocode(q: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": q, "format": "json", "limit": 5, "addressdetails": 0}
    headers = {"User-Agent": "genmap/1.0 (neighbourhood-map)"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
    return resp.json()


# Serve frontend build if it exists (production mode)
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    cfg = _get_cfg()
    uvicorn.run("api:app", host=cfg.api.host, port=cfg.api.port, reload=True)
