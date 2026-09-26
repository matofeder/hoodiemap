"""Overpass API access: query builders, endpoint fallback and a JSON file cache."""
import hashlib
import json
import logging
import time
from pathlib import Path

import httpx

from geo import square_bbox

logger = logging.getLogger(__name__)

ENDPOINTS: list[str] = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = "genmap/1.0 (neighbourhood-map)"
TIMEOUT_S = 25
CACHE_TTL_S = 30 * 24 * 3600
AREA_MARGIN_M = 20

# category -> (Overpass tag filter, search radius in metres)
POI_QUERIES: dict[str, tuple[str, int]] = {
    "hospital":     ('["amenity"="hospital"]', 30_000),
    "supermarket":  ('["shop"="supermarket"]', 5_000),
    "school":       ('["amenity"="school"]', 5_000),
    "kindergarten": ('["amenity"="kindergarten"]', 5_000),
    "pharmacy":     ('["amenity"="pharmacy"]', 5_000),
    "bus_stop":     ('["highway"="bus_stop"]', 3_000),
    "train":        ('["railway"~"^(station|halt)$"]', 30_000),
    "park":         ('["leisure"~"^(park|playground)$"]', 3_000),
}

_AREA_FILTERS = [
    '["building"]',
    '["leisure"~"^(park|garden|playground)$"]',
    '["landuse"~"^(grass|meadow|recreation_ground|village_green|forest)$"]',
    '["natural"~"^(water|wood)$"]',
    '["waterway"="riverbank"]',
]


class OverpassError(RuntimeError):
    """All Overpass endpoints failed for a query."""


def build_area_query(south: float, west: float, north: float, east: float) -> str:
    b = f"({south:.6f},{west:.6f},{north:.6f},{east:.6f})"
    parts = [f"way{f}{b};relation{f}{b};" for f in _AREA_FILTERS]
    parts.append(f'way["highway"]{b};')
    parts.append(f'node["natural"="tree"]{b};')
    return "[out:json][timeout:25];(" + "".join(parts) + ");out geom;"


def build_poi_query(lat: float, lon: float, categories: list[str]) -> str:
    parts = []
    for cat in categories:
        selector, radius = POI_QUERIES[cat]
        parts.append(f"nwr{selector}(around:{radius},{lat:.6f},{lon:.6f});")
    return "[out:json][timeout:25];(" + "".join(parts) + ");out center tags;"


def categorize_poi(tags: dict) -> str | None:
    amenity = tags.get("amenity")
    if amenity in ("hospital", "school", "kindergarten", "pharmacy"):
        return amenity
    if tags.get("shop") == "supermarket":
        return "supermarket"
    if tags.get("highway") == "bus_stop":
        return "bus_stop"
    if tags.get("railway") in ("station", "halt"):
        return "train"
    if tags.get("leisure") in ("park", "playground"):
        return "park"
    return None


def _cache_file(query: str, cache_dir: str) -> Path:
    return Path(cache_dir) / "osm" / f"{hashlib.sha256(query.encode()).hexdigest()[:16]}.json"


def _cache_read(query: str, cache_dir: str) -> dict | None:
    try:
        payload = json.loads(_cache_file(query, cache_dir).read_text(encoding="utf-8"))
        if time.time() - payload["fetched_at"] > CACHE_TTL_S:
            return None
        return payload["data"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _cache_write(query: str, data: dict, cache_dir: str) -> None:
    path = _cache_file(query, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_at": time.time(), "data": data}), encoding="utf-8")


def run_query(query: str, cache_dir: str | None, transport: httpx.BaseTransport | None = None) -> dict:
    if cache_dir:
        cached = _cache_read(query, cache_dir)
        if cached is not None:
            return cached
    errors = []
    with httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, transport=transport) as client:
        for url in ENDPOINTS:
            try:
                resp = client.post(url, data={"data": query})
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("Overpass %s failed: %s", url, exc)
                errors.append(f"{url}: {exc}")
                continue
            if "runtime error" in str(data.get("remark", "")):
                logger.warning("Overpass %s runtime error: %s", url, data["remark"])
                errors.append(f"{url}: {data['remark']}")
                continue
            if cache_dir:
                _cache_write(query, data, cache_dir)
            return data
    raise OverpassError("; ".join(errors))


def fetch_area(lat: float, lon: float, half_m: float, cache_dir: str | None) -> dict:
    south, west, north, east = square_bbox(lat, lon, half_m + AREA_MARGIN_M)
    return run_query(build_area_query(south, west, north, east), cache_dir)


def fetch_pois(lat: float, lon: float, categories: list[str], cache_dir: str | None) -> dict:
    if not categories:
        return {"elements": []}
    return run_query(build_poi_query(lat, lon, categories), cache_dir)
