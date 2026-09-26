"""Nominatim forward geocoding: the best match, its map tier, a 1 req/s throttle and a JSON cache."""
import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path

import httpx

from osm import USER_AGENT

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
TIMEOUT_S = 5
CACHE_TTL_S = 30 * 24 * 3600
MIN_INTERVAL_S = 1.0  # Nominatim usage policy: at most one request per second


class GeocodeUnavailable(RuntimeError):
    """Nominatim could not be reached or answered with an error."""


def tier_for_rank(rank: int) -> str:
    if rank >= 28:
        return "address"
    if rank >= 26:
        return "street"
    return "city"


def short_label(result: dict) -> str:
    a = result.get("address") or {}
    town = a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or ""
    name = result.get("name") or ""
    if result.get("place_rank", 0) >= 26:
        road = a.get("road") or a.get("pedestrian") or name
        parts = [f"{road} {a.get('house_number', '')}".strip(), town]
    else:
        parts = [name, town if town != name else ""]
    label = ", ".join(p for p in parts if p)
    if label and (a or name):
        return label
    return result.get("display_name", "") or label


def _street_name(result: dict) -> str:
    a = result.get("address") or {}
    return a.get("road") or a.get("pedestrian") or result.get("name") or ""


class Geocoder:
    def __init__(self, countrycodes: str, cache_dir: str | None, transport: httpx.BaseTransport | None = None,
                 clock=time.monotonic, sleep=time.sleep):
        self.countrycodes = countrycodes
        self.cache_dir = cache_dir
        self.transport = transport
        self._clock, self._sleep = clock, sleep
        self._lock = threading.Lock()
        self._last = float("-inf")

    def _cache_file(self, key: str) -> Path:
        digest = hashlib.sha256(f"{self.countrycodes}|{key}".encode()).hexdigest()[:16]
        return Path(self.cache_dir) / "geocode" / f"{digest}.json"

    def _cache_read(self, key: str) -> dict | None:
        if not self.cache_dir:
            return None
        try:
            payload = json.loads(self._cache_file(key).read_text(encoding="utf-8"))
            if time.time() - payload["fetched_at"] > CACHE_TTL_S:
                return None
            return payload["result"]
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _cache_write(self, key: str, result: dict) -> None:
        if not self.cache_dir:
            return
        path = self._cache_file(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps({"fetched_at": time.time(), "result": result}), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            logger.warning("Could not write geocode cache: %s", exc)

    def _request(self, q: str) -> list:
        params = {"q": q, "format": "jsonv2", "limit": 1, "addressdetails": 1,
                  "countrycodes": self.countrycodes, "accept-language": "sk"}
        with self._lock:
            wait = MIN_INTERVAL_S - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
            try:
                with httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, transport=self.transport) as c:
                    resp = c.get(NOMINATIM_URL, params=params)
                    resp.raise_for_status()
                    return resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise GeocodeUnavailable(str(exc)) from exc
            finally:
                self._last = self._clock()

    def search(self, q: str) -> dict | None:
        key = " ".join(q.lower().split())
        cached = self._cache_read(key)
        if cached is not None:
            return cached
        hits = self._request(q)
        if not hits:
            return None
        hit = hits[0]
        try:
            rank = int(hit.get("place_rank", 30))
            tier = tier_for_rank(rank)
            result = {
                "lat": float(hit["lat"]), "lon": float(hit["lon"]), "tier": tier,
                "name": _street_name(hit) if tier != "city" else (hit.get("name") or ""),
                "label": short_label(hit), "place_rank": rank,
            }
        except (KeyError, ValueError, TypeError) as exc:
            raise GeocodeUnavailable(f"Malformed Nominatim result: {exc}") from exc
        self._cache_write(key, result)
        return result
