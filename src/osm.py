"""Overpass API access: query builders, endpoint fallback and a JSON file cache."""
import hashlib
import json
import logging
import os
import threading
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
USER_AGENT = "hoodiemap/1.0 (neighbourhood-map)"
TIMEOUT_S = 25
CACHE_TTL_S = 30 * 24 * 3600
AREA_MARGIN_M = 20
LOCAL_RADIUS_M = 300

# category -> (Overpass tag filter, search radius in metres)
POI_QUERIES: dict[str, tuple[str, int]] = {
    "hospital":     ('["amenity"="hospital"]', 30_000),
    "supermarket":  ('["shop"="supermarket"]', 5_000),
    "school":       ('["amenity"="school"]', 5_000),
    "kindergarten": ('["amenity"="kindergarten"]', 5_000),
    "pharmacy":     ('["amenity"="pharmacy"]', 5_000),
    "bus_stop":     ('["highway"="bus_stop"]', 3_000),
    "train":        ('["railway"~"^(station|halt)$"]', 30_000),
    "park":         ('["leisure"="park"]', 3_000),
    # Local extras: only shown when they are on the map itself, so a small bbox is enough.
    "playground":   ('["leisure"="playground"]', LOCAL_RADIUS_M),
    "food":         ('["amenity"~"^(cafe|restaurant)$"]', LOCAL_RADIUS_M),
    "post":         ('["amenity"="post_office"]', LOCAL_RADIUS_M),
    "bank":         ('["amenity"="bank"]', LOCAL_RADIUS_M),
    "doctors":      ('["amenity"~"^(doctors|clinic|dentist)$"]', LOCAL_RADIUS_M),
    "city":         ('["place"="city"]', 70_000),
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
    parts.append(f'way["place"="square"]{b};relation["place"="square"]{b};')
    parts.append(f'relation["highway"="pedestrian"]{b};')
    parts.append(f'node["natural"="tree"]{b};')
    return "[out:json][timeout:25];(" + "".join(parts) + ");out geom;"


def build_poi_query(lat: float, lon: float, categories: list[str]) -> str:
    # Square bbox of the category radius instead of around: — bbox filters are index-backed,
    # large around: radii time out on busy servers. Nearest-by-distance is picked later anyway.
    parts = []
    for cat in categories:
        selector, radius = POI_QUERIES[cat]
        south, west, north, east = square_bbox(lat, lon, radius)
        parts.append(f"nwr{selector}({south:.6f},{west:.6f},{north:.6f},{east:.6f});")
    # bb: the bounding box gives both a centre and a rough size (tiny lawns tagged park).
    return "[out:json][timeout:25];(" + "".join(parts) + ");out bb tags;"


def categorize_poi(tags: dict) -> str | None:
    amenity = tags.get("amenity")
    if amenity in ("hospital", "school", "kindergarten", "pharmacy"):
        return amenity
    if amenity in ("cafe", "restaurant"):
        return "food"
    if amenity == "post_office":
        return "post"
    if amenity == "bank":
        return "bank"
    if amenity in ("doctors", "clinic", "dentist"):
        return "doctors"
    if tags.get("place") == "city":
        return "city"
    if tags.get("shop") == "supermarket":
        return "supermarket"
    if tags.get("highway") == "bus_stop":
        return "bus_stop"
    if tags.get("railway") in ("station", "halt"):
        return "train"
    if tags.get("leisure") == "park":
        return "park"
    if tags.get("leisure") == "playground":
        return "playground"
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
    tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps({"fetched_at": time.time(), "data": data}), encoding="utf-8")
    os.replace(tmp, path)


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
                try:
                    _cache_write(query, data, cache_dir)
                except OSError as exc:
                    logger.warning("Could not write Overpass cache: %s", exc)
            return data
    raise OverpassError("; ".join(errors))


def fetch_area(lat: float, lon: float, half_m: float, cache_dir: str | None) -> dict:
    south, west, north, east = square_bbox(lat, lon, half_m + AREA_MARGIN_M)
    return run_query(build_area_query(south, west, north, east), cache_dir)


def fetch_pois(lat: float, lon: float, categories: list[str], cache_dir: str | None) -> dict:
    if not categories:
        return {"elements": []}
    return run_query(build_poi_query(lat, lon, categories), cache_dir)
