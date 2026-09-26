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
CITY_TIMEOUT_S = 70
CACHE_TTL_S = 30 * 24 * 3600
AREA_MARGIN_M = 20
LOCAL_RADIUS_M = 300
STREET_SEARCH_M = 1500

LANDMARK_SELECTORS = (
    '["amenity"="townhall"]',
    '["place"="square"]',
    '["highway"="pedestrian"]["area"="yes"]["name"]',
    '["historic"~"^(castle|manor)$"]',
    '["building"~"^(church|cathedral)$"]',
    '["amenity"="place_of_worship"]',
    '["tourism"~"^(museum|attraction)$"]',
)

# category -> (Overpass tag filter(s), search radius in metres or None = map square)
POI_QUERIES: dict[str, tuple[str | tuple[str, ...], int | None]] = {
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
    "bus_station":  ('["amenity"="bus_station"]', 30_000),
    "mall":         ('["shop"="mall"]', 15_000),
    "landmark":     (LANDMARK_SELECTORS, None),
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


_PATH_KINDS = "footway|path|steps|track|cycleway"


def build_area_query(south: float, west: float, north: float, east: float, light: bool = False) -> str:
    b = f"({south:.6f},{west:.6f},{north:.6f},{east:.6f})"
    parts = [f"way{f}{b};relation{f}{b};" for f in _AREA_FILTERS]
    if light:  # city tier: no footways, no single trees — far less data at 450 m
        parts.append(f'way["highway"]["highway"!~"^({_PATH_KINDS})$"]{b};')
    else:
        parts.append(f'way["highway"]{b};')
        parts.append(f'node["natural"="tree"]{b};')
    parts.append(f'way["place"="square"]{b};relation["place"="square"]{b};')
    parts.append(f'relation["highway"="pedestrian"]{b};')
    timeout = 60 if light else 25
    return f"[out:json][timeout:{timeout}];(" + "".join(parts) + ");out geom;"


def build_poi_query(lat: float, lon: float, categories: list[str], square_m: float = 0.0) -> str:
    # Square bbox of the category radius instead of around: — bbox filters are index-backed,
    # large around: radii time out on busy servers. Nearest-by-distance is picked later anyway.
    parts = []
    for cat in categories:
        selectors, radius = POI_QUERIES[cat]
        south, west, north, east = square_bbox(lat, lon, square_m if radius is None else radius)
        for sel in (selectors,) if isinstance(selectors, str) else selectors:
            parts.append(f"nwr{sel}({south:.6f},{west:.6f},{north:.6f},{east:.6f});")
    # bb: the bounding box gives both a centre and a rough size (tiny lawns tagged park).
    return "[out:json][timeout:25];(" + "".join(parts) + ");out bb tags;"


def landmark_kind(tags: dict) -> tuple[int, str] | None:
    if tags.get("amenity") == "townhall":
        return (1, "Radnica")
    if tags.get("place") == "square" or (
            tags.get("highway") == "pedestrian" and tags.get("area") == "yes" and tags.get("name")):
        return (2, "Námestie")
    if tags.get("historic") == "castle":
        castle_type = tags.get("castle_type")
        if castle_type in ("palace", "stately"):
            return (3, "Palác")
        if castle_type == "manor":
            return (3, "Kaštieľ")
        return (3, "Hrad")
    if tags.get("historic") == "manor":
        return (3, "Kaštieľ")
    if tags.get("building") in ("church", "cathedral") or tags.get("amenity") == "place_of_worship":
        return (4, "Kostol")
    if tags.get("tourism") == "museum":
        return (5, "Múzeum")
    if tags.get("tourism") == "attraction":
        return (5, "Pamiatka")
    return None


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
    if amenity == "bus_station":
        return "bus_station"
    if tags.get("shop") == "mall":
        return "mall"
    if landmark_kind(tags):
        return "landmark"
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


def run_query(query: str, cache_dir: str | None, transport: httpx.BaseTransport | None = None,
              timeout_s: float = TIMEOUT_S, stats: list | None = None) -> dict:
    if cache_dir:
        cached = _cache_read(query, cache_dir)
        if cached is not None:
            if stats is not None:
                stats.append(True)
            return cached
    errors = []
    with httpx.Client(timeout=timeout_s, headers={"User-Agent": USER_AGENT}, transport=transport) as client:
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
            if stats is not None:
                stats.append(False)
            return data
    raise OverpassError("; ".join(errors))


def build_street_query(name: str, lat: float, lon: float) -> str:
    safe = name.replace("\\", "\\\\").replace('"', '\\"')
    return (f'[out:json][timeout:25];way["highway"]["name"="{safe}"]'
            f"(around:{STREET_SEARCH_M},{lat:.6f},{lon:.6f});out geom;")


def fetch_street(name: str, lat: float, lon: float, cache_dir: str | None, stats: list | None = None) -> dict:
    return run_query(build_street_query(name, lat, lon), cache_dir, stats=stats)


def fetch_area(lat: float, lon: float, half_m: float, cache_dir: str | None,
               light: bool = False, stats: list | None = None) -> dict:
    south, west, north, east = square_bbox(lat, lon, half_m + AREA_MARGIN_M)
    return run_query(build_area_query(south, west, north, east, light), cache_dir,
                      timeout_s=CITY_TIMEOUT_S if light else TIMEOUT_S, stats=stats)


def fetch_pois(lat: float, lon: float, categories: list[str], cache_dir: str | None,
               square_m: float = 0.0, stats: list | None = None) -> dict:
    if not categories:
        return {"elements": []}
    return run_query(build_poi_query(lat, lon, categories, square_m), cache_dir, stats=stats)
