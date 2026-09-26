# Location Search with Address / Street / City Tiers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One search box: the best Nominatim match decides the tier (address / street / city), the backend frames the map and picks POIs for that tier, the frontend renders it with tier-appropriate detail and shows the load time.

**Architecture:** Backend gets a `geocode.py` (Nominatim, tier from `place_rank`, throttle, cache) and a `street.py` (join a named street, frame the map); `build_scene` takes `tier`/`name`, fetches a lighter area at the city tier and reports `timing_ms`/`cached`. Frontend gets URL view parsing, a `detailFor(tier)` switchboard, merged building meshes (for thousands of buildings), a street highlight layer and a search form that swaps stages.

**Tech Stack:** Python 3.14, FastAPI, httpx, shapely, pytest · Three.js, Vite, vitest (node environment).

**Spec:** `docs/superpowers/specs/2026-09-26-location-search-tiers-design.md`

## Global Constraints

- Tier from Nominatim `place_rank`: ≥ 28 `address`, 26–27 `street`, ≤ 25 `city`.
- Radii (config `radii`): `display_meters: 140` (address), `street_min: 160`, `street_max: 300`, `city_meters: 450`.
- Street radius: `clamp(L / 2 + 60, street_min, street_max)`; if `L / 2 + 60 > street_max` centre on the geocoded point with `street_max`.
- Street ways: `way["highway"]["name"=…](around:1500, …)`, joined when within 30 m (transitively) of the way nearest the geocoded point.
- Geocode: `countrycodes` from config (default `"sk,cz"`), `limit=1`, `accept-language=sk`, timeout 5 s, ≤ 1 request/s process-wide, cache `.cache/geocode/` 30 days; misses are not cached.
- City tier: area query without footway/path/steps/track/cycleway ways and without tree nodes; Overpass `[timeout:60]`, HTTP timeout 70 s (25 s / 25 s elsewhere).
- No autocomplete, no result list — the first result loads.
- UI copy (Slovak, exact): placeholder `Zadajte mesto, ulicu alebo adresu`; not found `Nenašli sme „{q}“. Skúste pridať mesto alebo PSČ.`; geocoder down `Vyhľadávanie je dočasne nedostupné, skúste o chvíľu.`; city hint `Mestská úroveň je náročnejšia – skúste konkrétnu ulicu.`; timing `Načítané za {s} s · nové dáta` / `Načítané za {s} s · z cache`; tier names `adresa` / `ulica` / `mesto`.
- Run backend tests with `.venv/bin/python -m pytest` from the repo root, frontend tests with `npm test` in `frontend/`.
- Commit messages end with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01Ks8oBdDjJanB3ngMLhZ38E
  ```

## Review Focus

- A street name containing `"` or `\` (or odd OSM names) must not break the Overpass query → escaped in `build_street_query` (Task 3 test).
- Two searches in quick succession must never show the older scene → `createRequestGate` + `AbortController` (Task 7 test on the gate, Task 10 manual step 5).
- A street-tier hit with no matching highway ways (named square, typo in OSM) must still render a 160 m map around the point → `street_lines` on empty / non-way input (Task 3 test).
- A Nominatim result missing `address` or `name` must still produce a usable label → `short_label` fallbacks (Task 2 test).
- Repeated searches must not leak WebGL contexts or DOM nodes → `stage.dispose()` removes canvas, overlay, tooltip and calls `forceContextLoss()` (Task 8 code + Task 10 manual check of 10 searches).

## File Structure

| File | Responsibility |
|---|---|
| `src/config.py`, `config.yaml` | new radii, `geocode.countrycodes`, new POI flags |
| `src/geocode.py` (new) | Nominatim search, tier, label, throttle, cache |
| `src/street.py` (new) | join street ways, frame the street map |
| `src/osm.py` | street query, light city area query, landmark/bus_station/mall categories, timeout + cache stats in `run_query` |
| `src/scene_builder.py` | tier categories, street distances, landmarks, `focus`, `tier`, timing |
| `src/api.py` | `/api/geocode` (one result / 404 / 503), `/api/scene` `tier` + `name` |
| `frontend/src/url.js` | view ↔ URL, scene URL |
| `frontend/src/map/detail.js` (new) | per-tier detail switches |
| `frontend/src/format.js` | load-time text, tier names |
| `frontend/src/requestGate.js` (new) | "latest request wins" helper |
| `frontend/src/map/buildings.js`, `map/hover.js` | merged meshes + index attribute, glow overlay |
| `frontend/src/map/focus.js` (new) | street highlight + tag anchor |
| `frontend/src/map/stage.js`, `ground.js`, `trees.js`, `cars.js`, `people.js`, `placement.js`, `overlay/labels.js`, `overlay/tooltip.js` | tier detail wiring, optional tag, full dispose |
| `frontend/index.html`, `style.css`, `main.js` | search form, messages, timing line, stage swapping |
| `frontend/src/palette.js`, `icons.js`, `overlay/describe.js` | landmark / bus_station / mall categories |

---

### Task 1: Config — tier radii, geocode settings, new POI flags

**Files:**
- Modify: `src/config.py`, `config.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `cfg.radii.street_min: float = 160`, `cfg.radii.street_max: float = 300`, `cfg.radii.city_meters: float = 450`, `cfg.geocode.countrycodes: str = "sk,cz"`, POI flags `bus_station`, `mall`, `landmark` (default `True`, appended after `city` in `PoiShowConfig`).

- [ ] **Step 1: Write the failing tests** — replace the `ALL` list and add two tests in `tests/test_config.py`:

```python
ALL = ["hospital", "supermarket", "school", "kindergarten", "pharmacy", "bus_stop", "train", "park",
       "playground", "food", "post", "bank", "doctors", "city", "bus_station", "mall", "landmark"]


def test_tier_radii_and_geocode_defaults():
    from config import Config, LocationConfig
    cfg = Config(location=LocationConfig(lat=48.0, lon=17.0))
    assert (cfg.radii.display_meters, cfg.radii.street_min, cfg.radii.street_max, cfg.radii.city_meters) == (140, 160, 300, 450)
    assert cfg.geocode.countrycodes == "sk,cz"


def test_repo_config_has_tier_settings():
    cfg = load_config(Path(__file__).parent.parent / "config.yaml")
    assert cfg.radii.city_meters == 450 and cfg.radii.street_max == 300
    assert cfg.geocode.countrycodes == "sk,cz"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL (`street_min` / `geocode` attribute missing, `ALL` mismatch).

- [ ] **Step 3: Implement** — in `src/config.py`:

```python
class RadiiConfig(BaseModel):
    display_meters: float = 140.0  # address tier
    street_min: float = 160.0
    street_max: float = 300.0
    city_meters: float = 450.0
```

Append to `PoiShowConfig` after `city: bool = True`:

```python
    bus_station: bool = True
    mall: bool = True
    landmark: bool = True
```

Add the geocode section and wire it into `Config`:

```python
class GeocodeConfig(BaseModel):
    countrycodes: str = "sk,cz"


class Config(BaseModel):
    location: LocationConfig
    radii: RadiiConfig = Field(default_factory=RadiiConfig)
    poi: PoiConfig = Field(default_factory=PoiConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    geocode: GeocodeConfig = Field(default_factory=GeocodeConfig)
```

In `config.yaml` replace the `radii` block and add flags + geocode:

```yaml
radii:
  display_meters: 140      # address tier: half-size of the square around the property
  street_min: 160          # street tier: clamp(street length / 2 + 60 m, min, max)
  street_max: 300
  city_meters: 450         # city tier: half-size around the town centre
```

Under `poi.show`, after `city: true`:

```yaml
    bus_station: true    # city tier
    mall: true           # city tier (shop=mall)
    landmark: true       # city tier: town hall, square, castle, church, museum (with Wikipedia/Wikidata)
```

At the end of the file:

```yaml
geocode:
  countrycodes: "sk,cz"    # Nominatim search is limited to these countries
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_config.py -v` → PASS. Then `.venv/bin/python -m pytest -q` → all pass (new flags default on; nothing consumes them yet).

- [ ] **Step 5: Commit**

```bash
git add src/config.py config.yaml tests/test_config.py
git commit -m "feat(config): tier radii, geocode countrycodes, city-tier POI flags" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ks8oBdDjJanB3ngMLhZ38E"
```

---

### Task 2: Geocoder — best match, tier, label, throttle, cache, `/api/geocode`

**Files:**
- Create: `src/geocode.py`, `tests/test_geocode.py`
- Modify: `src/api.py` (replace the `/api/geocode` endpoint), `tests/test_api.py`

**Interfaces:**
- Consumes: `cfg.geocode.countrycodes`, `cfg.cache` (Task 1); `osm.USER_AGENT`.
- Produces:
  - `geocode.tier_for_rank(rank: int) -> str`
  - `geocode.short_label(result: dict) -> str`
  - `class geocode.GeocodeUnavailable(RuntimeError)`
  - `class geocode.Geocoder(countrycodes: str, cache_dir: str | None, transport=None, clock=time.monotonic, sleep=time.sleep)` with `.search(q: str) -> dict | None` returning `{"lat": float, "lon": float, "tier": str, "name": str, "label": str, "place_rank": int}`
  - `GET /api/geocode?q=` → that dict, 404 `{"detail": GEOCODE_NOT_FOUND}`, 503 `{"detail": GEOCODE_DOWN}`

- [ ] **Step 1: Write the failing tests** — `tests/test_geocode.py`:

```python
import httpx
import pytest

from geocode import Geocoder, GeocodeUnavailable, short_label, tier_for_rank

HIT = {
    "lat": "48.2895813", "lon": "17.2696", "place_rank": 26, "name": "Záhradná",
    "display_name": "Záhradná, Cajla, Pezinok, okres Pezinok, Slovensko",
    "address": {"road": "Záhradná", "town": "Pezinok"},
}


def _transport(bodies, calls):
    def handler(request):
        calls.append(request)
        body = bodies[len(calls) - 1]
        if isinstance(body, Exception):
            raise body
        return httpx.Response(200, json=body)
    return httpx.MockTransport(handler)


class Clock:
    def __init__(self):
        self.t, self.slept = 100.0, []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 3))
        self.t += s


@pytest.mark.parametrize("rank,tier", [(30, "address"), (28, "address"), (27, "street"), (26, "street"),
                                       (25, "city"), (18, "city"), (16, "city")])
def test_tier_for_rank(rank, tier):
    assert tier_for_rank(rank) == tier


def test_short_labels():
    assert short_label(HIT) == "Záhradná, Pezinok"
    house = {**HIT, "place_rank": 30, "address": {"road": "Záhradná", "house_number": "12", "town": "Pezinok"}}
    assert short_label(house) == "Záhradná 12, Pezinok"
    borough = {"place_rank": 18, "name": "Staré Mesto", "address": {"city": "Bratislava"}}
    assert short_label(borough) == "Staré Mesto, Bratislava"
    town = {"place_rank": 16, "name": "Pezinok", "address": {"town": "Pezinok"}}
    assert short_label(town) == "Pezinok"


def test_short_label_survives_missing_fields():
    assert short_label({"place_rank": 26, "display_name": "Niečo, Niekde"}) == "Niečo, Niekde"
    assert short_label({"place_rank": 16, "name": "Modra"}) == "Modra"
    assert short_label({}) == ""


def test_search_returns_best_match_with_tier_and_sends_params(tmp_path):
    calls = []
    g = Geocoder("sk,cz", str(tmp_path), transport=_transport([[HIT]], calls))
    r = g.search("Záhradná Pezinok")
    assert r == {"lat": 48.2895813, "lon": 17.2696, "tier": "street", "name": "Záhradná",
                 "label": "Záhradná, Pezinok", "place_rank": 26}
    params = calls[0].url.params
    assert params["countrycodes"] == "sk,cz" and params["limit"] == "1" and params["format"] == "jsonv2"
    assert params["accept-language"] == "sk" and params["addressdetails"] == "1"


def test_street_name_prefers_road_over_display_name(tmp_path):
    house = {**HIT, "place_rank": 30, "name": "", "address": {"road": "Záhradná", "house_number": "12", "town": "Pezinok"}}
    g = Geocoder("sk", str(tmp_path), transport=_transport([[house]], []))
    assert g.search("Záhradná 12 Pezinok")["name"] == "Záhradná"


def test_search_cache_hit_skips_network_and_normalizes_query(tmp_path):
    calls = []
    g = Geocoder("sk", str(tmp_path), transport=_transport([[HIT]], calls))
    first = g.search("Záhradná  Pezinok")
    assert g.search("  záhradná pezinok ") == first
    assert len(calls) == 1


def test_not_found_returns_none_and_is_not_cached(tmp_path):
    calls, clock = [], Clock()
    g = Geocoder("sk", str(tmp_path), transport=_transport([[], [HIT]], calls), clock=clock.now, sleep=clock.sleep)
    assert g.search("xyz") is None
    assert g.search("xyz") is not None
    assert len(calls) == 2


def test_throttle_waits_one_second_between_requests(tmp_path):
    clock = Clock()
    g = Geocoder("sk", None, transport=_transport([[HIT], [HIT]], []), clock=clock.now, sleep=clock.sleep)
    g.search("a")
    clock.t += 0.25
    g.search("b")
    assert clock.slept == [0.75]


def test_network_error_raises_unavailable(tmp_path):
    g = Geocoder("sk", None, transport=_transport([httpx.ConnectError("offline")], []))
    with pytest.raises(GeocodeUnavailable):
        g.search("Pezinok")
```

Add to `tests/test_api.py`:

```python
async def test_geocode_returns_best_match():
    hit = {"lat": 48.29, "lon": 17.27, "tier": "street", "name": "Záhradná", "label": "Záhradná, Pezinok", "place_rank": 26}
    with patch("api._get_geocoder") as g:
        g.return_value.search.return_value = hit
        r = await _get("/api/geocode?q=Záhradná%20Pezinok")
    assert r.status_code == 200 and r.json() == hit


async def test_geocode_404_and_503():
    from api import GEOCODE_DOWN, GEOCODE_NOT_FOUND
    from geocode import GeocodeUnavailable
    with patch("api._get_geocoder") as g:
        g.return_value.search.return_value = None
        r = await _get("/api/geocode?q=xyzxyz")
    assert r.status_code == 404 and r.json()["detail"] == GEOCODE_NOT_FOUND
    with patch("api._get_geocoder") as g:
        g.return_value.search.side_effect = GeocodeUnavailable("down")
        r = await _get("/api/geocode?q=Pezinok")
    assert r.status_code == 503 and r.json()["detail"] == GEOCODE_DOWN


async def test_geocode_rejects_too_short_query():
    assert (await _get("/api/geocode?q=a")).status_code == 422
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_geocode.py tests/test_api.py -v`
Expected: FAIL (`No module named 'geocode'`, `_get_geocoder` missing).

- [ ] **Step 3: Implement** — `src/geocode.py`:

```python
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
        rank = int(hit.get("place_rank", 30))
        tier = tier_for_rank(rank)
        result = {
            "lat": float(hit["lat"]), "lon": float(hit["lon"]), "tier": tier,
            "name": _street_name(hit) if tier != "city" else (hit.get("name") or ""),
            "label": short_label(hit), "place_rank": rank,
        }
        self._cache_write(key, result)
        return result
```

In `src/api.py`: add imports and constants, replace the old `geocode` endpoint:

```python
from geocode import GeocodeUnavailable, Geocoder

GEOCODE_NOT_FOUND = "No place matches the query."
GEOCODE_DOWN = "Geocoding is temporarily unavailable."

_geocoder = None


def _get_geocoder() -> Geocoder:
    global _geocoder
    if _geocoder is None:
        cfg = _get_cfg()
        _geocoder = Geocoder(cfg.geocode.countrycodes, cfg.cache.dir if cfg.cache.enabled else None)
    return _geocoder


@app.get("/api/geocode")
async def geocode(q: Annotated[str, Query(min_length=2, max_length=200)]):
    try:
        result = await asyncio.to_thread(_get_geocoder().search, q)
    except GeocodeUnavailable as exc:
        raise HTTPException(status_code=503, detail=GEOCODE_DOWN) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=GEOCODE_NOT_FOUND)
    return result
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_geocode.py tests/test_api.py -v` → PASS; then `.venv/bin/python -m pytest -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add src/geocode.py src/api.py tests/test_geocode.py tests/test_api.py
git commit -m "feat(api): geocode best match with tier, label, throttle and cache" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ks8oBdDjJanB3ngMLhZ38E"
```

---

### Task 3: Street tier geometry — query, joining ways, framing

**Files:**
- Create: `src/street.py`, `tests/test_street.py`
- Modify: `src/osm.py` (add `STREET_SEARCH_M`, `build_street_query`, `fetch_street`; extend `run_query` with `timeout_s` and `stats`), `tests/test_osm.py`

**Interfaces:**
- Produces:
  - `osm.run_query(query: str, cache_dir: str | None, transport=None, timeout_s: float = TIMEOUT_S, stats: list | None = None) -> dict` — appends `True` to `stats` on a cache hit, `False` on a network fetch.
  - `osm.build_street_query(name: str, lat: float, lon: float) -> str`
  - `osm.fetch_street(name: str, lat: float, lon: float, cache_dir: str | None, stats: list | None = None) -> dict`
  - `street.street_lines(raw: dict, lat: float, lon: float) -> list[list[tuple[float, float]]]` (local metres around lat/lon)
  - `street.street_frame(lines, r_min: float, r_max: float) -> dict` with keys `x`, `y` (new centre, local metres), `radius_m`, `length_m`
  - `street.street_anchor(lines) -> tuple[float, float]` — point on the lines nearest the origin (0, 0 if none)

- [ ] **Step 1: Write the failing tests** — `tests/test_street.py`:

```python
import pytest

from geo import from_local
from street import street_anchor, street_frame, street_lines

LAT0, LON0 = 48.28646, 17.27221


def way(pts, id=1):
    return {"type": "way", "id": id, "geometry": [dict(zip(("lat", "lon"), from_local(x, y, LAT0, LON0))) for x, y in pts]}


def test_joins_connected_ways_and_drops_same_name_far_away():
    raw = {"elements": [
        way([(0, 0), (100, 0)], 1),
        way([(110, 5), (200, 5)], 2),          # 10 m gap -> same street
        way([(900, 0), (1000, 0)], 3),         # another village, same name
        {"type": "node", "id": 4, "lat": LAT0, "lon": LON0},
    ]}
    lines = street_lines(raw, LAT0, LON0)
    assert len(lines) == 2
    assert max(x for line in lines for x, _ in line) == pytest.approx(200, abs=0.5)


def test_no_ways_gives_no_lines():
    assert street_lines({"elements": []}, LAT0, LON0) == []
    assert street_lines({"elements": [{"type": "way", "id": 1, "geometry": []}]}, LAT0, LON0) == []


def test_frame_centres_on_midpoint_with_margin():
    f = street_frame([[(0, 0), (200, 0)]], 160, 300)
    assert (f["x"], f["y"]) == pytest.approx((100, 0))
    assert f["radius_m"] == pytest.approx(160)       # 200/2 + 60 = 160
    f = street_frame([[(0, 0), (400, 0)]], 160, 300)
    assert f["radius_m"] == pytest.approx(260)


def test_frame_long_street_stays_on_point():
    f = street_frame([[(-3000, 0), (1000, 0)]], 160, 300)
    assert (f["x"], f["y"], f["radius_m"]) == (0.0, 0.0, 300)
    assert f["length_m"] == pytest.approx(4000)


def test_frame_branching_street_uses_bbox_centre():
    f = street_frame([[(0, 0), (100, 0)], [(50, -40), (50, 40)]], 160, 300)
    assert (f["x"], f["y"]) == pytest.approx((50, 0))


def test_frame_without_lines_is_minimal_on_point():
    assert street_frame([], 160, 300) == {"x": 0.0, "y": 0.0, "radius_m": 160, "length_m": 0.0}


def test_anchor_is_nearest_point_on_street():
    assert street_anchor([[(-50, 20), (50, 20)]]) == pytest.approx((0, 20))
    assert street_anchor([]) == (0.0, 0.0)
```

Add to `tests/test_osm.py`:

```python
def test_street_query_escapes_name_and_uses_around():
    from osm import build_street_query
    q = build_street_query('Nám. "SNP" \\ 1', 48.1, 17.1)
    assert '["name"="Nám. \\"SNP\\" \\\\ 1"]' in q
    assert "(around:1500,48.100000,17.100000)" in q
    assert q.startswith("[out:json][timeout:25];way[\"highway\"]") and q.rstrip().endswith("out geom;")


def test_run_query_reports_cache_hits_in_stats(tmp_path):
    stats = []
    t = _transport([(200, {"elements": [1]})], [])
    run_query("q", str(tmp_path), transport=t, stats=stats)
    run_query("q", str(tmp_path), transport=t, stats=stats)
    assert stats == [False, True]


def test_run_query_passes_timeout(monkeypatch):
    seen = {}
    real = httpx.Client

    def spy(*a, **kw):
        seen["timeout"] = kw.get("timeout")
        return real(*a, **kw)

    monkeypatch.setattr(osm.httpx, "Client", spy)
    run_query("q", None, transport=_transport([(200, {"elements": []})], []), timeout_s=70)
    assert seen["timeout"] == 70
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_street.py tests/test_osm.py -v`
Expected: FAIL (`No module named 'street'`, `build_street_query` missing, unexpected `stats` / `timeout_s`).

- [ ] **Step 3: Implement** — in `src/osm.py` change `run_query` and add the street query:

```python
STREET_SEARCH_M = 1500


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
```

`src/street.py`:

```python
"""Street tier: join the OSM ways of one named street and frame the map around it."""
from shapely.geometry import LineString, Point
from shapely.ops import linemerge, nearest_points, unary_union

from geo import to_local

JOIN_M = 30.0  # ways closer than this belong to the same street
MARGIN_M = 60.0


def street_lines(raw: dict, lat: float, lon: float) -> list[list[tuple[float, float]]]:
    """Ways connected (transitively, within JOIN_M) to the way nearest (lat, lon), in local metres.

    Same-name streets in neighbouring villages are not connected, so they are dropped."""
    lines = []
    for el in raw.get("elements", []):
        if el.get("type") != "way":
            continue
        pts = [to_local(p["lat"], p["lon"], lat, lon) for p in el.get("geometry") or [] if p]
        if len(pts) >= 2:
            lines.append(LineString(pts))
    if not lines:
        return []
    origin = Point(0, 0)
    seed = min(range(len(lines)), key=lambda i: lines[i].distance(origin))
    keep, frontier = {seed}, [seed]
    while frontier:
        i = frontier.pop()
        for j, other in enumerate(lines):
            if j not in keep and lines[i].distance(other) <= JOIN_M:
                keep.add(j)
                frontier.append(j)
    return [list(lines[i].coords) for i in sorted(keep)]


def street_frame(lines, r_min: float, r_max: float) -> dict:
    """New map centre (local metres) and radius; long streets stay centred on the geocoded point."""
    if not lines:
        return {"x": 0.0, "y": 0.0, "radius_m": r_min, "length_m": 0.0}
    geoms = [LineString(line) for line in lines]
    length = sum(g.length for g in geoms)
    want = length / 2 + MARGIN_M
    if want > r_max:
        return {"x": 0.0, "y": 0.0, "radius_m": r_max, "length_m": length}
    merged = linemerge(unary_union(geoms))
    if merged.geom_type == "LineString":
        mid = merged.interpolate(0.5, normalized=True)
        cx, cy = mid.x, mid.y
    else:  # branching street: no single "halfway" point
        minx, miny, maxx, maxy = merged.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    return {"x": cx, "y": cy, "radius_m": max(r_min, want), "length_m": length}


def street_anchor(lines) -> tuple[float, float]:
    """Where the "Na predaj" tag goes: the point of the street nearest the map centre."""
    if not lines:
        return (0.0, 0.0)
    geom = unary_union([LineString(line) for line in lines])
    p = nearest_points(geom, Point(0, 0))[0]
    return (p.x, p.y)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_street.py tests/test_osm.py -v` → PASS; `.venv/bin/python -m pytest -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add src/osm.py src/street.py tests/test_street.py tests/test_osm.py
git commit -m "feat: street tier geometry — named-street query, way joining, map framing" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ks8oBdDjJanB3ngMLhZ38E"
```

---

### Task 4: City-tier POI categories and landmarks in `osm.py`

**Files:**
- Modify: `src/osm.py` (`POI_QUERIES`, `build_poi_query`, `fetch_pois`, `categorize_poi`, new `landmark_kind`, `build_area_query`, `fetch_area`), `tests/test_osm.py`

**Interfaces:**
- Consumes: `run_query(..., timeout_s, stats)` (Task 3).
- Produces:
  - `osm.landmark_kind(tags: dict) -> tuple[int, str] | None` — `(priority, Slovak label)`, lower priority is better.
  - `categorize_poi` returns `"bus_station"`, `"mall"`, `"landmark"` for the new tags (checked after all existing categories).
  - `osm.build_poi_query(lat, lon, categories, square_m: float = 0.0) -> str` — categories whose radius is `None` use `square_m`.
  - `osm.fetch_pois(lat, lon, categories, cache_dir, square_m: float = 0.0, stats: list | None = None) -> dict`
  - `osm.build_area_query(south, west, north, east, light: bool = False) -> str` — light: no footway/path/steps/track/cycleway ways, no tree nodes, `[timeout:60]`.
  - `osm.fetch_area(lat, lon, half_m, cache_dir, light: bool = False, stats: list | None = None) -> dict` — light uses HTTP timeout `CITY_TIMEOUT_S = 70`.

- [ ] **Step 1: Write the failing tests** — add to `tests/test_osm.py`:

```python
@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "townhall", "wikidata": "Q1"}, (1, "Radnica")),
    ({"place": "square", "name": "Hlavné námestie"}, (2, "Námestie")),
    ({"highway": "pedestrian", "area": "yes", "name": "Radničné námestie"}, (2, "Námestie")),
    ({"highway": "pedestrian", "area": "yes"}, None),
    ({"historic": "castle"}, (3, "Hrad")),
    ({"historic": "manor"}, (3, "Kaštieľ")),
    ({"building": "church"}, (4, "Kostol")),
    ({"amenity": "place_of_worship"}, (4, "Kostol")),
    ({"tourism": "museum"}, (5, "Múzeum")),
    ({"tourism": "attraction"}, (5, "Pamiatka")),
    ({"shop": "bakery"}, None),
])
def test_landmark_kind(tags, expected):
    from osm import landmark_kind
    assert landmark_kind(tags) == expected


@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "bus_station"}, "bus_station"),
    ({"shop": "mall"}, "mall"),
    ({"amenity": "townhall"}, "landmark"),
    ({"amenity": "pharmacy", "tourism": "attraction"}, "pharmacy"),  # existing categories win
])
def test_categorize_city_tier_tags(tags, expected):
    assert categorize_poi(tags) == expected


def test_poi_query_landmarks_use_the_map_square():
    q = build_poi_query(48.0, 17.0, ["landmark", "mall"], square_m=450)
    s, w, n, e = square_bbox(48.0, 17.0, 450)
    bbox = f"({s:.6f},{w:.6f},{n:.6f},{e:.6f})"
    for sel in ['["amenity"="townhall"]', '["place"="square"]', '["historic"~"^(castle|manor)$"]',
                '["building"~"^(church|cathedral)$"]', '["amenity"="place_of_worship"]',
                '["tourism"~"^(museum|attraction)$"]']:
        assert f"nwr{sel}{bbox};" in q
    s, w, n, e = square_bbox(48.0, 17.0, 15_000)
    assert f'nwr["shop"="mall"]({s:.6f},{w:.6f},{n:.6f},{e:.6f});' in q


def test_light_area_query_skips_footways_and_trees():
    q = build_area_query(48.1, 17.1, 48.2, 17.2, light=True)
    assert q.startswith("[out:json][timeout:60];")
    assert 'way["highway"]["highway"!~"^(footway|path|steps|track|cycleway)$"]' in q
    assert '"natural"="tree"' not in q
    assert build_area_query(48.1, 17.1, 48.2, 17.2).startswith("[out:json][timeout:25];")
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_osm.py -v`
Expected: FAIL (`landmark_kind` missing, unexpected `square_m` / `light`).

- [ ] **Step 3: Implement** in `src/osm.py`:

```python
CITY_TIMEOUT_S = 70

LANDMARK_SELECTORS = (
    '["amenity"="townhall"]',
    '["place"="square"]',
    '["highway"="pedestrian"]["area"="yes"]["name"]',
    '["historic"~"^(castle|manor)$"]',
    '["building"~"^(church|cathedral)$"]',
    '["amenity"="place_of_worship"]',
    '["tourism"~"^(museum|attraction)$"]',
)
```

Add to `POI_QUERIES` (a value may now be a tuple of selectors; radius `None` = the map square):

```python
    "bus_station":  ('["amenity"="bus_station"]', 30_000),
    "mall":         ('["shop"="mall"]', 15_000),
    "landmark":     (LANDMARK_SELECTORS, None),
```

(`LANDMARK_SELECTORS` must be defined above `POI_QUERIES`.)

```python
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
```

In `categorize_poi`, just before the final `return None`:

```python
    if amenity == "bus_station":
        return "bus_station"
    if tags.get("shop") == "mall":
        return "mall"
    if landmark_kind(tags):
        return "landmark"
```

Area query and fetchers:

```python
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
```

(Keep the existing `place=square` / `relation["highway"="pedestrian"]` lines — they move into the function body shown above; make sure they appear once.)

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_osm.py -v` → PASS; `.venv/bin/python -m pytest -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add src/osm.py tests/test_osm.py
git commit -m "feat(osm): landmark, bus station and mall categories; light city-tier area query" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ks8oBdDjJanB3ngMLhZ38E"
```

---

### Task 5: Tier-aware scene — POI selection, street distances, landmarks, focus, timing

**Files:**
- Modify: `src/scene_builder.py`, `tests/test_assemble.py`

**Interfaces:**
- Consumes: `street_lines`, `street_frame`, `street_anchor` (Task 3); `fetch_street`, `fetch_area(..., light, stats)`, `fetch_pois(..., square_m, stats)`, `landmark_kind` (Tasks 3–4); `cfg.radii.*` (Task 1).
- Produces:
  - `scene_builder.TIER_CATEGORIES: dict[str, frozenset[str]]`
  - `split_pois(lat, lon, radius_m, pois_raw, categories, street=None) -> tuple[list, list]` — `street`: list of local-metre polylines; distances measured to them when given.
  - `select_landmarks(lat, lon, radius_m, pois_raw) -> list[dict]` — near entries `{"category": "landmark", "kind", "name", "distance_m", "x", "y"}`, ≤ 3, one per priority.
  - `assemble_scene(lat, lon, radius_m, area, pois_raw, categories, tier="address", street=None) -> dict` — adds `"tier"`, `"focus"`; property only at the address tier.
  - `build_scene(lat, lon, cfg, tier="address", name=None) -> dict` — adds `"warnings"`, `"timing_ms"`, `"cached"`; street tier re-centres the scene and sets `focus.name`.
  - Scene `focus`: `{"kind": "building"}` | `{"kind": "street", "name": str, "lines": [[[x, y], …]], "anchor": [x, y]}` | `{"kind": "centre"}`.

- [ ] **Step 1: Write the failing tests** — add to `tests/test_assemble.py`:

```python
from scene_builder import TIER_CATEGORIES, select_landmarks


def cats(tier):
    return [c for c in CATS + ["bus_station", "mall", "landmark"] if c in TIER_CATEGORIES[tier]]


def test_tier_categories():
    assert "school" in TIER_CATEGORIES["street"] and "food" in TIER_CATEGORIES["street"]
    assert TIER_CATEGORIES["city"] == frozenset(
        {"hospital", "train", "park", "supermarket", "bus_station", "mall", "landmark", "city"})


def test_street_distances_are_measured_to_the_street():
    street = [[(-100, 50), (100, 50)]]
    pois = [node(0, 60, {"amenity": "school", "name": "ZŠ"}, 1)]
    near, _ = split_pois(LAT0, LON0, R, {"elements": pois}, CATS, street=street)
    assert near[0]["distance_m"] == 10           # 10 m from the street, 60 m from the centre


def test_landmarks_need_wiki_are_capped_and_one_per_kind():
    wiki = {"wikidata": "Q1"}
    pois = [
        node(10, 10, {"amenity": "townhall", "name": "Radnica", **wiki}, 1),
        node(20, 0, {"amenity": "townhall", "name": "Druhá radnica", **wiki}, 2),   # same kind -> dropped
        node(-30, 0, {"building": "church", "name": "Kostol sv. Martina", **wiki}, 3),
        node(0, -40, {"tourism": "museum", "name": "Múzeum", "wikipedia": "sk:Múzeum"}, 4),
        node(5, 5, {"historic": "castle", "name": "Bez wiki"}, 5),                  # no wiki -> dropped
        node(0, 60, {"historic": "castle", "name": "Hrad", **wiki}, 6),
        node(0, 500, {"place": "square", "name": "Ďaleko", **wiki}, 7),             # outside the square
    ]
    picked = select_landmarks(LAT0, LON0, R, {"elements": pois})
    assert [(p["kind"], p["name"]) for p in picked] == [("Radnica", "Radnica"), ("Hrad", "Hrad"), ("Kostol", "Kostol sv. Martina")]
    assert all(p["category"] == "landmark" and "x" in p for p in picked)


def test_city_scene_has_no_property_and_landmarks_near():
    s = assemble_scene(LAT0, LON0, R, {"elements": [way(rect(-5, -5, 5, 5), {"building": "house"})]},
                       {"elements": [node(10, 10, {"amenity": "townhall", "name": "Radnica", "wikidata": "Q1"}, 1),
                                     node(0, 5000, {"amenity": "school"}, 2)]},
                       cats("city"), tier="city")
    assert s["tier"] == "city" and s["focus"] == {"kind": "centre"}
    assert s["property"] == {"building_index": None}
    assert [p["category"] for p in s["near_pois"]] == ["landmark"]
    assert s["far_pois"] == []                   # school is not a city-tier category


def test_street_scene_focus_lines_clipped_and_anchor():
    street = [[(-300, 20), (300, 20)]]
    s = assemble_scene(LAT0, LON0, R, {"elements": []}, {"elements": []}, cats("street"), tier="street", street=street)
    assert s["focus"]["kind"] == "street"
    xs = [x for line in s["focus"]["lines"] for x, _ in line]
    assert min(xs) == pytest.approx(-R) and max(xs) == pytest.approx(R)
    assert s["focus"]["anchor"] == pytest.approx([0, 20])
    assert s["property"] == {"building_index": None}


def test_address_scene_focus_is_building():
    s = scene([way(rect(-5, -5, 5, 5), {"building": "house"})])
    assert s["tier"] == "address" and s["focus"] == {"kind": "building"}
    assert s["property"] == {"building_index": 0}


def test_build_scene_street_tier_recentres_and_reports_timing(monkeypatch, default_config):
    street_raw = {"elements": [way([(0, 0), (200, 0)], {"highway": "residential", "name": "Záhradná"}, closed=False)]}
    seen = {}
    monkeypatch.setattr(scene_builder, "fetch_street", lambda *a, **k: street_raw)

    def fake_area(lat, lon, half_m, cache_dir, light=False, stats=None):
        seen.update(lat=lat, lon=lon, half=half_m, light=light)
        stats.append(True)
        return {"elements": []}

    def fake_pois(lat, lon, categories, cache_dir, square_m=0.0, stats=None):
        seen["categories"] = categories
        stats.append(True)
        return {"elements": []}

    monkeypatch.setattr(scene_builder, "fetch_area", fake_area)
    monkeypatch.setattr(scene_builder, "fetch_pois", fake_pois)
    s = build_scene(LAT0, LON0, default_config, tier="street", name="Záhradná")
    expect_lat, expect_lon = from_local(100, 0, LAT0, LON0)
    assert (seen["lat"], seen["lon"]) == pytest.approx((expect_lat, expect_lon))
    assert seen["half"] == pytest.approx(160) and seen["light"] is False
    assert "school" in seen["categories"]
    assert s["focus"]["name"] == "Záhradná" and s["focus"]["anchor"] == pytest.approx([0, 0], abs=0.2)
    assert s["cached"] is True and isinstance(s["timing_ms"], int)


def test_build_scene_city_tier_is_light_and_street_failure_is_a_warning(monkeypatch, default_config):
    seen = {}

    def fake_area(lat, lon, half_m, cache_dir, light=False, stats=None):
        seen.update(half=half_m, light=light)
        stats.append(False)
        return {"elements": []}

    monkeypatch.setattr(scene_builder, "fetch_area", fake_area)
    monkeypatch.setattr(scene_builder, "fetch_pois", lambda *a, **k: {"elements": []})
    s = build_scene(LAT0, LON0, default_config, tier="city")
    assert seen == {"half": 450, "light": True}
    assert s["cached"] is False

    def boom(*a, **k):
        raise OverpassError("down")

    monkeypatch.setattr(scene_builder, "fetch_street", boom)
    s = build_scene(LAT0, LON0, default_config, tier="street", name="X")
    assert s["warnings"] == ["street_fetch_failed"] and s["radius_m"] == 160
```

Also update the existing concurrency test's fakes to accept the new keyword arguments:

```python
    def slow_area(*a, **k):
        time.sleep(0.3)
        return {"elements": []}

    def slow_pois(*a, **k):
        time.sleep(0.3)
        return {"elements": []}
```

and in `test_build_scene_poi_failure_adds_warning` / `test_build_scene_area_failure_raises` change the lambdas / `boom` to accept `*a, **k`.

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -v`
Expected: FAIL (`TIER_CATEGORIES` / `select_landmarks` missing, unexpected `tier` / `street` keywords).

- [ ] **Step 3: Implement** in `src/scene_builder.py`:

Imports:

```python
import time

from shapely.geometry import LineString, MultiLineString, Point, Polygon, box
from shapely.ops import polygonize

from geo import compute_bearing, from_local, haversine_m, to_local
from osm import OverpassError, categorize_poi, fetch_area, fetch_pois, fetch_street, landmark_kind
from street import street_anchor, street_frame, street_lines
```

Constants (next to the other POI constants):

```python
_BUYER = frozenset({"hospital", "supermarket", "school", "kindergarten", "pharmacy", "bus_stop", "train", "park",
                    "playground", "food", "post", "bank", "doctors", "city"})
TIER_CATEGORIES = {
    "address": _BUYER,
    "street": _BUYER,
    # A city has dozens of schools and pharmacies — "the one nearest the square" means nothing.
    "city": frozenset({"hospital", "train", "park", "supermarket", "bus_station", "mall", "landmark", "city"}),
}
MAX_LANDMARKS = 3
NO_BUILDING = frozenset({"park", "playground"})
```

`split_pois` — new signature and distance function; landmarks are handled by `select_landmarks`, so skip them here:

```python
def split_pois(lat: float, lon: float, radius_m: float, pois_raw: dict,
               categories: list[str], street=None) -> tuple[list[dict], list[dict]]:
    wanted = set(categories) - {"landmark"}
    street_geom = MultiLineString(street) if street else None

    def distance(plat: float, plon: float) -> float:
        if street_geom is None:
            return haversine_m(lat, lon, plat, plon)
        return street_geom.distance(Point(*to_local(plat, plon, lat, lon)))

    best: dict[str, tuple[float, dict, tuple[float, float]]] = {}
    cities: dict[str, tuple[float, dict, tuple[float, float]]] = {}
    for el in pois_raw.get("elements", []):
        tags = el.get("tags") or {}
        cat = categorize_poi(tags)
        pos = _element_latlon(el)
        if cat not in wanted or pos is None:
            continue
        if cat == "hospital" and not _is_general_hospital(tags):
            continue
        if cat == "park" and not _is_real_park(el, tags):
            continue
        d = distance(*pos)
        # … the rest of the loop body and the near/far split stay exactly as they are today …
```

(Only the header, `wanted`, the `distance` helper and `d = distance(*pos)` change; the city grouping, candidate sorting and near/far split stay as they are.)

New function below `split_pois`:

```python
def select_landmarks(lat: float, lon: float, radius_m: float, pois_raw: dict) -> list[dict]:
    """Up to MAX_LANDMARKS notable places inside the square: best kind first, then nearest; one per kind."""
    limit = radius_m - NEAR_INSET_M
    found = []
    for el in pois_raw.get("elements", []):
        tags = el.get("tags") or {}
        kind = landmark_kind(tags)
        pos = _element_latlon(el)
        if kind is None or pos is None or not (tags.get("wikipedia") or tags.get("wikidata")):
            continue
        x, y = to_local(*pos, lat, lon)
        if abs(x) > limit or abs(y) > limit:
            continue  # landmarks describe the centre, not a direction
        found.append((kind[0], haversine_m(lat, lon, *pos), kind[1], tags, x, y))
    found.sort(key=lambda f: (f[0], f[1]))
    picked, seen = [], set()
    for prio, d, label, tags, x, y in found:
        if prio in seen:
            continue
        seen.add(prio)
        picked.append({"category": "landmark", "kind": label, "name": tags.get("name", ""),
                       "distance_m": round(d), "x": _r(x), "y": _r(y)})
        if len(picked) == MAX_LANDMARKS:
            break
    return picked
```

`assemble_scene` — signature and the end of the function:

```python
def assemble_scene(lat: float, lon: float, radius_m: float, area: dict, pois_raw: dict,
                   categories: list[str], tier: str = "address", street=None) -> dict:
    # … the element loop is unchanged …

    near, far = split_pois(lat, lon, radius_m, pois_raw, categories, street=street if tier == "street" else None)
    if "landmark" in categories:
        near += select_landmarks(lat, lon, radius_m, pois_raw)
    property_index = find_property(buildings) if tier == "address" else None
    for poi in near:
        if poi["category"] not in NO_BUILDING and poi.get("kind") != "Námestie":
            poi["building_index"] = poi_building(poi, buildings, property_index)
    return {
        "center": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "tier": tier,
        "focus": _focus(tier, street, square),
        "buildings": buildings,
        "property": {"building_index": property_index},
        "roads": roads,
        "areas": areas,
        "trees": trees,
        "near_pois": near,
        "far_pois": far,
    }


def _focus(tier: str, street, square) -> dict:
    if tier == "address":
        return {"kind": "building"}
    if tier == "city":
        return {"kind": "centre"}
    lines = []
    for line in street or []:
        for part in _parts(LineString(line).intersection(square), "LineString"):
            lines.append([[_r(x), _r(y)] for x, y in part.coords])
    ax, ay = street_anchor(street or [])
    return {"kind": "street", "lines": lines, "anchor": [_r(ax), _r(ay)]}
```

`build_scene`:

```python
def build_scene(lat: float, lon: float, cfg: Config, tier: str = "address", name: str | None = None) -> dict:
    t0 = time.perf_counter()
    cache_dir = cfg.cache.dir if cfg.cache.enabled else None
    stats: list[bool] = []  # one entry per Overpass query: True = served from cache
    warnings: list[str] = []
    lines = None
    radius = {"address": cfg.radii.display_meters, "city": cfg.radii.city_meters}.get(tier, cfg.radii.street_min)
    if tier == "street":
        lines = []
        if name:
            try:
                lines = street_lines(fetch_street(name, lat, lon, cache_dir, stats), lat, lon)
            except OverpassError as exc:
                logger.warning("Street fetch failed: %s", exc)
                warnings.append("street_fetch_failed")
        frame = street_frame(lines, cfg.radii.street_min, cfg.radii.street_max)
        radius = frame["radius_m"]
        lat, lon = from_local(frame["x"], frame["y"], lat, lon)
        # Shifting local metres is exact enough for a few hundred metres (equirectangular projection).
        lines = [[(x - frame["x"], y - frame["y"]) for x, y in line] for line in lines]
    categories = [c for c in cfg.poi.enabled() if c in TIER_CATEGORIES[tier]]
    with ThreadPoolExecutor(max_workers=2) as pool:
        area_job = pool.submit(fetch_area, lat, lon, radius, cache_dir, tier == "city", stats)
        poi_job = pool.submit(fetch_pois, lat, lon, categories, cache_dir, radius, stats)
        area = area_job.result()
    try:
        pois_raw = poi_job.result()
    except OverpassError as exc:
        logger.warning("POI fetch failed: %s", exc)
        pois_raw = {"elements": []}
        warnings.append("poi_fetch_failed")
    scene = assemble_scene(lat, lon, radius, area, pois_raw, categories, tier=tier, street=lines)
    if tier == "street":
        scene["focus"]["name"] = name or ""
    scene["warnings"] = warnings
    scene["timing_ms"] = round((time.perf_counter() - t0) * 1000)
    scene["cached"] = all(stats)
    return scene
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -v` → PASS; `.venv/bin/python -m pytest -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add src/scene_builder.py tests/test_assemble.py
git commit -m "feat(scene): tier-aware POIs, street distances, landmarks, focus, timing and cache flag" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ks8oBdDjJanB3ngMLhZ38E"
```

---

### Task 6: `/api/scene` accepts `tier` and `name`

**Files:**
- Modify: `src/api.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: `build_scene(lat, lon, cfg, tier, name)` (Task 5).
- Produces: `GET /api/scene?lat&lon&tier=address|street|city&name=` (invalid `tier` → 422). Reverse geocoding only at the address tier; other tiers return `"address": null` (the frontend shows its search label).

- [ ] **Step 1: Write the failing tests** — add to `tests/test_api.py`:

```python
async def test_scene_passes_tier_and_name_and_skips_reverse_geocode():
    calls = {}

    def fake_build(lat, lon, cfg, tier, name):
        calls.update(tier=tier, name=name)
        return dict(SCENE)

    rev = AsyncMock(return_value="x")
    with patch("api.build_scene", side_effect=fake_build), patch("api._reverse_geocode", rev):
        r = await _get("/api/scene?lat=48.28&lon=17.27&tier=street&name=Z%C3%A1hradn%C3%A1")
    assert r.status_code == 200 and r.json()["address"] is None
    assert calls == {"tier": "street", "name": "Záhradná"}
    rev.assert_not_called()


async def test_scene_rejects_unknown_tier():
    assert (await _get("/api/scene?lat=48.28&lon=17.27&tier=planet")).status_code == 422
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_api.py -v`
Expected: FAIL (tier ignored → 200 for `planet`; `build_scene` called with 3 args).

- [ ] **Step 3: Implement** — in `src/api.py` add `from typing import Annotated, Literal` and replace the scene endpoint body:

```python
@app.get("/api/scene")
async def scene(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    fixture: bool = False,
    tier: Literal["address", "street", "city"] = "address",
    name: Annotated[str | None, Query(max_length=200)] = None,
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
    data["address"] = await _reverse_geocode(lat, lon) if tier == "address" else None
    return data
```

Update `test_scene_returns_scene_with_address` so its patched `build_scene` accepts the extra arguments (`patch("api.build_scene", return_value=dict(SCENE))` already accepts any args — no change needed).

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "feat(api): scene tier and street name parameters" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ks8oBdDjJanB3ngMLhZ38E"
```

---

### Task 7: Frontend helpers — URL view, detail switches, load-time text, request gate, new categories

**Files:**
- Modify: `frontend/src/url.js`, `frontend/src/url.test.js`, `frontend/src/format.js`, `frontend/src/format.test.js`, `frontend/src/palette.js`, `frontend/src/icons.js`, `frontend/src/overlay/describe.js`, `frontend/src/overlay/describe.test.js`
- Create: `frontend/src/map/detail.js`, `frontend/src/map/detail.test.js`, `frontend/src/requestGate.js`, `frontend/src/requestGate.test.js`

**Interfaces:**
- Produces:
  - `url.getViewFromURL(search: string) -> {lat, lon, tier, name, label} | null`
  - `url.viewToSearch(view) -> string` (starts with `?`)
  - `url.sceneUrl(view, fixture: boolean) -> string`
  - `detail.detailFor(tier) -> {lanes, decor, people, pigeons, seededTrees, maxCars, shadowMap, property, streetFocus}`
  - `format.formatLoadTime(ms: number, cached: boolean) -> string`, `format.tierLabel(tier) -> 'adresa'|'ulica'|'mesto'`
  - `requestGate.createRequestGate() -> {next(): number, isCurrent(token: number): boolean}`
  - `CATEGORIES.landmark|bus_station|mall`; `poiInfo` uses `poi.kind` as the category label for landmarks.

- [ ] **Step 1: Write the failing tests**

`frontend/src/url.test.js` — append:

```js
import { getViewFromURL, sceneUrl, viewToSearch } from './url.js';

describe('view URL', () => {
  it('reads tier, name and label', () => {
    expect(getViewFromURL('?lat=48.1&lon=17.1&tier=street&name=Z%C3%A1hradn%C3%A1&label=Z%C3%A1hradn%C3%A1%2C+Pezinok'))
      .toEqual({ lat: 48.1, lon: 17.1, tier: 'street', name: 'Záhradná', label: 'Záhradná, Pezinok' });
  });
  it('plain lat/lon is the address tier; bad tier falls back', () => {
    expect(getViewFromURL('?lat=48.1&lon=17.1')).toEqual({ lat: 48.1, lon: 17.1, tier: 'address', name: null, label: null });
    expect(getViewFromURL('?lat=48.1&lon=17.1&tier=planet').tier).toBe('address');
    expect(getViewFromURL('?tier=city')).toBeNull();
  });
  it('round-trips and builds the scene URL', () => {
    const v = { lat: 48.1, lon: 17.1, tier: 'street', name: 'Nám. SNP', label: 'Nám. SNP, Pezinok' };
    expect(getViewFromURL(viewToSearch(v))).toEqual(v);
    expect(sceneUrl(v, false)).toBe('/api/scene?lat=48.1&lon=17.1&tier=street&name=N%C3%A1m.+SNP');
    expect(sceneUrl({ ...v, tier: 'city', name: 'Pezinok' }, true)).toBe('/api/scene?lat=48.1&lon=17.1&tier=city&fixture=true');
  });
});
```

`frontend/src/map/detail.test.js`:

```js
import { describe, expect, it } from 'vitest';
import { detailFor } from './detail.js';

describe('detailFor', () => {
  it('address keeps everything', () => {
    expect(detailFor('address')).toMatchObject({ decor: true, people: 1, pigeons: true, property: true, streetFocus: false, shadowMap: 1024 });
  });
  it('street halves people and drops decor, shows the street', () => {
    expect(detailFor('street')).toMatchObject({ decor: false, people: 0.5, pigeons: false, property: false, streetFocus: true, shadowMap: 2048 });
  });
  it('city is the lightest', () => {
    expect(detailFor('city')).toMatchObject({ lanes: false, people: 0, seededTrees: false, maxCars: 10, property: false });
  });
  it('unknown tier behaves like address', () => expect(detailFor(undefined)).toEqual(detailFor('address')));
});
```

`frontend/src/requestGate.test.js`:

```js
import { describe, expect, it } from 'vitest';
import { createRequestGate } from './requestGate.js';

describe('createRequestGate', () => {
  it('only the latest token is current', () => {
    const gate = createRequestGate();
    const a = gate.next();
    const b = gate.next();
    expect(gate.isCurrent(a)).toBe(false);
    expect(gate.isCurrent(b)).toBe(true);
  });
});
```

`frontend/src/format.test.js` — append:

```js
import { formatLoadTime, tierLabel } from './format.js';

describe('formatLoadTime', () => {
  it.each([[12400, false, 'Načítané za 12,4 s · nové dáta'], [95, true, 'Načítané za 0,1 s · z cache'],
    [0, true, 'Načítané za 0,0 s · z cache']])('%i ms cached=%s', (ms, c, s) => expect(formatLoadTime(ms, c)).toBe(s));
  it('tier labels', () => expect(['address', 'street', 'city'].map(tierLabel)).toEqual(['adresa', 'ulica', 'mesto']));
});
```

`frontend/src/overlay/describe.test.js` — append inside `describe('poiInfo', …)`:

```js
  it('landmarks use their kind as the label', () =>
    expect(poiInfo({ category: 'landmark', kind: 'Radnica', name: 'Stará radnica', distance_m: 40 }).lines[0])
      .toBe('Radnica · 40 m · ≈ 1 min pešo'));
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test`
Expected: FAIL (missing exports / modules).

- [ ] **Step 3: Implement**

`frontend/src/url.js` — keep the existing exports and add:

```js
const TIERS = new Set(['address', 'street', 'city']);

export function getViewFromURL(search) {
  const coords = getCoordsFromURL(search);
  if (!coords) return null;
  const p = new URLSearchParams(search);
  const tier = TIERS.has(p.get('tier')) ? p.get('tier') : 'address';
  return { ...coords, tier, name: p.get('name') || null, label: p.get('label') || null };
}

export function viewToSearch(view) {
  const p = new URLSearchParams({ lat: String(view.lat), lon: String(view.lon), tier: view.tier });
  if (view.name) p.set('name', view.name);
  if (view.label) p.set('label', view.label);
  return `?${p}`;
}

export function sceneUrl(view, fixture) {
  const p = new URLSearchParams({ lat: String(view.lat), lon: String(view.lon), tier: view.tier });
  if (view.tier === 'street' && view.name) p.set('name', view.name);
  if (fixture) p.set('fixture', 'true');
  return `/api/scene?${p}`;
}
```

`frontend/src/map/detail.js`:

```js
// What each tier draws. Bigger maps drop the small, per-object details — they would be
// invisible at that scale and cost the most draw calls.
const DETAIL = {
  address: { lanes: true, decor: true, people: 1, pigeons: true, seededTrees: true, maxCars: 6, shadowMap: 1024, property: true, streetFocus: false },
  street: { lanes: true, decor: false, people: 0.5, pigeons: false, seededTrees: true, maxCars: 6, shadowMap: 2048, property: false, streetFocus: true },
  city: { lanes: false, decor: false, people: 0, pigeons: false, seededTrees: false, maxCars: 10, shadowMap: 2048, property: false, streetFocus: false },
};

export function detailFor(tier) {
  return DETAIL[tier] ?? DETAIL.address;
}
```

`frontend/src/requestGate.js`:

```js
// "Latest request wins": a newer search makes every older token stale.
export function createRequestGate() {
  let current = 0;
  return {
    next: () => ++current,
    isCurrent: (token) => token === current,
  };
}
```

`frontend/src/format.js` — append:

```js
export function formatLoadTime(ms, cached) {
  const s = (Math.round(ms / 100) / 10).toFixed(1).replace('.', ',');
  return `Načítané za ${s} s · ${cached ? 'z cache' : 'nové dáta'}`;
}

const TIER_LABELS = { address: 'adresa', street: 'ulica', city: 'mesto' };

export function tierLabel(tier) {
  return TIER_LABELS[tier] ?? tier;
}
```

`frontend/src/palette.js` — add to `CATEGORIES`:

```js
  landmark: { label: 'Pamiatka', color: '#B5838D' },
  bus_station: { label: 'Autobusová stanica', color: '#7B5EA7' },
  mall: { label: 'Nákupné centrum', color: '#2F9C8F' },
```

`frontend/src/icons.js` — add to `PATHS`:

```js
  landmark: '<path d="M3 21h18M5 21V10M19 21V10M9 21V10M15 21V10M2 10h20L12 3z"/>',
  bus_station: '<rect x="4" y="3" width="16" height="14" rx="3"/><path d="M4 10h16M8 20v-3M16 20v-3M9 6.5h6"/>',
  mall: '<path d="M5 8h14l-1 12H6z"/><path d="M9 8a3 3 0 0 1 6 0"/>',
```

`frontend/src/overlay/describe.js` — in `poiInfo`, change the first line of the body:

```js
  const { label: categoryLabel, color } = categoryInfo(poi.category);
  const label = poi.kind ?? categoryLabel;
```

(the rest of `poiInfo` keeps using `label`.)

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test` → all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): view URL, tier detail switches, load-time text, request gate, city-tier categories" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ks8oBdDjJanB3ngMLhZ38E"
```

---

### Task 8: Merged building meshes with hover picking and a glow overlay

**Files:**
- Modify: `frontend/src/map/buildings.js`, `frontend/src/map/hover.js`, `frontend/src/map/stage.js` (hover wiring + full dispose), `frontend/src/overlay/labels.js` (dispose), `frontend/src/overlay/tooltip.js` (dispose)
- Create: `frontend/src/map/buildings.test.js`

**Interfaces:**
- Produces:
  - `addBuildings(world, buildings, propertyIndex, mat, highlights) -> THREE.Mesh[]` — one mesh per material; every geometry has a `buildingIndex` float attribute (one value per vertex).
  - `buildingIndexAt(hit) -> number | null` — reads the attribute for a raycast hit.
  - `glowGeometry(building) -> THREE.BufferGeometry` — the footprint extruded to `height + 0.4`, scaled 1.02 around its centroid.
  - `createHover({container, camera, meshes, world, buildings, tooltip, describe, requestRender})` — same `onLabel`, `clear`, `dispose` as today.
  - `createOverlay(...)` and `createTooltip(...)` return an extra `dispose()` that removes their DOM nodes.

- [ ] **Step 1: Write the failing test** — `frontend/src/map/buildings.test.js`:

```js
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { addBuildings, buildingIndexAt, glowGeometry } from './buildings.js';

const mat = (() => {
  const cache = new Map();
  return (color, opts = {}) => {
    const key = `${color}|${opts.flatShading ? 1 : 0}`;
    if (!cache.has(key)) cache.set(key, new THREE.MeshLambertMaterial({ color, ...opts }));
    return cache.get(key);
  };
})();

const square = (x, y, s) => [[x, y], [x + s, y], [x + s, y + s], [x, y + s]];
const buildings = [
  { footprint: square(0, 0, 10), kind: 'apartment', height: 12 },
  { footprint: square(30, 0, 10), kind: 'apartment', height: 9 },
  { footprint: square(60, 0, 8), kind: 'house', height: 6 },
];

describe('addBuildings (merged)', () => {
  it('merges into one mesh per material and tags every vertex with its building', () => {
    const added = [];
    const meshes = addBuildings({ add: (m) => added.push(m) }, buildings, null, mat, new Map());
    expect(meshes.length).toBe(added.length);
    expect(meshes.length).toBeLessThan(buildings.length * 2);
    const seen = new Set();
    for (const m of meshes) {
      const attr = m.geometry.getAttribute('buildingIndex');
      expect(attr.count).toBe(m.geometry.getAttribute('position').count);
      for (let i = 0; i < attr.count; i++) seen.add(attr.getX(i));
    }
    expect([...seen].sort()).toEqual([0, 1, 2]);
  });

  it('buildingIndexAt reads the hit face', () => {
    const meshes = addBuildings({ add() {} }, buildings, null, mat, new Map());
    const ray = new THREE.Raycaster(new THREE.Vector3(35, 100, -5), new THREE.Vector3(0, -1, 0));
    const hit = ray.intersectObjects(meshes, false)[0];
    expect(buildingIndexAt(hit)).toBe(1);
    expect(buildingIndexAt(undefined)).toBeNull();
  });

  it('glowGeometry covers the building a bit above its height', () => {
    const g = glowGeometry(buildings[0]);
    g.computeBoundingBox();
    expect(g.boundingBox.max.y).toBeCloseTo(12.4);
    expect(g.boundingBox.max.x).toBeGreaterThan(10);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/map/buildings.test.js`
Expected: FAIL (`buildingIndexAt` / `glowGeometry` not exported; mesh count = one per part).

- [ ] **Step 3: Implement**

`frontend/src/map/buildings.js` — replace `addMesh` / `addBuildings` and add the helpers:

```js
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

const GLOW_LIFT_M = 0.4;
const GLOW_SCALE = 1.02;

// Tag every vertex with its building so a raycast hit on a merged mesh can be traced back.
function tagged(geo, index) {
  geo.deleteAttribute('uv'); // buildings are untextured; merge needs identical attribute sets
  const ids = new Float32Array(geo.getAttribute('position').count).fill(index);
  geo.setAttribute('buildingIndex', new THREE.BufferAttribute(ids, 1));
  return geo;
}

// Returns one mesh per material (all buildings merged), each vertex tagged with buildingIndex.
// Thousands of buildings at the city tier would otherwise mean thousands of draw calls.
export function addBuildings(world, buildings, propertyIndex, mat, highlights = new Map()) {
  const buckets = new Map(); // material -> geometries
  const put = (material, geo) => {
    if (!buckets.has(material)) buckets.set(material, []);
    buckets.get(material).push(geo);
  };
  buildings.forEach((b, i) => {
    const fp = b.footprint;
    if (!fp || fp.length < 3) return;
    const isProperty = i === propertyIndex;
    const [cx, cy] = centroid(fp);
    const h = hashPoint(cx, cy);
    const wall = isProperty ? PALETTE.propertyWalls
      : b.kind === 'other' ? PALETTE.otherWalls
        : PALETTE.walls[h % PALETTE.walls.length];
    const roof = isProperty ? PALETTE.property
      : highlights.get(i) ?? PALETTE.roofs[(h >>> 4) % PALETTE.roofs.length];
    try {
      const type = roofType(b.kind, fp);
      const wallHeight = type === 'flat' ? Math.max(1, b.height - FLAT_CAP_M) : b.height;
      put(mat(wall), tagged(extrude(fp, wallHeight, 0), i));
      if (type === 'flat') {
        put(mat(roof), tagged(extrude(fp, FLAT_CAP_M, wallHeight), i));
      } else if (type !== 'none') {
        const tris = roofTriangles(orientedRect(fp), type);
        put(mat(roof, { flatShading: true, side: THREE.DoubleSide }), tagged(roofGeometry(tris, b.height), i));
      }
    } catch (err) {
      console.warn('hoodiemap: skipped building', b, err);
    }
  });
  const meshes = [];
  for (const [material, geos] of buckets) {
    const mesh = new THREE.Mesh(mergeGeometries(geos, false), material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    world.add(mesh);
    meshes.push(mesh);
    geos.forEach((g) => g.dispose());
  }
  return meshes;
}

export function buildingIndexAt(hit) {
  if (!hit?.face) return null;
  return hit.object.geometry.getAttribute('buildingIndex')?.getX(hit.face.a) ?? null;
}

export function glowGeometry(building) {
  const [cx, cy] = centroid(building.footprint);
  const fp = building.footprint.map(([x, y]) => [cx + (x - cx) * GLOW_SCALE, cy + (y - cy) * GLOW_SCALE]);
  return extrude(fp, building.height + GLOW_LIFT_M, 0);
}
```

(`extrude`, `roofGeometry`, `centroid`, `hashPoint`, `roofType`, `roofTriangles`, `orientedRect`, `FLAT_CAP_M` stay as they are; the old `addMesh` is deleted.)

`frontend/src/map/hover.js` — replace the material-swapping glow with an overlay mesh and read the index from the hit:

```js
import * as THREE from 'three';
import { buildingIndexAt, glowGeometry } from './buildings.js';

const LABEL_SELECTOR = '.gm-near, .gm-far, .gm-tag';

// Hover (and tap) picking of buildings: a soft white shell appears over the building under
// the pointer and the tooltip describes it. Labels report their own hover via onLabel.
export function createHover({ container, camera, meshes, world, buildings, tooltip, describe, requestRender }) {
  const glowMat = new THREE.MeshBasicMaterial({ color: '#FFFFFF', transparent: true, opacity: 0.28, depthWrite: false });
  let lit = null; // building index currently glowing
  let glow = null;
  let pinned = false; // touch: keep the tooltip until the next tap

  function light(index) {
    if (index === lit) return;
    if (glow) {
      world.remove(glow);
      glow.geometry.dispose();
      glow = null;
    }
    lit = index;
    if (lit != null && buildings[lit]) {
      glow = new THREE.Mesh(glowGeometry(buildings[lit]), glowMat);
      glow.renderOrder = 2;
      world.add(glow);
    }
    requestRender();
  }

  const raycaster = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function pick(clientX, clientY) {
    const rect = container.getBoundingClientRect();
    ndc.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    return { index: buildingIndexAt(raycaster.intersectObjects(meshes, false)[0]), x: clientX - rect.left, y: clientY - rect.top };
  }

  // … showBuilding, clear, onMove, onDown, listeners and onLabel stay exactly as they are today …

  return {
    onLabel,
    clear,
    dispose() {
      container.removeEventListener('pointermove', onMove);
      container.removeEventListener('pointerdown', onDown);
      if (glow) {
        world.remove(glow);
        glow.geometry.dispose(); // no light(null): it would render one more frame while tearing down
      }
      glowMat.dispose();
    },
  };
}
```

(The `glowing()` material cache, `originals` map and `byIndex` map are deleted; `GLOW` / `GLOW_INTENSITY` constants are deleted.)

`frontend/src/overlay/tooltip.js` — return `{ show, hide, dispose: () => tip.remove() }`.

`frontend/src/overlay/labels.js` — return `{ update, measure, dispose: () => root.remove() }`.

`frontend/src/map/stage.js` — pass the new hover arguments and dispose everything:

```js
  const tooltip = createTooltip(container);
  const hover = createHover({
    container, camera, meshes: buildingMeshes, world, buildings: scene.buildings, tooltip,
    describe: (i) => buildingInfo(scene.buildings[i], { isProperty: i === propertyIndex, poi: poiByBuilding.get(i) }),
    requestRender: () => { if (!raf) frame(performance.now()); },
  });
```

and replace `dispose()`:

```js
    dispose() {
      cancelAnimationFrame(raf);
      raf = 0;
      visible = false;
      hover.dispose();
      overlay.dispose();
      tooltip.dispose();
      ro.disconnect();
      io.disconnect();
      document.removeEventListener('visibilitychange', start);
      world.traverse((o) => {
        o.geometry?.dispose();
        for (const m of [o.material].flat()) {
          m?.map?.dispose();
          m?.dispose();
        }
      });
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    },
```

- [ ] **Step 4: Run tests and check the running app**

Run: `cd frontend && npm test` → all pass.
Then open `http://localhost:5173/?lat=48.28646434486518&lon=17.27221245956356` (servers from the README): hovering the Billa roof still shows the Billa bubble and a white shell over the building; no console errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "perf(frontend): merge building meshes per material; hover via vertex building index and glow shell" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ks8oBdDjJanB3ngMLhZ38E"
```

---

### Task 9: Tier rendering — detail switches, street highlight, optional tag

**Files:**
- Create: `frontend/src/map/focus.js`
- Modify: `frontend/src/map/stage.js`, `frontend/src/map/ground.js` (export `flatGeometry`, `lanes` option), `frontend/src/map/trees.js` (`seeded` option), `frontend/src/map/placement.js` (`planCars(roads, rng, max)`), `frontend/src/map/cars.js` (`max` pass-through), `frontend/src/map/people.js` (`share` factor), `frontend/src/overlay/labels.js` (optional anchor / tag info), `frontend/src/map/placement.test.js`

**Interfaces:**
- Consumes: `detailFor` (Task 7); `scene.tier`, `scene.focus` (Task 5); merged buildings + hover (Task 8).
- Produces:
  - `addStreetFocus(world, focus, mat) -> {update(t), anchor: {x, y, h, base}}`
  - `addGround(world, scene, mat, { lanes = true } = {})`
  - `addTrees(world, scene, mat, { seeded = true } = {})`
  - `planCars(roads, rng, max = MAX_CARS)`, `addCars(world, roads, mat, rng, max)`
  - `addPedestrians(world, roads, mat, rng, share = 1)`, `addCyclists(world, roads, mat, rng, share = 1)`
  - `createOverlay(container, scene, project, anchor | null, onLabel, tagInfo | null)` — no tag when `anchor` is null.

- [ ] **Step 1: Write the failing test** — append to `frontend/src/map/placement.test.js` inside `describe('cars', …)`:

```js
  it('respects a custom car cap', () => {
    const long = [{ kind: 'main', points: [[-2000, 0], [2000, 0]] }];
    expect(planCars(long, mulberry32(1))).toHaveLength(6);
    expect(planCars(long, mulberry32(1), 10)).toHaveLength(10);
  });
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/map/placement.test.js`
Expected: FAIL (second expectation gets 6).

- [ ] **Step 3: Implement**

`frontend/src/map/placement.js`:

```js
export function planCars(roads, rng, max = MAX_CARS) {
  return planMovers(roads, rng, {
    kinds: ['main', 'street'], max, metersPer: METERS_PER_CAR, speed: [8, 14],
    lane: () => LANE_OFFSET_M, colors: PALETTE.cars,
  });
}
```

`frontend/src/map/cars.js`: `export function addCars(world, roads, mat, rng, max) {` and `const cars = planCars(roads, rng, max);`.

`frontend/src/map/people.js`:

```js
export function addPedestrians(world, roads, mat, rng, share = 1) {
  const all = [...planPedestrians(roads, rng), ...planZoneWalkers(roads, rng)];
  return addMovers(world, all.slice(0, Math.round(all.length * share)), (m) => makePerson(mat, m.color), walkBob);
}
```

and in `addCyclists(world, roads, mat, rng, share = 1)` use `const plan = planCyclists(roads, rng); plan.slice(0, Math.round(plan.length * share))` as the list passed to `addMovers`.

`frontend/src/map/trees.js`: signature `addTrees(world, scene, mat, { seeded = true } = {})`, and
`const pts = seeded ? seedTreePositions(scene, rng) : (scene.trees ?? []).map((t) => [t.x, t.y]);`.

`frontend/src/map/ground.js`: `export function flatGeometry(...)` (was private), signature `addGround(world, scene, mat, { lanes = true } = {})`, and wrap the lane-marking block in `if (lanes) { … }` (the `const centre = CENTRE_LINE[kind]; if (!centre) continue;` block and the edge lines).

`frontend/src/map/focus.js`:

```js
import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { flatGeometry } from './ground.js';
import { ribbonTriangles } from './lines.js';

// Street tier: the street being sold on glows in the property colour under the road surface
// (wider than the road, so a soft band shows on both sides), and the tag sits on the street.
const FOCUS_WIDTH_M = 14;
const LEVEL_Y = 0.058; // just below streets (0.06), above paths and parks

export function addStreetFocus(world, focus, mat) {
  const lines = focus?.lines ?? [];
  const [ax, ay] = focus?.anchor ?? [0, 0];
  const material = new THREE.MeshBasicMaterial({
    color: PALETTE.property, transparent: true, opacity: 0.35, depthWrite: false,
    side: THREE.DoubleSide, clippingPlanes: mat.clippingPlanes,
  });
  if (lines.length) {
    world.add(new THREE.Mesh(flatGeometry(ribbonTriangles(lines, FOCUS_WIDTH_M), LEVEL_Y), material));
  }
  return {
    update(t) {
      material.opacity = 0.28 + Math.sin(t * 2) * 0.1;
    },
    anchor: { x: ax, y: ay, h: 10, base: 0 },
  };
}
```

`frontend/src/overlay/labels.js`:

- signature `createOverlay(container, scene, project, anchor, onLabel = () => {}, tagInfo = null)`;
- create the tag only when `anchor` is set:

```js
  const tag = anchor ? el('div', 'gm-tag', root) : null;
  if (tag) {
    tag.textContent = 'Na predaj';
    const propertyIndex = scene.property?.building_index ?? null;
    const info = propertyIndex != null
      ? buildingInfo(scene.buildings[propertyIndex], { isProperty: true })
      : tagInfo;
    if (info) interactive(tag, info, propertyIndex, onLabel);
  }
```

- in `measure()`: `if (tag) { tag.w = tag.offsetWidth; tag.h = tag.offsetHeight; }`;
- in `update()`: use `const centre = anchor ?? { x: 0, y: 0, h: 0, base: 0 };` for the far-badge centre (`project(centre.x, centre.y, 0)`), place the tag only `if (tag)`, and build `fixed` only when there is a tag:

```js
    const fixed = [];
    if (tag) {
      const top = project(anchor.x, anchor.y, anchor.h);
      place(tag, top.x, top.y, 'translate(-50%, -100%)');
      const pinBottom = project(anchor.x, anchor.y, 0).y;
      fixed.push({ x: top.x, y: (top.y - tag.h + pinBottom) / 2, w: Math.max(tag.w, 44), h: pinBottom - top.y + tag.h });
    }
```

(remove the old unconditional `top` / `place(tag…)` lines at the start of `update`.)

`frontend/src/map/stage.js`:

```js
import { detailFor } from './detail.js';
import { addStreetFocus } from './focus.js';
import { tierLabel } from '../format.js';
```

Inside `createStage`, right after `const r = scene.radius_m;`:

```js
  const detail = detailFor(scene.tier);
```

- `sun.shadow.mapSize.set(detail.shadowMap, detail.shadowMap);`
- `addGround(world, scene, mat, { lanes: detail.lanes });`
- `const trees = addTrees(world, scene, mat, { seeded: detail.seededTrees });`
- `const cars = addCars(world, scene.roads, mat, mulberry32(seed + 1), detail.maxCars);`
- `if (detail.decor) addDecor(world, scene, mat);`
- `const people = addPedestrians(world, scene.roads, mat, mulberry32(seed + 2), detail.people);`
- `const bikes = addCyclists(world, scene.roads, mat, mulberry32(seed + 3), detail.people);`
- pigeons and groups only with `detail.pigeons`:

```js
  const idle = { update() {} };
  const groups = detail.pigeons ? addChatGroups(world, spots.slice(1), mat, mulberry32(seed + 5)) : idle;
  const pigeons = detail.pigeons ? addPigeons(world, spots[0] ?? null, r, mat, mulberry32(seed + 6)) : idle;
```

- the focus / property layer and the tag info:

```js
  const focus = detail.property ? addProperty(world, scene, mat)
    : detail.streetFocus ? addStreetFocus(world, scene.focus, mat)
      : { update() {}, anchor: null };
  const tagInfo = detail.streetFocus
    ? { title: `Na predaj · ${tierLabel('street')} ${scene.focus?.name ?? ''}`.trim(), lines: ['Presná adresa nie je uvedená'] }
    : null;
```

- rename the old `property` variable to `focus` everywhere (`focus.update(t)` in `frame`, `focus.anchor` for the overlay):

```js
  const overlay = createOverlay(container, scene, project, focus.anchor, hover.onLabel, tagInfo);
```

- [ ] **Step 4: Run tests and check the running app**

Run: `cd frontend && npm test` → all pass.
Browser: the plain Pezinok URL looks exactly as before (address tier).
`http://localhost:5173/?lat=48.2895&lon=17.2696&tier=street&name=Z%C3%A1hradn%C3%A1` → a wider map, a red band along Záhradná, "Na predaj" on the street, no pin, no benches, fewer people.
`http://localhost:5173/?lat=48.2877&lon=17.2667&tier=city` → the 450 m map without tag, people or lane markings; landmark labels near the centre. Note both cold load times.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): tier rendering — detail switches, street highlight, tag on the street" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ks8oBdDjJanB3ngMLhZ38E"
```

---

### Task 10: Search UI — form, messages, stage swapping, load time

**Files:**
- Modify: `frontend/index.html`, `frontend/src/style.css`, `frontend/src/main.js`

**Interfaces:**
- Consumes: `getViewFromURL`, `viewToSearch`, `sceneUrl`, `DEFAULT_COORDS`, `isFixture` (url.js); `formatLoadTime`, `tierLabel` (format.js); `createRequestGate` (requestGate.js); `createStage(container, scene) -> {dispose()}` (Task 8).

- [ ] **Step 1: Markup** — replace the `<body>` of `frontend/index.html`:

```html
<body>
  <main class="gm-page">
    <form id="search" class="gm-search" role="search">
      <input id="q" name="q" type="search" autocomplete="off" required minlength="2"
             placeholder="Zadajte mesto, ulicu alebo adresu" aria-label="Hľadať miesto" />
      <button type="submit">Hľadať</button>
    </form>
    <p id="search-msg" class="gm-search-msg" role="alert" hidden></p>
    <div id="map" class="gm-map">
      <div id="status" class="gm-status" role="status">
        <div class="gm-slab"></div>
        <p id="status-text">Načítavam okolie…</p>
        <button id="retry" type="button" hidden>Skúsiť znova</button>
      </div>
    </div>
    <p id="timing" class="gm-timing" hidden></p>
  </main>
  <script type="module" src="/src/main.js"></script>
</body>
```

- [ ] **Step 2: Styles** — in `frontend/src/style.css` replace the `body { … display: grid; place-items: center; }` rule and remove `margin-inline: auto` / `max-width` from `.gm-map` (the page wrapper owns the width now); add:

```css
body { box-sizing: border-box; min-height: 100vh; padding: 16px; display: grid; place-items: center; }
.gm-page { width: 100%; max-width: 874px; display: grid; gap: 10px; }
.gm-map { max-width: none; }

.gm-search { display: flex; gap: 8px; }
.gm-search input {
  flex: 1; min-width: 0; font: inherit; font-size: 15px; color: #1E2A2F;
  padding: 10px 16px; border: 1px solid #D5DEE3; border-radius: 999px; background: #fff;
  box-shadow: 0 2px 8px rgba(30, 42, 47, 0.06);
}
.gm-search input:focus-visible { outline: 3px solid rgba(255, 90, 95, 0.35); border-color: #FF5A5F; }
.gm-search button {
  font: inherit; font-weight: 600; color: #fff; background: #FF5A5F;
  border: 0; border-radius: 999px; padding: 10px 20px; cursor: pointer;
}
.gm-search button:focus-visible { outline: 3px solid #1E2A2F; outline-offset: 2px; }
.gm-search-msg { margin: 0; font-size: 13px; color: #B23A3E; }
.gm-timing { margin: 0; text-align: right; font-size: 12px; color: #7A868C; font-variant-numeric: tabular-nums; }
```

- [ ] **Step 3: Controller** — replace `frontend/src/main.js`:

```js
import './style.css';
import { formatLoadTime, tierLabel } from './format.js';
import { createStage } from './map/stage.js';
import { createRequestGate } from './requestGate.js';
import { DEFAULT_COORDS, getViewFromURL, isFixture, sceneUrl, viewToSearch } from './url.js';

const mapEl = document.getElementById('map');
const statusEl = document.getElementById('status');
const statusText = document.getElementById('status-text');
const retryBtn = document.getElementById('retry');
const form = document.getElementById('search');
const input = document.getElementById('q');
const searchMsg = document.getElementById('search-msg');
const timingEl = document.getElementById('timing');

const NOT_FOUND = (q) => `Nenašli sme „${q}“. Skúste pridať mesto alebo PSČ.`;
const GEOCODE_DOWN = 'Vyhľadávanie je dočasne nedostupné, skúste o chvíľu.';
const LOAD_FAILED = 'Mapu sa nepodarilo načítať. Skúste to znova o chvíľu.';
const CITY_HINT = ' Mestská úroveň je náročnejšia – skúste konkrétnu ulicu.';
const LOADING = { address: 'Načítavam okolie', street: 'Načítavam ulicu', city: 'Načítavam mesto' };

const gate = createRequestGate();
let controller = null;
let stage = null;
let current = null;

function defaultView() {
  return { ...DEFAULT_COORDS, tier: 'address', name: null, label: null };
}

function beginRequest() {
  controller?.abort();
  controller = new AbortController();
  return { token: gate.next(), signal: controller.signal };
}

function showStatus(text, isError) {
  statusEl.hidden = false;
  statusEl.classList.toggle('is-error', isError);
  statusText.textContent = text;
  retryBtn.hidden = !isError;
}

async function showView(view, startedAt = performance.now()) {
  current = view;
  const { token, signal } = beginRequest();
  showStatus(`${LOADING[view.tier]}${view.label ? ` ${view.label}` : ''}…`, false);
  try {
    const res = await fetch(sceneUrl(view, isFixture(window.location.search)), { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const scene = await res.json();
    if (!gate.isCurrent(token)) return;
    if (view.label) scene.address = `${view.label} · ${tierLabel(view.tier)}`;
    stage?.dispose();
    stage = createStage(mapEl, scene);
    statusEl.hidden = true;
    timingEl.textContent = formatLoadTime(performance.now() - startedAt, scene.cached === true);
    timingEl.hidden = false;
  } catch (err) {
    if (err.name === 'AbortError' || !gate.isCurrent(token)) return;
    console.error('hoodiemap: scene load failed', err);
    showStatus(LOAD_FAILED + (view.tier === 'city' ? CITY_HINT : ''), true);
  }
}

function showSearchMsg(text) {
  searchMsg.textContent = text;
  searchMsg.hidden = false;
}

async function search(q) {
  const startedAt = performance.now();
  const { token, signal } = beginRequest();
  searchMsg.hidden = true;
  let hit;
  try {
    const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`, { signal });
    if (!gate.isCurrent(token)) return;
    if (!res.ok) {
      showSearchMsg(res.status === 404 ? NOT_FOUND(q) : GEOCODE_DOWN);
      return;
    }
    hit = await res.json();
  } catch (err) {
    if (err.name !== 'AbortError' && gate.isCurrent(token)) showSearchMsg(GEOCODE_DOWN);
    return;
  }
  const view = { lat: hit.lat, lon: hit.lon, tier: hit.tier, name: hit.name || null, label: hit.label || null };
  history.pushState(null, '', viewToSearch(view));
  await showView(view, startedAt);
}

form.addEventListener('submit', (e) => {
  e.preventDefault();
  const q = input.value.trim();
  if (q.length >= 2) search(q);
});
retryBtn.addEventListener('click', () => showView(current ?? defaultView()));
window.addEventListener('popstate', () => {
  const view = getViewFromURL(window.location.search) ?? defaultView();
  input.value = view.label ?? '';
  showView(view);
});

const initial = getViewFromURL(window.location.search) ?? defaultView();
input.value = initial.label ?? '';
showView(initial);
```

(Any non-404 failure — HTTP 503 or a network error — shows `GEOCODE_DOWN`; the previous map stays.)

- [ ] **Step 4: Verify in the browser**

With both servers running, open `http://localhost:5173/`:
1. Type `Záhradná 12, Pezinok` → Enter → address tier; the chip reads `Záhradná 12, Pezinok · adresa`; timing line appears.
2. `Záhradná, Pezinok` → street tier with the red band.
3. `Pezinok` → city tier.
4. `xyzqwv` → the not-found message; the previous map stays.
5. Type 3 queries quickly, pressing Enter after each → only the last one ends up on screen.
6. Browser Back → the previous view reloads.
7. Run 10 searches in a row, then check the console: no "Too many active WebGL contexts" warning and only one `<canvas>` inside `#map` (`document.querySelectorAll('#map canvas').length === 1`).

Run: `cd frontend && npm test && npx vite build` → pass / built.

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/src/style.css frontend/src/main.js
git commit -m "feat(frontend): search box — geocode, tier view, stage swapping, load time" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ks8oBdDjJanB3ngMLhZ38E"
```

---

### Task 11: Docs, fixture and the timing check

**Files:**
- Modify: `CLAUDE.md`, `fixtures/pezinok-centrum.json` (regenerated), `docs/superpowers/specs/2026-09-26-location-search-tiers-design.md` (two clarifications)
- Create: `scripts/time_tiers.py`

- [ ] **Step 1: Timing script** — `scripts/time_tiers.py`:

```python
"""Time geocode + scene for the five acceptance queries against a running backend (cold, then cached)."""
import sys
import time

import httpx

QUERIES = ["Záhradná 12, Pezinok", "Záhradná, Pezinok", "Pezinok", "Obchodná, Bratislava", "Staré Mesto, Bratislava"]
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def run(client: httpx.Client, q: str) -> str:
    t0 = time.perf_counter()
    hit = client.get(f"{BASE}/api/geocode", params={"q": q})
    if hit.status_code != 200:
        return f"{q:28} geocode {hit.status_code}"
    g = hit.json()
    params = {"lat": g["lat"], "lon": g["lon"], "tier": g["tier"]}
    if g["tier"] == "street":
        params["name"] = g["name"]
    scene = client.get(f"{BASE}/api/scene", params=params)
    total = time.perf_counter() - t0
    if scene.status_code != 200:
        return f"{q:28} {g['tier']:7} scene {scene.status_code} after {total:5.1f} s"
    s = scene.json()
    return (f"{q:28} {g['tier']:7} r={s['radius_m']:5.0f} m  buildings={len(s['buildings']):5}  "
            f"near={len(s['near_pois']):2} far={len(s['far_pois']):2}  total={total:5.1f} s  "
            f"backend={s['timing_ms'] / 1000:5.1f} s  cached={s['cached']}")


with httpx.Client(timeout=200) as client:
    for label in ("first run", "second run (cache)"):
        print(f"--- {label}")
        for q in QUERIES:
            print(run(client, q), flush=True)
```

- [ ] **Step 2: Run it and record the numbers**

Run: `.venv/bin/python scripts/time_tiers.py`
Expected: every line has a tier and `cached=True` on the second run with totals under ~1.5 s; first-run totals for address/street under ~10 s. Record the full output — it goes into the final report / PR description. If the city tier's first run exceeds ~40 s or returns 502, say so in the report and propose lowering `radii.city_meters` (do not change it silently).

- [ ] **Step 3: Spec clarifications** — in the spec:
  - In section 3, replace "food, post, bank, doctors, playground (map-only icons) | ✓ | ✓ (6 nearest) | —" with "… | ✓ | ✓ | —" and add below the table: "Map-only icons are already limited to the nearest one per category (5 at most), so no extra cap is needed."
  - In section 4 "Street highlight", replace "slightly wider than the road (street width + 3 m)" with "14 m wide (about 4 m of band on each side of a street; tuned visually)".

- [ ] **Step 4: CLAUDE.md** — update:
  - Running: add `Search box: type a town, a street or a full address; the tier follows the match (see the spec).` and `Timing: .venv/bin/python scripts/time_tiers.py`.
  - Configuration block: the new `radii` keys and `geocode.countrycodes`.
  - Architecture: `geocode.py` (Nominatim best match → tier, 1 req/s, `.cache/geocode`), `street.py` (join a named street, frame the map), `map/detail.js`, `map/focus.js`, `requestGate.js`.
  - Pipeline: one paragraph on tiers — address ±140 m; street = the joined street, radius `clamp(L/2 + 60, 160, 300)`, distances to the street line, red band + tag; city ±450 m around the Nominatim point, light area query (no footways/trees, 60 s), POIs hospital/train/park/supermarket/bus_station/mall + up to 3 landmarks with Wikipedia/Wikidata; scene carries `tier`, `focus`, `timing_ms`, `cached`.
  - POI table: rows for `bus_station` (30 km, city tier), `mall` (15 km, city tier), `landmark` (the map square, city tier, ≤ 3, one per kind).

- [ ] **Step 5: Regenerate the fixture and run everything**

Run: `.venv/bin/python scripts/capture_fixture.py` (address tier; the fixture now carries `tier`, `focus`, `timing_ms`, `cached`), then `.venv/bin/python -m pytest -q` and `cd frontend && npm test && npx vite build` → all pass / built.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md fixtures/pezinok-centrum.json scripts/time_tiers.py docs/superpowers/specs/2026-09-26-location-search-tiers-design.md
git commit -m "docs: tiers in CLAUDE.md, timing script, fixture refresh" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Ks8oBdDjJanB3ngMLhZ38E"
```
