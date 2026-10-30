"""/api/score: HoodieMap skóre (Pešo, Zeleň, Rodina, Pokoj) for one point, and the method behind it."""
import asyncio
import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

import score
import score_method
from config import get_config
from geo import haversine_m
from osm import AREA_FAILED_DETAIL, OverpassError, endpoints_for, run_query

FIXTURES = Path(__file__).parent.parent / "fixtures"
router = APIRouter(prefix="/api/score")


def _nearest_fixture(lat: float, lon: float) -> dict:
    """Offline development: the fixture closest to the point (fixtures/score-*.json, scripts/osm_fixture.py)."""
    best = None
    for path in sorted(FIXTURES.glob("score-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        c = data.get("center") or {}
        d = haversine_m(lat, lon, c.get("lat", 0), c.get("lon", 0))
        if best is None or d < best[0]:
            best = (d, data)
    if best is None:
        raise HTTPException(status_code=404, detail="No score fixtures. Run scripts/osm_fixture.py first.")
    return best[1]


def _fetch(lat: float, lon: float) -> dict:
    cfg = get_config()
    return run_query(score.build_score_query(lat, lon), cfg.cache.dir if cfg.cache.enabled else None,
                     timeout_s=70, endpoints=endpoints_for(lat, lon, cfg.overpass))


@router.get("")
async def score_point(lat: Annotated[float, Query(ge=-90, le=90)], lon: Annotated[float, Query(ge=-180, le=180)],
                      fixture: bool = False):
    if fixture:
        osm = _nearest_fixture(lat, lon)
        lat, lon = osm["center"]["lat"], osm["center"]["lon"]
    else:
        try:
            osm = await asyncio.to_thread(_fetch, lat, lon)
        except OverpassError as exc:
            raise HTTPException(status_code=502, detail=AREA_FAILED_DETAIL) from exc
    return await asyncio.to_thread(score.compute, osm, lat, lon)


@router.get("/method")
async def method():
    return score_method.method()
