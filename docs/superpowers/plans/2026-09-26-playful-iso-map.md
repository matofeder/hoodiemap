# Playful Isometric Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dense realistic 3D city with a lightweight, playful pastel isometric widget showing ±140 m around a property, with far POIs hinted as edge badges.

**Architecture:** The backend fetches OSM data with two direct Overpass queries (`osm.py`, JSON file cache) and turns them into a compact scene JSON (`scene_builder.py`: clipping, building classification, property detection, nearest POI per category). The frontend is small ES modules: pure geometry/format helpers (unit-tested with vitest) plus Three.js layers (ground, buildings, trees, cars, property) and an HTML overlay for labels and edge badges.

**Tech Stack:** Python 3 · FastAPI · httpx · shapely 2 · pydantic 2 · pytest | Vite 5 · Three.js 0.168 · vitest 1.6

**Spec:** `docs/superpowers/specs/2026-09-26-playful-iso-map-design.md`

## Global Constraints

- Display square half-size: `radii.display_meters: 140`.
- Overpass `User-Agent: genmap/1.0 (neighbourhood-map)`. Endpoints in order: overpass-api.de, overpass.kumi.systems, maps.mail.ru. Timeout 25 s each.
- Cache: `<cache.dir>/osm/<sha256(query)[:16]>.json`, TTL 30 days.
- POI categories and search radii: hospital 30 km, supermarket 5 km, school 5 km, kindergarten 5 km, pharmacy 5 km, bus_stop 3 km, train 30 km, park 3 km. Only the nearest POI per category is kept.
- Local coords: metres, x east, y north. Backend (x, y) → Three (x, 0, −y).
- Distance format: `"350 m"` below 1 km, `"2,4 km"` below 10 km, `"25 km"` at or above 10 km.
- Slovak UI copy: "Na predaj", "Načítavam okolie…", "Mapu sa nepodarilo načítať. Skúste to znova o chvíľu.", "Skúsiť znova".
- Palette values are exactly as in spec §2 (see `palette.js` in Task 6).
- Python tests run with `.venv/bin/python -m pytest` from the repo root. Frontend tests run with `npm test` in `frontend/`.

## Review Focus

1. **Rural or empty location** (no buildings or roads in OSM): the scene must still render a slab with the pin at the center and no crash. Tested in Task 4 (`test_empty_area_gives_valid_scene`) and Task 6 (`planCars([])`, `seedTreePositions` on an empty scene).
2. **POI without a name**, or with a very long name: the badge shows the category label. Tested in Task 6 (`poiTitle`).
3. **Degenerate OSM geometry** (unclosed building way, < 4 points, self-intersecting ring): skipped or repaired, never raised. Tested in Task 4.
4. **Several far POIs in nearly the same direction**: badges must not overlap and must stay inside the widget. Tested in Task 6 (three badges at the same point).
5. **Narrow widget (320 px wide)**: badges clamp inside bounds. Tested in Task 6 (`edgePoint` with W=320).

---

## File Structure

**Backend (`src/`)**
- `config.py`: modify. New POI categories, `display_meters` 140, remove output/fetch settings.
- `geo.py`: rewrite (track it; currently untracked). Haversine, bearing, local projection, bbox.
- `osm.py`: create. Overpass queries, endpoint fallback, cache, POI categorization.
- `scene_builder.py`: rewrite. Classification rules, geometry assembly, property, POI split.
- `api.py`: modify. Trim endpoints, 502 handling, reverse-geocode helper.
- Delete: `fetcher.py`, `renderer.py`, `genmap.py`, `styles.py`.

**Frontend (`frontend/src/`)**
- Pure, unit-tested: `format.js`, `random.js`, `url.js`, `palette.js`, `map/geom.js`, `map/lines.js`, `map/roofs.js`, `map/placement.js`, `overlay/edge.js`.
- Three.js / DOM: `map/materials.js`, `map/stage.js`, `map/ground.js`, `map/buildings.js`, `map/trees.js`, `map/cars.js`, `map/property.js`, `overlay/labels.js`, `icons.js`, `main.js`, `style.css`, `index.html`.
- Delete: `animations.js`, `frame.js`, `frame.test.js`, `infographic.js`, `poi.js`, `route.js`, `ui.js`, `colors.js`, `geometry.js`, `geometry.test.js`, `scene.js`, `main.test.js`.

---

### Task 1: Branch, config and geo helpers

**Files:**
- Modify: `src/config.py`, `config.yaml`, `requirements.txt`, `tests/conftest.py`
- Create/replace: `src/geo.py`, `tests/test_config.py`, `tests/test_geo.py`

**Interfaces:**
- Produces: `Config.poi.enabled() -> list[str]` (category names in order hospital, supermarket, school, kindergarten, pharmacy, bus_stop, train, park); `cfg.radii.display_meters: float`; `geo.haversine_m(lat1, lon1, lat2, lon2) -> float`; `geo.compute_bearing(lat1, lon1, lat2, lon2) -> float` (0–360, 0 = north); `geo.to_local(lat, lon, lat0, lon0) -> (x, y)`; `geo.from_local(x, y, lat0, lon0) -> (lat, lon)`; `geo.square_bbox(lat0, lon0, half_m) -> (south, west, north, east)`.

- [ ] **Step 1: Create the feature branch and preserve legacy untracked files in history**

```bash
git checkout -b feat/playful-iso-map
git add src/renderer.py src/genmap.py src/styles.py src/geo.py
git commit -m "chore: track legacy renderer files before removal"
```

- [ ] **Step 2: Write failing tests**

`tests/test_config.py`:
```python
from pathlib import Path

from config import PoiConfig, PoiShowConfig, load_config

ALL = ["hospital", "supermarket", "school", "kindergarten", "pharmacy", "bus_stop", "train", "park"]


def test_default_enables_all_eight_categories():
    assert PoiConfig().enabled() == ALL


def test_enabled_lists_only_true_categories():
    show = PoiShowConfig(**{name: name in ("hospital", "pharmacy") for name in ALL})
    assert PoiConfig(show=show).enabled() == ["hospital", "pharmacy"]


def test_repo_config_loads():
    cfg = load_config(Path(__file__).parent.parent / "config.yaml")
    assert cfg.radii.display_meters == 140
    assert cfg.poi.enabled() == ALL
```

`tests/test_geo.py`:
```python
import math

import pytest

from geo import compute_bearing, from_local, haversine_m, square_bbox, to_local

LAT0, LON0 = 48.28646, 17.27221


@pytest.mark.parametrize("x,y", [(140, 0), (0, 140), (-140, -140), (99, -37)])
def test_local_projection_matches_haversine(x, y):
    lat, lon = from_local(x, y, LAT0, LON0)
    assert haversine_m(LAT0, LON0, lat, lon) == pytest.approx(math.hypot(x, y), abs=0.5)


def test_roundtrip():
    lat, lon = from_local(12.3, -45.6, LAT0, LON0)
    x, y = to_local(lat, lon, LAT0, LON0)
    assert x == pytest.approx(12.3, abs=1e-6)
    assert y == pytest.approx(-45.6, abs=1e-6)


def test_bearing_north_and_east():
    lat, lon = from_local(0, 1000, LAT0, LON0)
    assert compute_bearing(LAT0, LON0, lat, lon) == pytest.approx(0, abs=0.5)
    lat, lon = from_local(1000, 0, LAT0, LON0)
    assert compute_bearing(LAT0, LON0, lat, lon) == pytest.approx(90, abs=0.5)


def test_square_bbox():
    s, w, n, e = square_bbox(LAT0, LON0, 160)
    assert s < LAT0 < n and w < LON0 < e
    assert haversine_m(s, LON0, n, LON0) == pytest.approx(320, abs=0.5)
```

`tests/conftest.py` (replace the fixture):
```python
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def default_config(tmp_path):
    from config import CacheConfig, Config, LocationConfig, RadiiConfig
    return Config(
        location=LocationConfig(lat=48.28646, lon=17.27221),
        radii=RadiiConfig(display_meters=140),
        cache=CacheConfig(enabled=False, dir=str(tmp_path / "cache")),
    )
```

- [ ] **Step 3: Run tests, expect failure**

Run: `.venv/bin/python -m pytest tests/test_config.py tests/test_geo.py -v`
Expected: FAIL (`enabled` missing, `from_local` missing).

- [ ] **Step 4: Implement**

`src/config.py`:
```python
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class LocationConfig(BaseModel):
    lat: float
    lon: float


class RadiiConfig(BaseModel):
    display_meters: float = 140.0


class PoiShowConfig(BaseModel):
    hospital: bool = True
    supermarket: bool = True
    school: bool = True
    kindergarten: bool = True
    pharmacy: bool = True
    bus_stop: bool = True
    train: bool = True
    park: bool = True


class PoiConfig(BaseModel):
    show: PoiShowConfig = Field(default_factory=PoiShowConfig)

    def enabled(self) -> list[str]:
        return [name for name, on in self.show.model_dump().items() if on]


class CacheConfig(BaseModel):
    enabled: bool = True
    dir: str = ".cache"


class ApiConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class Config(BaseModel):
    location: LocationConfig
    radii: RadiiConfig = Field(default_factory=RadiiConfig)
    poi: PoiConfig = Field(default_factory=PoiConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)


def load_config(path: str | Path = "config.yaml") -> Config:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Config.model_validate(data)
```

`src/geo.py`:
```python
import math

EARTH_RADIUS_M = 6_371_000.0
M_PER_DEG = math.pi * EARTH_RADIUS_M / 180.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def compute_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def to_local(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    """Equirectangular projection around (lat0, lon0) in metres: x east, y north."""
    x = (lon - lon0) * math.cos(math.radians(lat0)) * M_PER_DEG
    y = (lat - lat0) * M_PER_DEG
    return x, y


def from_local(x: float, y: float, lat0: float, lon0: float) -> tuple[float, float]:
    lat = lat0 + y / M_PER_DEG
    lon = lon0 + x / (math.cos(math.radians(lat0)) * M_PER_DEG)
    return lat, lon


def square_bbox(lat0: float, lon0: float, half_m: float) -> tuple[float, float, float, float]:
    """(south, west, north, east) of a square with half-size half_m around the center."""
    south, west = from_local(-half_m, -half_m, lat0, lon0)
    north, east = from_local(half_m, half_m, lat0, lon0)
    return south, west, north, east
```

`config.yaml`:
```yaml
location:
  lat: 48.28646434486518
  lon: 17.27221245956356

radii:
  display_meters: 140      # half-size of the visible square around the property

poi:
  show:
    hospital: true
    supermarket: true
    school: true
    kindergarten: true
    pharmacy: true
    bus_stop: true
    train: true
    park: true

cache:
  enabled: true
  dir: .cache

api:
  host: "0.0.0.0"
  port: 8000
```

`requirements.txt`:
```
shapely>=2.0
pydantic>=2.0
PyYAML>=6.0
fastapi>=0.111
uvicorn[standard]>=0.29
httpx>=0.27
pytest>=8.0
pytest-asyncio>=0.23
```

- [ ] **Step 5: Run tests, expect pass**

Run: `.venv/bin/python -m pytest tests/test_config.py tests/test_geo.py -v`
Expected: all PASS. (Other test files may fail until later tasks replace them; only run these two.)

- [ ] **Step 6: Commit**

```bash
git add src/config.py src/geo.py config.yaml requirements.txt tests/conftest.py tests/test_config.py tests/test_geo.py
git commit -m "feat: new POI categories, 140 m display radius, local projection helpers"
```

---

### Task 2: Overpass client with fallback and cache (`osm.py`)

**Files:**
- Create: `src/osm.py`, `tests/test_osm.py`

**Interfaces:**
- Consumes: `geo.square_bbox`.
- Produces: `osm.OverpassError`; `osm.ENDPOINTS: list[str]`; `osm.USER_AGENT: str`; `osm.CACHE_TTL_S: int`; `osm.build_area_query(south, west, north, east) -> str`; `osm.build_poi_query(lat, lon, categories) -> str`; `osm.run_query(query, cache_dir: str | None, transport=None) -> dict`; `osm.fetch_area(lat, lon, half_m, cache_dir) -> dict`; `osm.fetch_pois(lat, lon, categories, cache_dir) -> dict`; `osm.categorize_poi(tags: dict) -> str | None`; `osm._cache_file(query, cache_dir) -> Path`.

- [ ] **Step 1: Write failing tests** in `tests/test_osm.py`

```python
import time

import httpx
import pytest

import osm
from osm import OverpassError, build_area_query, build_poi_query, categorize_poi, run_query


def _transport(responses, calls):
    def handler(request):
        calls.append(str(request.url))
        status, body = responses[len(calls) - 1]
        if isinstance(body, dict):
            return httpx.Response(status, json=body)
        return httpx.Response(status, text=body)
    return httpx.MockTransport(handler)


def test_area_query_contains_bbox_and_layers():
    q = build_area_query(48.1, 17.1, 48.2, 17.2)
    assert "(48.100000,17.100000,48.200000,17.200000)" in q
    for part in ['way["building"]', 'relation["building"]', 'way["highway"]', 'node["natural"="tree"]',
                 '"leisure"~"^(park|garden|playground)$"', '"natural"~"^(water|wood)$"', '"waterway"="riverbank"']:
        assert part in q
    assert q.rstrip().endswith("out geom;")


def test_poi_query_only_enabled_categories_with_radii():
    q = build_poi_query(48.0, 17.0, ["hospital", "pharmacy"])
    assert 'nwr["amenity"="hospital"](around:30000,48.000000,17.000000);' in q
    assert 'nwr["amenity"="pharmacy"](around:5000,48.000000,17.000000);' in q
    assert "supermarket" not in q
    assert q.rstrip().endswith("out center tags;")


def test_falls_back_to_next_endpoint_on_406():
    calls = []
    t = _transport([(406, "Not Acceptable"), (200, {"elements": [1]})], calls)
    assert run_query("q", cache_dir=None, transport=t) == {"elements": [1]}
    assert calls[0].startswith(osm.ENDPOINTS[0])
    assert calls[1].startswith(osm.ENDPOINTS[1])


def test_timeout_falls_back():
    n = {"i": 0}

    def handler(request):
        n["i"] += 1
        if n["i"] == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"elements": [3]})

    assert run_query("q", None, transport=httpx.MockTransport(handler)) == {"elements": [3]}


def test_sends_user_agent():
    seen = {}

    def handler(request):
        seen["ua"] = request.headers["user-agent"]
        return httpx.Response(200, json={"elements": []})

    run_query("q", None, transport=httpx.MockTransport(handler))
    assert seen["ua"] == osm.USER_AGENT


def test_raises_when_all_endpoints_fail():
    calls = []
    t = _transport([(429, "busy")] * len(osm.ENDPOINTS), calls)
    with pytest.raises(OverpassError):
        run_query("q", None, transport=t)
    assert len(calls) == len(osm.ENDPOINTS)


def test_runtime_error_remark_counts_as_failure():
    calls = []
    t = _transport([(200, {"remark": "runtime error: Query timed out", "elements": []}),
                    (200, {"elements": [2]})], calls)
    assert run_query("q", None, transport=t) == {"elements": [2]}


def test_cache_hit_skips_network(tmp_path):
    calls = []
    t = _transport([(200, {"elements": [4]})], calls)
    run_query("q", str(tmp_path), transport=t)
    assert run_query("q", str(tmp_path), transport=t) == {"elements": [4]}
    assert len(calls) == 1


def test_cache_expires(tmp_path, monkeypatch):
    calls = []
    t = _transport([(200, {"elements": [5]}), (200, {"elements": [6]})], calls)
    run_query("q", str(tmp_path), transport=t)
    later = time.time() + osm.CACHE_TTL_S + 1
    monkeypatch.setattr(osm.time, "time", lambda: later)
    assert run_query("q", str(tmp_path), transport=t) == {"elements": [6]}


def test_corrupt_cache_is_ignored(tmp_path):
    p = osm._cache_file("q", str(tmp_path))
    p.parent.mkdir(parents=True)
    p.write_text("{not json", encoding="utf-8")
    t = _transport([(200, {"elements": [7]})], [])
    assert run_query("q", str(tmp_path), transport=t) == {"elements": [7]}


def test_cache_disabled_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_query("q", None, transport=_transport([(200, {"elements": []})], []))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "hospital"}, "hospital"),
    ({"shop": "supermarket"}, "supermarket"),
    ({"amenity": "school"}, "school"),
    ({"amenity": "kindergarten"}, "kindergarten"),
    ({"amenity": "pharmacy"}, "pharmacy"),
    ({"highway": "bus_stop"}, "bus_stop"),
    ({"railway": "station"}, "train"),
    ({"railway": "halt"}, "train"),
    ({"leisure": "park"}, "park"),
    ({"leisure": "playground"}, "park"),
    ({"amenity": "bar"}, None),
    ({}, None),
])
def test_categorize_poi(tags, expected):
    assert categorize_poi(tags) == expected
```

- [ ] **Step 2: Run, expect failure**

Run: `.venv/bin/python -m pytest tests/test_osm.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'osm'`.

- [ ] **Step 3: Implement `src/osm.py`**

```python
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
```

- [ ] **Step 4: Run, expect pass**

Run: `.venv/bin/python -m pytest tests/test_osm.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/osm.py tests/test_osm.py
git commit -m "feat: osm.py — direct Overpass client with User-Agent, endpoint fallback and JSON cache"
```

---

### Task 3: Classification rules (`scene_builder.py`, part 1)

**Files:**
- Create (replacing old content): `src/scene_builder.py`
- Create: `tests/test_rules.py`
- Delete: `tests/test_scene_builder.py` (old pipeline tests)

**Interfaces:**
- Produces: `classify_building(tags: dict, area_m2: float) -> str` (house|apartment|commercial|civic|other); `building_height(tags: dict, kind: str) -> float`; `road_kind(highway) -> str | None` (main|street|path); `area_layer(tags) -> str | None` (park|water|forest).

- [ ] **Step 1: Write failing tests** in `tests/test_rules.py`

```python
import pytest

from scene_builder import area_layer, building_height, classify_building, road_kind


@pytest.mark.parametrize("tags,area,kind", [
    ({"building": "school"}, 800, "civic"),
    ({"building": "church"}, 300, "civic"),
    ({"building": "retail"}, 500, "commercial"),
    ({"building": "industrial"}, 900, "commercial"),
    ({"building": "garage"}, 20, "other"),
    ({"building": "shed"}, 8, "other"),
    ({"building": "house"}, 400, "house"),
    ({"building": "detached"}, 120, "house"),
    ({"building": "yes"}, 120, "house"),
    ({"building": "residential", "building:levels": "2"}, 180, "house"),
    ({"building": "yes", "building:levels": "3"}, 120, "apartment"),
    ({"building": "yes"}, 260, "apartment"),
    ({"building": "apartments"}, 100, "apartment"),
    ({"building": "YES"}, 100, "house"),
])
def test_classify_building(tags, area, kind):
    assert classify_building(tags, area) == kind


@pytest.mark.parametrize("tags,kind,height", [
    ({"height": "12 m"}, "apartment", 12.0),
    ({"height": "1"}, "other", 2.0),
    ({"building:levels": "4"}, "apartment", 12.0),
    ({"height": "abc", "building:levels": "2"}, "house", 6.0),
    ({}, "house", 6.0),
    ({}, "apartment", 12.0),
    ({}, "commercial", 8.0),
    ({}, "civic", 10.0),
    ({}, "other", 3.0),
])
def test_building_height(tags, kind, height):
    assert building_height(tags, kind) == height


@pytest.mark.parametrize("highway,kind", [
    ("primary", "main"), ("tertiary_link", "main"), ("residential", "street"),
    ("service", "street"), ("footway", "path"), ("steps", "path"),
    ("construction", None), ("proposed", None),
])
def test_road_kind(highway, kind):
    assert road_kind(highway) == kind


@pytest.mark.parametrize("tags,layer", [
    ({"leisure": "park"}, "park"), ({"leisure": "playground"}, "park"), ({"landuse": "grass"}, "park"),
    ({"natural": "water"}, "water"), ({"waterway": "riverbank"}, "water"),
    ({"landuse": "forest"}, "forest"), ({"natural": "wood"}, "forest"),
    ({"landuse": "residential"}, None),
])
def test_area_layer(tags, layer):
    assert area_layer(tags) == layer
```

- [ ] **Step 2: Run, expect failure**

Run: `git rm -q tests/test_scene_builder.py && .venv/bin/python -m pytest tests/test_rules.py -v`
Expected: FAIL (ImportError on `classify_building`).

- [ ] **Step 3: Implement.** Replace `src/scene_builder.py` entirely with the rules part:

```python
"""Turn raw Overpass JSON into the compact scene consumed by the frontend."""
import logging

logger = logging.getLogger(__name__)

CIVIC = frozenset({"school", "kindergarten", "church", "chapel", "hospital", "public", "civic",
                   "government", "train_station"})
COMMERCIAL = frozenset({"retail", "commercial", "office", "supermarket", "industrial", "warehouse", "hotel"})
OTHER = frozenset({"garage", "garages", "shed", "roof", "carport", "hut", "service"})
HOUSE = frozenset({"house", "detached", "semidetached_house", "terrace", "bungalow"})
HOUSE_MAX_AREA_M2 = 250
HOUSE_MAX_LEVELS = 2
DEFAULT_HEIGHT = {"house": 6.0, "apartment": 12.0, "commercial": 8.0, "civic": 10.0, "other": 3.0}
METERS_PER_LEVEL = 3.0

ROAD_KINDS: dict[str, str] = {
    **dict.fromkeys(["primary", "secondary", "tertiary", "primary_link", "secondary_link", "tertiary_link"], "main"),
    **dict.fromkeys(["residential", "unclassified", "living_street", "service", "road"], "street"),
    **dict.fromkeys(["footway", "path", "cycleway", "pedestrian", "steps", "track"], "path"),
}
PARK_LEISURE = frozenset({"park", "garden", "playground"})
PARK_LANDUSE = frozenset({"grass", "meadow", "recreation_ground", "village_green"})


def _num(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).lower().replace("m", "").replace(",", ".").strip())
    except ValueError:
        return None


def classify_building(tags: dict, area_m2: float) -> str:
    b = str(tags.get("building", "yes")).lower()
    if b in CIVIC:
        return "civic"
    if b in COMMERCIAL:
        return "commercial"
    if b in OTHER:
        return "other"
    if b in HOUSE:
        return "house"
    levels = _num(tags.get("building:levels"))
    small = area_m2 < HOUSE_MAX_AREA_M2 and (levels is None or levels <= HOUSE_MAX_LEVELS)
    if b in ("yes", "residential") and small:
        return "house"
    return "apartment"


def building_height(tags: dict, kind: str) -> float:
    height = _num(tags.get("height"))
    if height is not None and height > 0:
        return max(2.0, height)
    levels = _num(tags.get("building:levels"))
    if levels is not None and levels > 0:
        return levels * METERS_PER_LEVEL
    return DEFAULT_HEIGHT[kind]


def road_kind(highway) -> str | None:
    return ROAD_KINDS.get(str(highway))


def area_layer(tags: dict) -> str | None:
    if tags.get("natural") == "water" or tags.get("waterway") == "riverbank":
        return "water"
    if tags.get("landuse") == "forest" or tags.get("natural") == "wood":
        return "forest"
    if tags.get("leisure") in PARK_LEISURE or tags.get("landuse") in PARK_LANDUSE:
        return "park"
    return None
```

- [ ] **Step 4: Run, expect pass**

Run: `.venv/bin/python -m pytest tests/test_rules.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/scene_builder.py tests/test_rules.py tests/test_scene_builder.py
git commit -m "feat: building, road and area classification rules"
```

---

### Task 4: Scene assembly — geometry, property, POIs (`scene_builder.py`, part 2)

**Files:**
- Modify: `src/scene_builder.py` (append)
- Create: `tests/test_assemble.py`

**Interfaces:**
- Consumes: Task 2 `osm.fetch_area`, `osm.fetch_pois`, `osm.categorize_poi`, `osm.OverpassError`; Task 1 `geo.to_local`, `geo.haversine_m`, `geo.compute_bearing`, `Config.poi.enabled()`.
- Produces: `assemble_scene(lat, lon, radius_m, area: dict, pois_raw: dict, categories: list[str]) -> dict` (keys: center, radius_m, buildings, property, roads, areas, trees, near_pois, far_pois); `find_property(buildings) -> int | None`; `split_pois(lat, lon, radius_m, pois_raw, categories) -> (near, far)`; `build_scene(lat, lon, cfg) -> dict` (the above + `warnings`).

- [ ] **Step 1: Write failing tests** in `tests/test_assemble.py`

```python
import pytest

import scene_builder
from geo import from_local
from osm import OverpassError
from scene_builder import assemble_scene, build_scene, find_property, split_pois

LAT0, LON0 = 48.28646, 17.27221
R = 140
CATS = ["hospital", "supermarket", "school", "kindergarten", "pharmacy", "bus_stop", "train", "park"]


def ll(x, y):
    lat, lon = from_local(x, y, LAT0, LON0)
    return {"lat": lat, "lon": lon}


def way(pts, tags, closed=True, id=1):
    geom = [ll(*p) for p in pts]
    if closed:
        geom.append(geom[0])
    return {"type": "way", "id": id, "tags": tags, "geometry": geom}


def node(x, y, tags, id=1):
    return {"type": "node", "id": id, **ll(x, y), "tags": tags}


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def scene(elements, pois=()):
    return assemble_scene(LAT0, LON0, R, {"elements": list(elements)}, {"elements": list(pois)}, CATS)


def test_building_inside_is_kept_with_open_ring():
    s = scene([way(rect(10, 10, 30, 20), {"building": "house"})])
    b = s["buildings"][0]
    assert b["kind"] == "house" and b["height"] == 6.0
    assert len(b["footprint"]) == 4
    assert [10.0, 10.0] in b["footprint"]


def test_building_half_outside_is_clipped():
    s = scene([way(rect(130, 0, 150, 10), {"building": "yes"})])
    xs = [p[0] for p in s["buildings"][0]["footprint"]]
    assert max(xs) == pytest.approx(140, abs=0.1)


def test_mostly_outside_building_is_dropped():
    s = scene([way(rect(134, 0, 154, 10), {"building": "yes"})])
    assert s["buildings"] == []


def test_unclosed_or_tiny_building_is_skipped():
    s = scene([
        way(rect(0, 0, 10, 10), {"building": "yes"}, closed=False),
        way([(0, 0), (1, 0), (0, 1)], {"building": "yes"}),
    ])
    assert s["buildings"] == []


def test_self_intersecting_building_is_repaired():
    bowtie = [(0, 0), (20, 20), (20, 0), (0, 20)]
    s = scene([way(bowtie, {"building": "yes"})])
    assert all(len(b["footprint"]) >= 3 for b in s["buildings"])


def test_relation_multipolygon_outer_members_are_joined():
    rel = {"type": "relation", "id": 9, "tags": {"natural": "water"}, "members": [
        {"type": "way", "role": "outer", "geometry": [ll(0, 0), ll(20, 0), ll(20, 20)]},
        {"type": "way", "role": "outer", "geometry": [ll(20, 20), ll(0, 20), ll(0, 0)]},
    ]}
    s = scene([rel])
    assert len(s["areas"]["water"]) == 1


def test_road_is_clipped_to_square_and_kind_mapped():
    s = scene([way([(-300, 5), (300, 5)], {"highway": "secondary"}, closed=False)])
    road = s["roads"][0]
    assert road["kind"] == "main"
    assert road["points"][0][0] == pytest.approx(-140, abs=0.1)
    assert road["points"][-1][0] == pytest.approx(140, abs=0.1)


def test_unknown_highway_is_dropped():
    s = scene([way([(0, 0), (50, 0)], {"highway": "construction"}, closed=False)])
    assert s["roads"] == []


def test_trees_outside_square_are_dropped():
    s = scene([node(10, 10, {"natural": "tree"}, 1), node(200, 0, {"natural": "tree"}, 2)])
    assert s["trees"] == [{"x": 10.0, "y": 10.0}]


def test_park_is_clipped():
    s = scene([way(rect(100, -20, 200, 20), {"leisure": "park"})])
    xs = [p[0] for p in s["areas"]["park"][0]]
    assert max(xs) == pytest.approx(140, abs=0.1)


def test_empty_area_gives_valid_scene():
    s = scene([])
    assert s["buildings"] == [] and s["roads"] == [] and s["trees"] == []
    assert s["property"] == {"building_index": None}
    assert s["areas"] == {"park": [], "water": [], "forest": []}
    assert s["radius_m"] == R


def test_find_property_containing_nearest_and_none():
    inside = {"footprint": [[-5, -5], [5, -5], [5, 5], [-5, 5]]}
    near = {"footprint": [[10, 0], [20, 0], [20, 10], [10, 10]]}
    far = {"footprint": [[50, 0], [60, 0], [60, 10], [50, 10]]}
    assert find_property([near, inside]) == 1
    assert find_property([far, near]) == 1
    assert find_property([far]) is None


def test_split_pois_nearest_per_category_and_near_far():
    pois = [
        node(30, 40, {"amenity": "pharmacy", "name": "Near"}, 1),
        node(60, 60, {"amenity": "pharmacy", "name": "Farther"}, 2),
        {"type": "way", "id": 3, "center": ll(0, 2400), "tags": {"amenity": "hospital", "name": "Nemocnica"}},
        node(0, 0, {"amenity": "bar"}, 4),
        {"type": "way", "id": 5, "tags": {"amenity": "school"}},
    ]
    near, far = split_pois(LAT0, LON0, R, {"elements": pois}, CATS)
    assert [p["name"] for p in near] == ["Near"]
    assert near[0]["x"] == 30.0 and near[0]["distance_m"] == 50
    assert far == [{"category": "hospital", "name": "Nemocnica", "distance_m": 2400, "bearing_deg": 0.0}]


def test_poi_near_edge_goes_to_far():
    near, far = split_pois(LAT0, LON0, R, {"elements": [node(135, 0, {"amenity": "pharmacy"})]}, CATS)
    assert near == [] and far[0]["bearing_deg"] == pytest.approx(90, abs=0.5)


def test_disabled_category_is_ignored():
    near, far = split_pois(LAT0, LON0, R, {"elements": [node(10, 10, {"amenity": "pharmacy"})]}, ["hospital"])
    assert near == [] and far == []


def test_build_scene_poi_failure_adds_warning(monkeypatch, default_config):
    monkeypatch.setattr(scene_builder, "fetch_area", lambda *a: {"elements": []})

    def boom(*a):
        raise OverpassError("down")

    monkeypatch.setattr(scene_builder, "fetch_pois", boom)
    s = build_scene(LAT0, LON0, default_config)
    assert s["warnings"] == ["poi_fetch_failed"]
    assert s["far_pois"] == []


def test_build_scene_area_failure_raises(monkeypatch, default_config):
    def boom(*a):
        raise OverpassError("down")

    monkeypatch.setattr(scene_builder, "fetch_area", boom)
    with pytest.raises(OverpassError):
        build_scene(LAT0, LON0, default_config)
```

- [ ] **Step 2: Run, expect failure**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -v`
Expected: FAIL (ImportError on `assemble_scene`).

- [ ] **Step 3: Implement.** In `src/scene_builder.py` add imports at the top (below `import logging`):

```python
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import polygonize

from config import Config
from geo import compute_bearing, haversine_m, to_local
from osm import OverpassError, categorize_poi, fetch_area, fetch_pois
```

Append to the end of the file:

```python
MIN_KEEP_RATIO = 0.4
MIN_BUILDING_AREA_M2 = 4.0
PROPERTY_MAX_DIST_M = 15.0
NEAR_INSET_M = 10.0


def _r(v: float) -> float:
    return round(v, 1)


def _coords(geometry, lat0: float, lon0: float) -> list[tuple[float, float]]:
    return [to_local(p["lat"], p["lon"], lat0, lon0) for p in geometry or [] if p]


def _parts(geom, geom_type: str) -> list:
    if geom.is_empty:
        return []
    if geom.geom_type == geom_type:
        return [geom]
    return [p for sub in getattr(geom, "geoms", []) for p in _parts(sub, geom_type)]


def _polygons(el: dict, lat0: float, lon0: float) -> list[Polygon]:
    if el.get("type") == "way":
        pts = _coords(el.get("geometry"), lat0, lon0)
        if len(pts) < 4 or pts[0] != pts[-1]:
            return []
        raw = [Polygon(pts)]
    elif el.get("type") == "relation":
        lines = [LineString(_coords(m["geometry"], lat0, lon0)) for m in el.get("members", [])
                 if m.get("role") == "outer" and len(m.get("geometry") or []) >= 2]
        raw = list(polygonize(lines))
    else:
        return []
    out = []
    for poly in raw:
        fixed = poly if poly.is_valid else poly.buffer(0)
        out.extend(_parts(fixed, "Polygon"))
    return out


def _ring(poly: Polygon) -> list[list[float]]:
    return [[_r(x), _r(y)] for x, y in list(poly.exterior.coords)[:-1]]


def _building(poly: Polygon, tags: dict, square) -> dict | None:
    if poly.area < MIN_BUILDING_AREA_M2:
        return None
    clipped = _parts(poly.intersection(square), "Polygon")
    if not clipped:
        return None
    main = max(clipped, key=lambda p: p.area)
    if main.area < MIN_KEEP_RATIO * poly.area:
        return None
    kind = classify_building(tags, poly.area)
    return {"footprint": _ring(main), "kind": kind, "height": _r(building_height(tags, kind))}


def find_property(buildings: list[dict]) -> int | None:
    origin = Point(0, 0)
    best, best_d = None, PROPERTY_MAX_DIST_M
    for i, b in enumerate(buildings):
        poly = Polygon(b["footprint"])
        if poly.contains(origin):
            return i
        d = poly.distance(origin)
        if d <= best_d:
            best, best_d = i, d
    return best


def _element_latlon(el: dict) -> tuple[float, float] | None:
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    center = el.get("center")
    if center:
        return center["lat"], center["lon"]
    return None


def split_pois(lat: float, lon: float, radius_m: float, pois_raw: dict,
               categories: list[str]) -> tuple[list[dict], list[dict]]:
    wanted = set(categories)
    best: dict[str, tuple[float, dict, tuple[float, float]]] = {}
    for el in pois_raw.get("elements", []):
        tags = el.get("tags") or {}
        cat = categorize_poi(tags)
        pos = _element_latlon(el)
        if cat not in wanted or pos is None:
            continue
        d = haversine_m(lat, lon, *pos)
        if cat not in best or d < best[cat][0]:
            best[cat] = (d, tags, pos)

    near, far = [], []
    limit = radius_m - NEAR_INSET_M
    for cat, (d, tags, (plat, plon)) in sorted(best.items(), key=lambda kv: kv[1][0]):
        entry = {"category": cat, "name": tags.get("name", ""), "distance_m": round(d)}
        x, y = to_local(plat, plon, lat, lon)
        if abs(x) <= limit and abs(y) <= limit:
            near.append({**entry, "x": _r(x), "y": _r(y)})
        else:
            far.append({**entry, "bearing_deg": round(compute_bearing(lat, lon, plat, plon), 1)})
    return near, far


def assemble_scene(lat: float, lon: float, radius_m: float, area: dict, pois_raw: dict,
                   categories: list[str]) -> dict:
    square = box(-radius_m, -radius_m, radius_m, radius_m)
    buildings, roads, trees = [], [], []
    areas: dict[str, list] = {"park": [], "water": [], "forest": []}

    for el in area.get("elements", []):
        tags = el.get("tags") or {}
        if el.get("type") == "node":
            if tags.get("natural") == "tree":
                x, y = to_local(el["lat"], el["lon"], lat, lon)
                if abs(x) <= radius_m and abs(y) <= radius_m:
                    trees.append({"x": _r(x), "y": _r(y)})
            continue
        if "building" in tags:
            for poly in _polygons(el, lat, lon):
                b = _building(poly, tags, square)
                if b:
                    buildings.append(b)
        elif "highway" in tags:
            kind = road_kind(tags["highway"])
            pts = _coords(el.get("geometry"), lat, lon)
            if kind is None or el.get("type") != "way" or len(pts) < 2:
                continue
            for part in _parts(LineString(pts).intersection(square), "LineString"):
                roads.append({"points": [[_r(x), _r(y)] for x, y in part.coords], "kind": kind})
        else:
            layer = area_layer(tags)
            if layer is None:
                continue
            for poly in _polygons(el, lat, lon):
                for part in _parts(poly.intersection(square), "Polygon"):
                    if part.area >= 1.0:
                        areas[layer].append(_ring(part))

    near, far = split_pois(lat, lon, radius_m, pois_raw, categories)
    return {
        "center": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "buildings": buildings,
        "property": {"building_index": find_property(buildings)},
        "roads": roads,
        "areas": areas,
        "trees": trees,
        "near_pois": near,
        "far_pois": far,
    }


def build_scene(lat: float, lon: float, cfg: Config) -> dict:
    cache_dir = cfg.cache.dir if cfg.cache.enabled else None
    radius = cfg.radii.display_meters
    categories = cfg.poi.enabled()
    area = fetch_area(lat, lon, radius, cache_dir)
    warnings = []
    try:
        pois_raw = fetch_pois(lat, lon, categories, cache_dir)
    except OverpassError as exc:
        logger.warning("POI fetch failed: %s", exc)
        pois_raw = {"elements": []}
        warnings.append("poi_fetch_failed")
    scene = assemble_scene(lat, lon, radius, area, pois_raw, categories)
    scene["warnings"] = warnings
    return scene
```

- [ ] **Step 4: Run, expect pass**

Run: `.venv/bin/python -m pytest tests/test_assemble.py tests/test_rules.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/scene_builder.py tests/test_assemble.py
git commit -m "feat: assemble compact scene — clipping, property detection, nearest POI per category"
```

---

### Task 5: API trim, legacy removal, fixture

**Files:**
- Modify: `src/api.py`, `scripts/capture_fixture.py`, `fixtures/pezinok-centrum.json` (regenerated)
- Replace: `tests/test_api.py`
- Delete: `src/fetcher.py`, `src/renderer.py`, `src/genmap.py`, `src/styles.py`

**Interfaces:**
- Consumes: `scene_builder.build_scene`, `osm.OverpassError`, `osm.USER_AGENT`.
- Produces: `GET /api/scene` → scene JSON + `address`; 502 with `api.AREA_FAILED_DETAIL`; `api._reverse_geocode(lat, lon) -> str` (async).

- [ ] **Step 1: Write failing tests.** Replace `tests/test_api.py`:

```python
from unittest.mock import AsyncMock, patch

import httpx
from httpx import ASGITransport, AsyncClient

from osm import OverpassError

SCENE = {
    "center": {"lat": 48.28, "lon": 17.27}, "radius_m": 140, "buildings": [],
    "property": {"building_index": None}, "roads": [],
    "areas": {"park": [], "water": [], "forest": []}, "trees": [],
    "near_pois": [], "far_pois": [], "warnings": [],
}


async def _get(url):
    from api import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(url)


async def test_health():
    r = await _get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_scene_returns_scene_with_address():
    with patch("api.build_scene", return_value=dict(SCENE)), \
         patch("api._reverse_geocode", AsyncMock(return_value="Záhradná, Pezinok")):
        r = await _get("/api/scene?lat=48.28&lon=17.27")
    assert r.status_code == 200
    body = r.json()
    assert body["address"] == "Záhradná, Pezinok"
    assert body["far_pois"] == []


async def test_scene_502_when_area_fetch_fails():
    from api import AREA_FAILED_DETAIL
    with patch("api.build_scene", side_effect=OverpassError("all down")):
        r = await _get("/api/scene?lat=48.28&lon=17.27")
    assert r.status_code == 502
    assert r.json()["detail"] == AREA_FAILED_DETAIL


async def test_scene_rejects_invalid_lat():
    r = await _get("/api/scene?lat=100&lon=17")
    assert r.status_code == 422


async def test_fixture_mode_serves_new_format():
    r = await _get("/api/scene?lat=0&lon=0&fixture=true")
    assert r.status_code == 200
    assert {"buildings", "property", "near_pois", "far_pois", "address"} <= r.json().keys()


async def test_removed_endpoints_are_gone():
    assert (await _get("/api/route?from_lat=1&from_lon=1&to_lat=2&to_lon=2")).status_code == 404
    assert (await _get("/api/scene/share?lat=1&lon=1")).status_code == 404


async def test_reverse_geocode_falls_back_to_coordinates():
    from api import _reverse_geocode
    with patch("api.httpx.AsyncClient", side_effect=httpx.ConnectError("offline")):
        assert await _reverse_geocode(48.28, 17.27) == "48.2800, 17.2700"
```

- [ ] **Step 2: Run, expect failure**

Run: `.venv/bin/python -m pytest tests/test_api.py -v`
Expected: FAIL (`AREA_FAILED_DETAIL` / `_reverse_geocode` missing; fixture in old format).

- [ ] **Step 3: Implement `src/api.py`**

```python
import asyncio
import json
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import load_config
from osm import USER_AGENT, OverpassError
from scene_builder import build_scene

_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "pezinok-centrum.json"
AREA_FAILED_DETAIL = "Could not load map data from OpenStreetMap. Try again in a minute."

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
        _cfg = load_config(Path(__file__).parent.parent / "config.yaml")
    return _cfg


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
async def geocode(q: str):
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 5, "addressdetails": 0},
            headers={"User-Agent": USER_AGENT},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail="Geocode upstream error") from exc
    return resp.json()


# Serve frontend build if it exists (production mode)
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    cfg = _get_cfg()
    uvicorn.run("api:app", host=cfg.api.host, port=cfg.api.port, reload=True)
```

`scripts/capture_fixture.py`:
```python
#!/usr/bin/env python3
"""
Generate fixtures/pezinok-centrum.json from live OSM data.

Run this whenever the scene data structure changes:
    python scripts/capture_fixture.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api import _reverse_geocode
from config import load_config
from scene_builder import build_scene

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "pezinok-centrum.json"


def main():
    cfg = load_config(CONFIG_PATH)
    lat, lon = cfg.location.lat, cfg.location.lon
    print(f"Fetching scene for lat={lat}, lon={lon} ...")
    data = build_scene(lat, lon, cfg)
    data["address"] = asyncio.run(_reverse_geocode(lat, lon))
    FIXTURE_PATH.parent.mkdir(exist_ok=True, parents=True)
    FIXTURE_PATH.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to {FIXTURE_PATH}: {len(data['buildings'])} buildings, "
          f"{len(data['near_pois'])} near / {len(data['far_pois'])} far POIs, warnings={data['warnings']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Remove legacy modules and regenerate the fixture**

```bash
git rm -q src/fetcher.py src/renderer.py src/genmap.py src/styles.py
time .venv/bin/python scripts/capture_fixture.py
```
Expected: finishes in well under a minute and prints non-zero buildings and roughly 8 POIs total with `warnings=[]`. If Overpass is down, retry later. Do not commit a fixture with `poi_fetch_failed`.

- [ ] **Step 5: Run the whole backend suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/api.py scripts/capture_fixture.py fixtures/pezinok-centrum.json tests/test_api.py
git commit -m "feat: trim API to scene/geocode, 502 on OSM failure, regenerate fixture; remove legacy PNG pipeline"
```

---

### Task 6: Frontend pure helpers (format, random, url, palette, geometry, roofs, placement, edge)

**Files:**
- Create: `frontend/src/format.js`, `frontend/src/random.js`, `frontend/src/url.js`, `frontend/src/palette.js`, `frontend/src/map/geom.js`, `frontend/src/map/lines.js`, `frontend/src/map/roofs.js`, `frontend/src/map/placement.js`, `frontend/src/overlay/edge.js`
- Tests: `frontend/src/format.test.js`, `frontend/src/url.test.js`, `frontend/src/map/geom.test.js`, `frontend/src/map/lines.test.js`, `frontend/src/map/roofs.test.js`, `frontend/src/map/placement.test.js`, `frontend/src/overlay/edge.test.js`

**Interfaces (produced, used by Tasks 7–8):**
- `formatDistance(m: number) -> string`; `poiTitle(poi, maxLen = 14) -> string`
- `mulberry32(seed) -> () => number in [0,1)`; `seedFromCoords(lat, lon) -> int`; `hashPoint(x, y) -> uint32`
- `DEFAULT_COORDS`, `getCoordsFromURL(search) -> {lat, lon} | null`, `isFixture(search) -> bool`
- `PALETTE` (keys: slabTop, slabSide, park, forest, water, road, path, roadDash, walls[5], roofs[5], otherWalls, propertyWalls, property, trunk, crowns[3], cars[4], carCabin); `CATEGORIES`; `categoryInfo(cat) -> {label, color}`
- geom: `polygonArea(pts)`, `centroid(pts) -> [x,y]`, `pointInPolygon(p, pts)`, `distToSegment(p, a, b)`, `distToPolyline(p, pts)`, `distToPolygon(p, pts)`, `convexHull(pts)`
- lines: `cumulativeLengths(pts) -> number[]`, `pointAlong(pts, cum, s) -> {x, y, dx, dy}`, `dashSegments(pts, on, off) -> polyline[]`, `ribbonTriangles(polylines, width) -> number[]` (flat plan x,y pairs, 3 vertices per triangle)
- roofs: `orientedRect(pts) -> {cx, cy, angle, length, width}` (length ≥ width, angle = long axis), `roofType(kind, pts) -> 'gable'|'hip'|'flat'|'none'`, `roofTriangles(rect, type, overhang = 0.6) -> [x, y, z][]` (plan coords, z up from wall top)
- placement: `seedTreePositions(scene, rng) -> [x, y][]`, `planCars(roads, rng) -> car[]`, `carPose(car, t) -> {x, y, heading}`
- edge: `edgePoint(center, dir, halfW, halfH, W, H, pad = 10) -> {x, y}`, `resolveOverlaps(boxes, W, H, pad = 10, gap = 6, maxIter = 20) -> boxes`

- [ ] **Step 1: Write failing tests**

`frontend/src/format.test.js`:
```js
import { describe, expect, it } from 'vitest';
import { formatDistance, poiTitle } from './format.js';

describe('formatDistance', () => {
  it.each([
    [0, '0 m'], [48, '50 m'], [350, '350 m'], [994, '990 m'], [995, '1,0 km'],
    [1000, '1,0 km'], [2412, '2,4 km'], [9940, '9,9 km'], [9950, '10 km'], [25000, '25 km'],
  ])('%i m -> %s', (m, s) => expect(formatDistance(m)).toBe(s));
});

describe('poiTitle', () => {
  it('uses a short name', () => expect(poiTitle({ category: 'supermarket', name: 'Lidl' })).toBe('Lidl'));
  it('falls back to label for long names', () =>
    expect(poiTitle({ category: 'hospital', name: 'Fakultná nemocnica Trnava' })).toBe('Nemocnica'));
  it('falls back to label for missing names', () => expect(poiTitle({ category: 'pharmacy', name: '' })).toBe('Lekáreň'));
  it('handles unknown categories', () => expect(poiTitle({ category: 'zoo' })).toBe('zoo'));
});
```

`frontend/src/url.test.js`:
```js
import { describe, expect, it } from 'vitest';
import { getCoordsFromURL, isFixture } from './url.js';

describe('url', () => {
  it('parses coords', () => expect(getCoordsFromURL('?lat=48.1&lon=17.2')).toEqual({ lat: 48.1, lon: 17.2 }));
  it('returns null when missing', () => expect(getCoordsFromURL('?lat=48.1')).toBeNull());
  it('rejects out-of-range', () => expect(getCoordsFromURL('?lat=100&lon=17')).toBeNull());
  it('detects fixture', () => {
    expect(isFixture('?fixture=true')).toBe(true);
    expect(isFixture('')).toBe(false);
  });
});
```

`frontend/src/map/geom.test.js`:
```js
import { describe, expect, it } from 'vitest';
import { centroid, convexHull, distToPolygon, distToPolyline, pointInPolygon, polygonArea } from './geom.js';

const sq = [[0, 0], [10, 0], [10, 10], [0, 10]];

describe('geom', () => {
  it('area', () => expect(polygonArea(sq)).toBe(100));
  it('centroid', () => expect(centroid(sq)).toEqual([5, 5]));
  it('point in polygon', () => {
    expect(pointInPolygon([5, 5], sq)).toBe(true);
    expect(pointInPolygon([15, 5], sq)).toBe(false);
  });
  it('distances', () => {
    expect(distToPolyline([5, 3], [[0, 0], [10, 0]])).toBe(3);
    expect(distToPolygon([5, 5], sq)).toBe(0);
    expect(distToPolygon([13, 5], sq)).toBe(3);
  });
  it('convex hull drops inner points', () => expect(convexHull([...sq, [5, 5]])).toHaveLength(4));
});
```

`frontend/src/map/lines.test.js`:
```js
import { describe, expect, it } from 'vitest';
import { cumulativeLengths, dashSegments, pointAlong, ribbonTriangles } from './lines.js';

const line = [[0, 0], [10, 0], [10, 10]];

describe('lines', () => {
  it('cumulative lengths', () => expect(cumulativeLengths(line)).toEqual([0, 10, 20]));
  it('point along second segment', () => {
    const p = pointAlong(line, cumulativeLengths(line), 15);
    expect(p).toEqual({ x: 10, y: 5, dx: 0, dy: 1 });
  });
  it('point along clamps', () => expect(pointAlong(line, cumulativeLengths(line), 99).y).toBe(10));
  it('dashes', () => {
    const d = dashSegments([[0, 0], [20, 0]], 4, 5);
    expect(d).toHaveLength(3);
    expect(d[1]).toEqual([[9, 0], [13, 0]]);
  });
  it('ribbon triangle count: 2 per segment + 12 per vertex', () =>
    expect(ribbonTriangles([[[0, 0], [10, 0]]], 2)).toHaveLength((2 + 24) * 6));
});
```

`frontend/src/map/roofs.test.js`:
```js
import { describe, expect, it } from 'vitest';
import { orientedRect, roofTriangles, roofType } from './roofs.js';

function rotated(w, h, deg, cx, cy) {
  const a = (deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  return [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]]
    .map(([x, y]) => [cx + x * c - y * s, cy + x * s + y * c]);
}

describe('orientedRect', () => {
  it('recovers a rotated rectangle', () => {
    const r = orientedRect(rotated(20, 10, 30, 5, 5));
    expect(r.length).toBeCloseTo(20);
    expect(r.width).toBeCloseTo(10);
    expect(r.cx).toBeCloseTo(5);
    expect(r.cy).toBeCloseTo(5);
    expect(Math.abs(Math.sin(r.angle - Math.PI / 6))).toBeCloseTo(0);
  });
  it('long axis wins for a tall rectangle', () => {
    const r = orientedRect(rotated(6, 18, 0, 0, 0));
    expect(r.length).toBeCloseTo(18);
    expect(Math.abs(Math.cos(r.angle))).toBeCloseTo(0);
  });
});

describe('roofType', () => {
  const L = [[0, 0], [20, 0], [20, 10], [10, 10], [10, 20], [0, 20]];
  it('rectangular house -> gable', () => expect(roofType('house', rotated(12, 8, 10, 0, 0))).toBe('gable'));
  it('L-shaped house -> hip', () => expect(roofType('house', L)).toBe('hip'));
  it('apartment -> flat', () => expect(roofType('apartment', L)).toBe('flat'));
  it('other -> none', () => expect(roofType('other', L)).toBe('none'));
});

describe('roofTriangles', () => {
  const rect = { cx: 0, cy: 0, angle: 0, length: 12, width: 8 };
  it('gable has ridge height 0.45 * width and 6 triangles', () => {
    const t = roofTriangles(rect, 'gable');
    expect(t).toHaveLength(18);
    expect(Math.max(...t.map((p) => p[2]))).toBeCloseTo(3.6);
  });
  it('hip ridge is shorter than the base', () => {
    const t = roofTriangles(rect, 'hip');
    const ridge = t.filter((p) => p[2] > 0).map((p) => p[0]);
    expect(Math.max(...ridge)).toBeCloseTo(2);
  });
});
```

`frontend/src/map/placement.test.js`:
```js
import { describe, expect, it } from 'vitest';
import { mulberry32 } from '../random.js';
import { distToPolygon } from './geom.js';
import { carPose, planCars, seedTreePositions } from './placement.js';

const park = [[0, 0], [60, 0], [60, 60], [0, 60]];
const house = [[20, 20], [40, 20], [40, 40], [20, 40]];
const base = { buildings: [{ footprint: house }], roads: [], areas: { park: [park], forest: [], water: [] }, trees: [{ x: -50, y: -50 }] };

describe('seedTreePositions', () => {
  it('keeps OSM trees and seeds parks away from buildings', () => {
    const pts = seedTreePositions(base, mulberry32(1));
    expect(pts[0]).toEqual([-50, -50]);
    expect(pts.length).toBeGreaterThan(5);
    for (const p of pts.slice(1)) expect(distToPolygon(p, house)).toBeGreaterThanOrEqual(3);
  });
  it('is deterministic', () =>
    expect(seedTreePositions(base, mulberry32(7))).toEqual(seedTreePositions(base, mulberry32(7))));
  it('handles an empty scene', () =>
    expect(seedTreePositions({ buildings: [], roads: [], areas: {}, trees: [] }, mulberry32(1))).toEqual([]));
});

describe('cars', () => {
  const roads = [{ kind: 'main', points: [[-140, 0], [140, 0]] }, { kind: 'path', points: [[0, -140], [0, 140]] }];
  it('one car per 60 m of drivable road, max 6', () => {
    expect(planCars(roads, mulberry32(1))).toHaveLength(4);
    expect(planCars([], mulberry32(1))).toEqual([]);
  });
  it('drives on the right lane and turns around at the end', () => {
    const car = { ...planCars(roads, mulberry32(1))[0], offset: 0, speed: 10 };
    const a = carPose(car, 1);
    expect(a.x).toBeCloseTo(-130);
    expect(a.y).toBeCloseTo(-2);
    expect(a.heading).toBeCloseTo(0);
    const b = carPose(car, 29);
    expect(b.x).toBeCloseTo(130);
    expect(b.y).toBeCloseTo(2);
    expect(Math.abs(b.heading)).toBeCloseTo(Math.PI);
  });
});
```

`frontend/src/overlay/edge.test.js`:
```js
import { describe, expect, it } from 'vitest';
import { edgePoint, resolveOverlaps } from './edge.js';

const C = { x: 400, y: 300 };

describe('edgePoint', () => {
  it.each([
    [{ x: 0, y: -1 }, { x: 400, y: 30 }],
    [{ x: 1, y: 0 }, { x: 740, y: 300 }],
    [{ x: 0, y: 1 }, { x: 400, y: 570 }],
    [{ x: -1, y: 0 }, { x: 60, y: 300 }],
  ])('dir %o', (dir, expected) => expect(edgePoint(C, dir, 50, 20, 800, 600)).toEqual(expected));

  it('stays inside a 320 px wide widget', () => {
    const p = edgePoint({ x: 160, y: 120 }, { x: 0.8, y: -0.6 }, 60, 18, 320, 240);
    expect(p.x).toBeLessThanOrEqual(320 - 70);
    expect(p.y).toBeGreaterThanOrEqual(28);
  });
});

describe('resolveOverlaps', () => {
  it('separates two badges on the same edge', () => {
    const [a, b] = resolveOverlaps([{ x: 740, y: 300, w: 100, h: 40 }, { x: 740, y: 310, w: 100, h: 40 }], 800, 600);
    expect(Math.abs(a.y - b.y)).toBeGreaterThanOrEqual(46 - 1e-6);
    expect(a.x).toBe(740);
  });
  it('separates three stacked badges and keeps them inside', () => {
    const boxes = resolveOverlaps([0, 1, 2].map(() => ({ x: 740, y: 30, w: 100, h: 40 })), 800, 600);
    for (let i = 0; i < 3; i++) {
      expect(boxes[i].y).toBeGreaterThanOrEqual(30);
      for (let j = i + 1; j < 3; j++) expect(Math.abs(boxes[i].y - boxes[j].y)).toBeGreaterThanOrEqual(46 - 1e-6);
    }
  });
});
```

- [ ] **Step 2: Run, expect failure**

Run: `cd frontend && npx vitest run src/format.test.js src/url.test.js src/map src/overlay`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement**

`frontend/src/palette.js`:
```js
export const PALETTE = {
  slabTop: '#CFE8B9',
  slabSide: '#B4D39C',
  park: '#B9E0A0',
  forest: '#9CCB86',
  water: '#8FD3F4',
  road: '#FBF6EC',
  path: '#F3EBDA',
  roadDash: '#F6C85F',
  walls: ['#FFF4E6', '#FDE2E4', '#E3F1EC', '#E2E8FD', '#FFF6CC'],
  roofs: ['#F28482', '#F6BD60', '#84A59D', '#8E9AAF', '#E07A5F'],
  otherWalls: '#E9E4DA',
  propertyWalls: '#FFFFFF',
  property: '#FF5A5F',
  trunk: '#A1785C',
  crowns: ['#86C98A', '#A1D9B4', '#6DB57A'],
  cars: ['#FF7B7B', '#5CA8FF', '#FFC94D', '#9C7CF4'],
  carCabin: '#EAF4FF',
};

export const CATEGORIES = {
  hospital: { label: 'Nemocnica', color: '#E05252' },
  supermarket: { label: 'Supermarket', color: '#3E9E6B' },
  school: { label: 'Škola', color: '#4A90D9' },
  kindergarten: { label: 'Škôlka', color: '#F2A541' },
  pharmacy: { label: 'Lekáreň', color: '#3AAFA9' },
  bus_stop: { label: 'Zastávka', color: '#7B5EA7' },
  train: { label: 'Stanica', color: '#7F8C8D' },
  park: { label: 'Park', color: '#5FAF6E' },
};

export function categoryInfo(category) {
  return CATEGORIES[category] ?? { label: category, color: '#7F8C8D' };
}
```

`frontend/src/format.js`:
```js
import { categoryInfo } from './palette.js';

export function formatDistance(meters) {
  const m = Math.round(meters / 10) * 10;
  if (m < 1000) return `${m} m`;
  const km = Math.round(m / 100) / 10;
  if (km >= 10) return `${Math.round(km)} km`;
  return `${km.toFixed(1).replace('.', ',')} km`;
}

export function poiTitle(poi, maxLen = 14) {
  const name = (poi.name ?? '').trim();
  return name && name.length <= maxLen ? name : categoryInfo(poi.category).label;
}
```

`frontend/src/random.js`:
```js
export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function seedFromCoords(lat, lon) {
  return (Math.imul(Math.round(lat * 1e5), 73856093) ^ Math.imul(Math.round(lon * 1e5), 19349663)) >>> 0;
}

export function hashPoint(x, y) {
  let h = Math.imul(Math.round(x * 10), 73856093) ^ Math.imul(Math.round(y * 10), 19349663);
  h = Math.imul(h ^ (h >>> 13), 0x5bd1e995);
  return (h ^ (h >>> 15)) >>> 0;
}
```

`frontend/src/url.js`:
```js
export const DEFAULT_COORDS = { lat: 48.28646434486518, lon: 17.27221245956356 };

export function getCoordsFromURL(search) {
  const params = new URLSearchParams(search);
  const lat = parseFloat(params.get('lat'));
  const lon = parseFloat(params.get('lon'));
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  return { lat, lon };
}

export function isFixture(search) {
  return new URLSearchParams(search).get('fixture') === 'true';
}
```

`frontend/src/map/geom.js`:
```js
export function polygonArea(pts) {
  let a = 0;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) a += pts[j][0] * pts[i][1] - pts[i][0] * pts[j][1];
  return Math.abs(a) / 2;
}

export function centroid(pts) {
  let x = 0, y = 0;
  for (const p of pts) { x += p[0]; y += p[1]; }
  return [x / pts.length, y / pts.length];
}

export function pointInPolygon([x, y], pts) {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i], [xj, yj] = pts[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function distToSegment([px, py], [ax, ay], [bx, by]) {
  const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
  const t = l2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) : 0;
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

export function distToPolyline(p, pts) {
  let d = Infinity;
  for (let i = 1; i < pts.length; i++) d = Math.min(d, distToSegment(p, pts[i - 1], pts[i]));
  return d;
}

export function distToPolygon(p, pts) {
  if (pointInPolygon(p, pts)) return 0;
  return distToPolyline(p, [...pts, pts[0]]);
}

export function convexHull(points) {
  const pts = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (pts.length < 3) return pts;
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower = [], upper = [];
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower.at(-2), lower.at(-1), p) <= 0) lower.pop();
    lower.push(p);
  }
  for (const p of [...pts].reverse()) {
    while (upper.length >= 2 && cross(upper.at(-2), upper.at(-1), p) <= 0) upper.pop();
    upper.push(p);
  }
  return lower.slice(0, -1).concat(upper.slice(0, -1));
}
```

`frontend/src/map/lines.js`:
```js
export function cumulativeLengths(pts) {
  const cum = [0];
  for (let i = 1; i < pts.length; i++) {
    cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  }
  return cum;
}

export function pointAlong(pts, cum, s) {
  const total = cum[cum.length - 1];
  const d = Math.max(0, Math.min(total, s));
  let i = 1;
  while (i < cum.length - 1 && cum[i] < d) i++;
  const [ax, ay] = pts[i - 1], [bx, by] = pts[i];
  const len = cum[i] - cum[i - 1] || 1;
  const t = (d - cum[i - 1]) / len;
  return { x: ax + (bx - ax) * t, y: ay + (by - ay) * t, dx: (bx - ax) / len, dy: (by - ay) / len };
}

function slice(pts, cum, s, e) {
  const a = pointAlong(pts, cum, s), b = pointAlong(pts, cum, e);
  const mid = [];
  for (let i = 1; i < pts.length - 1; i++) if (cum[i] > s && cum[i] < e) mid.push(pts[i]);
  return [[a.x, a.y], ...mid, [b.x, b.y]];
}

export function dashSegments(pts, on, off) {
  const cum = cumulativeLengths(pts), total = cum[cum.length - 1], out = [];
  for (let s = 0; s < total; s += on + off) {
    const e = Math.min(total, s + on);
    if (e - s < on * 0.3) break;
    out.push(slice(pts, cum, s, e));
  }
  return out;
}

const DISC_SEGMENTS = 12;

export function ribbonTriangles(polylines, width) {
  const h = width / 2, out = [];
  for (const pts of polylines) {
    for (let i = 1; i < pts.length; i++) {
      const [ax, ay] = pts[i - 1], [bx, by] = pts[i];
      const len = Math.hypot(bx - ax, by - ay);
      if (len < 1e-6) continue;
      const nx = (-(by - ay) / len) * h, ny = ((bx - ax) / len) * h;
      out.push(ax + nx, ay + ny, ax - nx, ay - ny, bx - nx, by - ny);
      out.push(ax + nx, ay + ny, bx - nx, by - ny, bx + nx, by + ny);
    }
    for (const [cx, cy] of pts) {
      for (let k = 0; k < DISC_SEGMENTS; k++) {
        const a0 = (k / DISC_SEGMENTS) * 2 * Math.PI, a1 = ((k + 1) / DISC_SEGMENTS) * 2 * Math.PI;
        out.push(cx, cy, cx + Math.cos(a0) * h, cy + Math.sin(a0) * h, cx + Math.cos(a1) * h, cy + Math.sin(a1) * h);
      }
    }
  }
  return out;
}
```

`frontend/src/map/roofs.js`:
```js
import { convexHull, polygonArea } from './geom.js';

export const GABLE_MIN_FILL = 0.8;

export function orientedRect(pts) {
  const hull = convexHull(pts);
  let best = null;
  for (let i = 0; i < hull.length; i++) {
    const [ax, ay] = hull[i], [bx, by] = hull[(i + 1) % hull.length];
    const angle = Math.atan2(by - ay, bx - ax), c = Math.cos(angle), s = Math.sin(angle);
    let minU = Infinity, maxU = -Infinity, minV = Infinity, maxV = -Infinity;
    for (const [x, y] of hull) {
      const u = x * c + y * s, v = -x * s + y * c;
      minU = Math.min(minU, u); maxU = Math.max(maxU, u);
      minV = Math.min(minV, v); maxV = Math.max(maxV, v);
    }
    const area = (maxU - minU) * (maxV - minV);
    if (!best || area < best.area - 1e-9) best = { area, angle, minU, maxU, minV, maxV };
  }
  let { angle } = best;
  const c = Math.cos(angle), s = Math.sin(angle);
  const cu = (best.minU + best.maxU) / 2, cv = (best.minV + best.maxV) / 2;
  let length = best.maxU - best.minU, width = best.maxV - best.minV;
  if (width > length) {
    [length, width] = [width, length];
    angle += Math.PI / 2;
  }
  return { cx: cu * c - cv * s, cy: cu * s + cv * c, angle, length, width };
}

export function roofType(kind, pts) {
  if (kind === 'house') {
    const r = orientedRect(pts);
    return polygonArea(pts) / (r.length * r.width) >= GABLE_MIN_FILL ? 'gable' : 'hip';
  }
  if (kind === 'other') return 'none';
  return 'flat';
}

export function roofTriangles(rect, type, overhang = 0.6) {
  const hl = rect.length / 2 + overhang, hw = rect.width / 2 + overhang;
  const h = (type === 'gable' ? 0.45 : 0.3) * rect.width;
  const a = type === 'gable' ? hl : Math.max(0, hl - hw);
  const c = Math.cos(rect.angle), s = Math.sin(rect.angle);
  const P = (u, v, z) => [rect.cx + u * c - v * s, rect.cy + u * s + v * c, z];
  const b1 = P(-hl, -hw, 0), b2 = P(hl, -hw, 0), b3 = P(hl, hw, 0), b4 = P(-hl, hw, 0);
  const r1 = P(-a, 0, h), r2 = P(a, 0, h);
  return [b1, b2, r2, b1, r2, r1, b3, b4, r1, b3, r1, r2, b2, b3, r2, b4, b1, r1];
}
```

Note the roof test: the hip ridge half-length is `max(0, hl − hw)` = (6 + 0.6) − (4 + 0.6) = 2.

`frontend/src/map/placement.js`:
```js
import { PALETTE } from '../palette.js';
import { distToPolygon, distToPolyline, pointInPolygon, polygonArea } from './geom.js';
import { cumulativeLengths, pointAlong } from './lines.js';

const TREE_DENSITY_M2 = { park: 180, forest: 60 };
const MAX_SEEDED_TREES = 350;
const TREE_CLEARANCE_M = 3;
const ROAD_HALF_WIDTH = { main: 4.5, street: 3, path: 1.25 };

export function seedTreePositions(scene, rng) {
  const out = (scene.trees ?? []).map((t) => [t.x, t.y]);
  const blocked = (p) =>
    scene.buildings.some((b) => distToPolygon(p, b.footprint) < TREE_CLEARANCE_M) ||
    scene.roads.some((r) => distToPolyline(p, r.points) < (ROAD_HALF_WIDTH[r.kind] ?? 3) + TREE_CLEARANCE_M);
  let budget = MAX_SEEDED_TREES;
  for (const layer of ['forest', 'park']) {
    for (const ring of scene.areas?.[layer] ?? []) {
      const want = Math.min(budget, Math.floor(polygonArea(ring) / TREE_DENSITY_M2[layer]));
      const xs = ring.map((p) => p[0]), ys = ring.map((p) => p[1]);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
      let placed = 0;
      for (let tries = 0; placed < want && tries < want * 6; tries++) {
        const p = [x0 + rng() * (x1 - x0), y0 + rng() * (y1 - y0)];
        if (!pointInPolygon(p, ring) || blocked(p)) continue;
        out.push(p);
        placed++;
      }
      budget -= placed;
    }
  }
  return out;
}

const MAX_CARS = 6;
const METERS_PER_CAR = 60;
const MIN_ROAD_M = 20;
const LANE_OFFSET_M = 2;

export function planCars(roads, rng) {
  const drivable = roads
    .filter((r) => r.kind === 'main' || r.kind === 'street')
    .map((r) => ({ pts: r.points, cum: cumulativeLengths(r.points) }))
    .filter((r) => r.cum.at(-1) >= MIN_ROAD_M)
    .sort((a, b) => b.cum.at(-1) - a.cum.at(-1));
  const total = drivable.reduce((sum, r) => sum + r.cum.at(-1), 0);
  const n = Math.min(MAX_CARS, Math.floor(total / METERS_PER_CAR));
  return Array.from({ length: n }, (_, i) => {
    const road = drivable[i % drivable.length];
    return {
      road,
      speed: 8 + rng() * 6,
      offset: rng() * road.cum.at(-1) * 2,
      color: PALETTE.cars[i % PALETTE.cars.length],
    };
  });
}

export function carPose(car, t) {
  const L = car.road.cum.at(-1);
  const d = (car.offset + car.speed * t) % (2 * L);
  const forward = d < L;
  const p = pointAlong(car.road.pts, car.road.cum, forward ? d : 2 * L - d);
  const dx = forward ? p.dx : -p.dx, dy = forward ? p.dy : -p.dy;
  return { x: p.x + dy * LANE_OFFSET_M, y: p.y - dx * LANE_OFFSET_M, heading: Math.atan2(dy, dx) };
}
```

Note on the car test: the road is 280 m long, so 280 / 60 → 4 cars. At t = 1 with offset 0 and speed 10, the car is 10 m along the road heading east: x = −130, lane y = −2. At t = 29 it has traveled 290 m, so 10 m back on the return leg: x = 130, heading west, lane y = +2.

`frontend/src/overlay/edge.js`:
```js
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);

export function edgePoint(center, dir, halfW, halfH, W, H, pad = 10) {
  const mx = halfW + pad, my = halfH + pad;
  const cx = clamp(center.x, mx, W - mx), cy = clamp(center.y, my, H - my);
  let k = Infinity;
  if (dir.x > 1e-6) k = Math.min(k, (W - mx - cx) / dir.x);
  if (dir.x < -1e-6) k = Math.min(k, (mx - cx) / dir.x);
  if (dir.y > 1e-6) k = Math.min(k, (H - my - cy) / dir.y);
  if (dir.y < -1e-6) k = Math.min(k, (my - cy) / dir.y);
  if (!Number.isFinite(k)) k = 0;
  return { x: cx + dir.x * k, y: cy + dir.y * k };
}

export function resolveOverlaps(boxes, W, H, pad = 10, gap = 6, maxIter = 20) {
  for (let iter = 0; iter < maxIter; iter++) {
    let moved = false;
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i], b = boxes[j];
        const ox = (a.w + b.w) / 2 + gap - Math.abs(a.x - b.x);
        const oy = (a.h + b.h) / 2 + gap - Math.abs(a.y - b.y);
        if (ox <= 1e-6 || oy <= 1e-6) continue;
        moved = true;
        if (ox < oy) {
          const s = ((a.x <= b.x ? -1 : 1) * ox) / 2;
          a.x += s; b.x -= s;
        } else {
          const s = ((a.y <= b.y ? -1 : 1) * oy) / 2;
          a.y += s; b.y -= s;
        }
      }
    }
    for (const b of boxes) {
      b.x = clamp(b.x, b.w / 2 + pad, W - b.w / 2 - pad);
      b.y = clamp(b.y, b.h / 2 + pad, H - b.h / 2 - pad);
    }
    if (!moved) break;
  }
  return boxes;
}
```

- [ ] **Step 4: Run, expect pass**

Run: `cd frontend && npx vitest run src/format.test.js src/url.test.js src/map src/overlay`
Expected: all PASS. If the "three stacked badges" test fails because 20 iterations are not enough for identical starting points, keep `maxIter = 20` but make the tie-break deterministic by index. In the `oy` branch, when `a.y === b.y`, move `a` up and `b` down (the `<=` already does this) and re-run. It must pass with the existing algorithm before moving on.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/format.js frontend/src/random.js frontend/src/url.js frontend/src/palette.js frontend/src/map frontend/src/overlay frontend/src/*.test.js
git commit -m "feat(frontend): pure helpers — distance format, geometry, roofs, tree/car placement, edge badges"
```

---

### Task 7: Three.js layers (materials, ground, buildings, trees, cars, property, stage)

**Files:**
- Create: `frontend/src/map/materials.js`, `frontend/src/map/ground.js`, `frontend/src/map/buildings.js`, `frontend/src/map/trees.js`, `frontend/src/map/cars.js`, `frontend/src/map/property.js`, `frontend/src/map/stage.js`

**Interfaces:**
- Consumes: Task 6 helpers and `PALETTE`.
- Produces: `createMaterialCache() -> (color, opts?) => MeshLambertMaterial`; `addGround(world, scene, mat)`; `addBuildings(world, buildings, propertyIndex, mat)`; `addTrees(world, scene, mat) -> {update(t)}`; `addCars(world, roads, mat, rng) -> {update(t)}`; `addProperty(world, scene, mat) -> {update(t), anchor: {x, y, h}}`; `createStage(container, scene) -> {dispose()}` (calls `createOverlay` from Task 8).

These modules are WebGL glue with no unit tests (logic lives in Task 6). They are verified visually in Task 9.

- [ ] **Step 1: `frontend/src/map/materials.js`**

```js
import * as THREE from 'three';

export function createMaterialCache() {
  const cache = new Map();
  return (color, opts = {}) => {
    const key = `${color}|${opts.side ?? ''}|${opts.flatShading ? 1 : 0}`;
    if (!cache.has(key)) cache.set(key, new THREE.MeshLambertMaterial({ color, ...opts }));
    return cache.get(key);
  };
}
```

- [ ] **Step 2: `frontend/src/map/ground.js`**

```js
import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { dashSegments, ribbonTriangles } from './lines.js';

const SLAB_THICKNESS = 10;
const ROAD_WIDTH = { main: 9, street: 6, path: 2.5 };
const LEVEL = { forest: 0.02, park: 0.03, water: 0.04, path: 0.05, street: 0.06, main: 0.07, dash: 0.08 };

function flatGeometry(flat, y) {
  const n = flat.length / 2;
  const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    pos[i * 3] = flat[i * 2];
    pos[i * 3 + 1] = y;
    pos[i * 3 + 2] = -flat[i * 2 + 1];
    nor[i * 3 + 1] = 1;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  return g;
}

function addFlat(world, flat, y, material) {
  if (!flat.length) return;
  const mesh = new THREE.Mesh(flatGeometry(flat, y), material);
  mesh.receiveShadow = true;
  world.add(mesh);
}

export function addGround(world, scene, mat) {
  const r = scene.radius_m;
  const side = mat(PALETTE.slabSide), top = mat(PALETTE.slabTop);
  const slab = new THREE.Mesh(new THREE.BoxGeometry(2 * r, SLAB_THICKNESS, 2 * r), [side, side, top, side, side, side]);
  slab.position.y = -SLAB_THICKNESS / 2;
  slab.receiveShadow = true;
  world.add(slab);

  for (const layer of ['forest', 'park', 'water']) {
    for (const ring of scene.areas?.[layer] ?? []) {
      if (ring.length < 3) continue;
      const shape = new THREE.Shape(ring.map(([x, y]) => new THREE.Vector2(x, y)));
      const geo = new THREE.ShapeGeometry(shape);
      geo.rotateX(-Math.PI / 2);
      const mesh = new THREE.Mesh(geo, mat(PALETTE[layer], { side: THREE.DoubleSide }));
      mesh.position.y = LEVEL[layer];
      mesh.receiveShadow = true;
      world.add(mesh);
    }
  }

  const flatMat = (color) => mat(color, { side: THREE.DoubleSide });
  for (const kind of ['path', 'street', 'main']) {
    const lines = scene.roads.filter((rd) => rd.kind === kind).map((rd) => rd.points);
    if (!lines.length) continue;
    const src = kind === 'path' ? lines.flatMap((l) => dashSegments(l, 2, 1.5)) : lines;
    addFlat(world, ribbonTriangles(src, ROAD_WIDTH[kind]), LEVEL[kind], flatMat(kind === 'path' ? PALETTE.path : PALETTE.road));
    if (kind === 'main') {
      addFlat(world, ribbonTriangles(lines.flatMap((l) => dashSegments(l, 4, 5)), 0.5), LEVEL.dash, flatMat(PALETTE.roadDash));
    }
  }
}
```

- [ ] **Step 3: `frontend/src/map/buildings.js`**

```js
import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { hashPoint } from '../random.js';
import { centroid } from './geom.js';
import { orientedRect, roofTriangles, roofType } from './roofs.js';

const FLAT_CAP_M = 1;

function extrude(footprint, depth, y0) {
  const shape = new THREE.Shape(footprint.map(([x, y]) => new THREE.Vector2(x, y)));
  const geo = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: false });
  geo.rotateX(-Math.PI / 2);
  geo.translate(0, y0, 0);
  return geo;
}

function roofGeometry(tris, y0) {
  const pos = new Float32Array(tris.length * 3);
  tris.forEach(([x, y, z], i) => {
    pos[i * 3] = x;
    pos[i * 3 + 1] = y0 + z;
    pos[i * 3 + 2] = -y;
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.computeVertexNormals();
  return geo;
}

function addMesh(world, geo, material) {
  const mesh = new THREE.Mesh(geo, material);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  world.add(mesh);
}

export function addBuildings(world, buildings, propertyIndex, mat) {
  buildings.forEach((b, i) => {
    const fp = b.footprint;
    if (!fp || fp.length < 3) return;
    const isProperty = i === propertyIndex;
    const [cx, cy] = centroid(fp);
    const h = hashPoint(cx, cy);
    const wall = isProperty ? PALETTE.propertyWalls
      : b.kind === 'other' ? PALETTE.otherWalls
        : PALETTE.walls[h % PALETTE.walls.length];
    const roof = isProperty ? PALETTE.property : PALETTE.roofs[(h >>> 4) % PALETTE.roofs.length];
    try {
      const type = roofType(b.kind, fp);
      const wallHeight = type === 'flat' ? Math.max(1, b.height - FLAT_CAP_M) : b.height;
      addMesh(world, extrude(fp, wallHeight, 0), mat(wall));
      if (type === 'flat') {
        addMesh(world, extrude(fp, FLAT_CAP_M, wallHeight), mat(roof));
      } else if (type !== 'none') {
        const tris = roofTriangles(orientedRect(fp), type);
        addMesh(world, roofGeometry(tris, b.height), mat(roof, { flatShading: true, side: THREE.DoubleSide }));
      }
    } catch (err) {
      console.warn('genmap: skipped building', b, err);
    }
  });
}
```

- [ ] **Step 4: `frontend/src/map/trees.js`**

```js
import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { mulberry32, seedFromCoords } from '../random.js';
import { seedTreePositions } from './placement.js';

const TRUNK_H = 3;
const SWAY = 0.04;

export function addTrees(world, scene, mat) {
  const rng = mulberry32(seedFromCoords(scene.center.lat, scene.center.lon));
  const pts = seedTreePositions(scene, rng);
  const cap = Math.max(1, pts.length);
  const trunks = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.45, 0.6, TRUNK_H, 6), mat(PALETTE.trunk), cap);
  const crowns = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 14, 10), mat('#FFFFFF'), cap);
  const m = new THREE.Matrix4(), color = new THREE.Color();
  const trees = pts.map(([x, y], i) => {
    m.makeTranslation(x, TRUNK_H / 2, -y);
    trunks.setMatrixAt(i, m);
    crowns.setColorAt(i, color.set(PALETTE.crowns[i % PALETTE.crowns.length]));
    return { x, y, radius: 2.6 + rng() * 1.9, phase: rng() * Math.PI * 2 };
  });
  trunks.count = crowns.count = pts.length;
  for (const mesh of [trunks, crowns]) {
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    world.add(mesh);
  }

  const q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
  function update(t) {
    trees.forEach((tr, i) => {
      const cy = TRUNK_H + tr.radius * 0.8;
      p.set(tr.x + Math.sin(t * 1.3 + tr.phase) * SWAY * cy, cy, -tr.y);
      s.setScalar(tr.radius);
      crowns.setMatrixAt(i, m.compose(p, q, s));
    });
    crowns.instanceMatrix.needsUpdate = true;
  }
  update(0);
  return { update };
}
```

- [ ] **Step 5: `frontend/src/map/cars.js`**

```js
import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { carPose, planCars } from './placement.js';

export function addCars(world, roads, mat, rng) {
  const cars = planCars(roads, rng);
  const body = new THREE.BoxGeometry(4.4, 1.5, 2.2);
  const cabin = new THREE.BoxGeometry(2.3, 1.2, 1.9);
  const groups = cars.map((car) => {
    const g = new THREE.Group();
    const b = new THREE.Mesh(body, mat(car.color));
    b.position.y = 1.15;
    const c = new THREE.Mesh(cabin, mat(PALETTE.carCabin));
    c.position.set(-0.3, 2.4, 0);
    g.add(b, c);
    g.traverse((o) => { o.castShadow = true; });
    world.add(g);
    return g;
  });
  function update(t) {
    cars.forEach((car, i) => {
      const pose = carPose(car, t);
      groups[i].position.set(pose.x, 0.1, -pose.y);
      groups[i].rotation.y = pose.heading;
    });
  }
  update(0);
  return { update };
}
```

- [ ] **Step 6: `frontend/src/map/property.js`**

```js
import * as THREE from 'three';
import { PALETTE } from '../palette.js';
import { centroid } from './geom.js';
import { orientedRect } from './roofs.js';

const PIN_CLEARANCE = 12;

export function addProperty(world, scene, mat) {
  const idx = scene.property?.building_index;
  const b = idx != null ? scene.buildings[idx] : null;
  const [x, y] = b ? centroid(b.footprint) : [0, 0];
  const ringR = b ? Math.max(12, orientedRect(b.footprint).length / 2 + 5) : 12;
  const base = (b?.height ?? 0) + PIN_CLEARANCE;

  const pinMat = mat(PALETTE.property);
  const pin = new THREE.Group();
  const head = new THREE.Mesh(new THREE.SphereGeometry(3.2, 20, 14), pinMat);
  head.position.y = 5;
  const tip = new THREE.Mesh(new THREE.ConeGeometry(2.3, 5.5, 20), pinMat);
  tip.rotation.x = Math.PI;
  tip.position.y = 1.2;
  const dot = new THREE.Mesh(new THREE.SphereGeometry(1.3, 12, 8), mat('#FFFFFF'));
  dot.position.set(0, 5, 2.6);
  pin.add(head, tip, dot);
  pin.traverse((o) => { o.castShadow = true; });
  world.add(pin);

  const ringGeo = new THREE.RingGeometry(ringR, ringR + 2, 48);
  ringGeo.rotateX(-Math.PI / 2);
  const ringMat = new THREE.MeshBasicMaterial({ color: PALETTE.property, transparent: true, depthWrite: false });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.position.set(x, 0.2, -y);
  world.add(ring);

  function update(t) {
    pin.position.set(x, base + Math.sin(t * 2.4) * 1.6, -y);
    pin.rotation.y = t * 1.2;
    const p = (t * 0.45) % 1;
    ring.scale.setScalar(0.7 + p * 1.1);
    ringMat.opacity = 0.75 * (1 - p);
  }
  update(0);
  return { update, anchor: { x, y, h: base + 9 } };
}
```

- [ ] **Step 7: `frontend/src/map/stage.js`**

```js
import * as THREE from 'three';
import { createOverlay } from '../overlay/labels.js';
import { mulberry32, seedFromCoords } from '../random.js';
import { addBuildings } from './buildings.js';
import { addCars } from './cars.js';
import { addGround } from './ground.js';
import { createMaterialCache } from './materials.js';
import { addProperty } from './property.js';
import { addTrees } from './trees.js';

const CAMERA_DIR = new THREE.Vector3(190, 215, 250).normalize();
const SUN_DIR = new THREE.Vector3(90, 160, 60).normalize();

export function createStage(container, scene) {
  const r = scene.radius_m;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  const world = new THREE.Scene();
  world.add(new THREE.HemisphereLight('#FFFFFF', '#B7C9A8', 0.72 * Math.PI));
  const sun = new THREE.DirectionalLight('#FFF6E8', 0.7 * Math.PI);
  sun.position.copy(SUN_DIR).multiplyScalar(r * 2.5);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -r * 1.3, right: r * 1.3, top: r * 1.3, bottom: -r * 1.3, near: 1, far: r * 6 });
  sun.shadow.bias = -0.0005;
  world.add(sun);

  const mat = createMaterialCache();
  addGround(world, scene, mat);
  addBuildings(world, scene.buildings, scene.property?.building_index ?? null, mat);
  const trees = addTrees(world, scene, mat);
  const cars = addCars(world, scene.roads, mat, mulberry32(seedFromCoords(scene.center.lat, scene.center.lon) + 1));
  const property = addProperty(world, scene, mat);

  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -r * 10, r * 10);
  camera.position.copy(CAMERA_DIR).multiplyScalar(r * 3);
  camera.lookAt(0, 0, 0);

  const v = new THREE.Vector3();
  const project = (x, y, h = 0) => {
    v.set(x, h, -y).project(camera);
    return { x: ((v.x + 1) / 2) * container.clientWidth, y: ((1 - v.y) / 2) * container.clientHeight };
  };
  const overlay = createOverlay(container, scene, project, property.anchor);

  function fit() {
    const W = container.clientWidth, H = container.clientHeight, aspect = W / H;
    renderer.setSize(W, H);
    const hh = Math.max(0.8 * r, (1.22 * r) / aspect);
    Object.assign(camera, { left: -hh * aspect, right: hh * aspect, top: hh, bottom: -hh });
    camera.updateProjectionMatrix();
    overlay.measure();
  }

  function frame(ms) {
    const t = ms / 1000;
    property.update(t);
    trees.update(t);
    cars.update(t);
    renderer.render(world, camera);
    overlay.update();
  }

  let visible = true, raf = 0;
  function loop(ms) {
    raf = 0;
    if (!visible || document.hidden) return;
    frame(ms);
    raf = requestAnimationFrame(loop);
  }
  function start() {
    if (!reduced && !raf && visible && !document.hidden) raf = requestAnimationFrame(loop);
  }

  fit();
  frame(0);
  const ro = new ResizeObserver(() => { fit(); frame(performance.now()); });
  ro.observe(container);
  const io = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; start(); });
  io.observe(container);
  document.addEventListener('visibilitychange', start);
  if (document.fonts) document.fonts.ready.then(() => { overlay.measure(); frame(performance.now()); });
  start();

  return {
    dispose() {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      document.removeEventListener('visibilitychange', start);
      renderer.dispose();
    },
  };
}
```

- [ ] **Step 8: Commit** (it will not run until Task 8 wires the overlay and `main.js`)

```bash
git add frontend/src/map
git commit -m "feat(frontend): Three.js layers — slab, roads, pastel buildings with roofs, trees, cars, property pin"
```

---

### Task 8: Overlay, icons, widget shell and cleanup

**Files:**
- Create: `frontend/src/icons.js`, `frontend/src/overlay/labels.js`, `frontend/src/style.css`
- Replace: `frontend/src/main.js`, `frontend/index.html`
- Delete: `frontend/src/animations.js`, `frame.js`, `frame.test.js`, `infographic.js`, `poi.js`, `route.js`, `ui.js`, `colors.js`, `geometry.js`, `geometry.test.js`, `scene.js`, `main.test.js`

**Interfaces:**
- Consumes: `edgePoint`, `resolveOverlaps`, `formatDistance`, `poiTitle`, `categoryInfo`, `createStage`, `getCoordsFromURL`, `isFixture`, `DEFAULT_COORDS`.
- Produces: `createOverlay(container, scene, project, anchor) -> {update(), measure()}`; `iconSvg(name) -> string`.

- [ ] **Step 1: `frontend/src/icons.js`**

```js
const PATHS = {
  hospital: '<path d="M12 5v14M5 12h14"/>',
  supermarket: '<path d="M3 4h2l2.4 10.5h10.2L20 8H6.3"/><circle cx="9" cy="19" r="1.3"/><circle cx="17" cy="19" r="1.3"/>',
  school: '<path d="M2 9.5 12 5l10 4.5L12 14z"/><path d="M6 11.5V16c3.5 2.5 8.5 2.5 12 0v-4.5"/>',
  kindergarten: '<rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/><rect x="8.5" y="4" width="7" height="7" rx="1"/>',
  pharmacy: '<rect x="3" y="8.5" width="18" height="7" rx="3.5" transform="rotate(-45 12 12)"/><path d="M9.5 9.5l5 5"/>',
  bus_stop: '<rect x="5" y="3" width="14" height="14" rx="3"/><path d="M5 10h14M8 20v-3M16 20v-3"/>',
  train: '<rect x="6" y="3" width="12" height="13" rx="3"/><path d="M6 10h12M9 20l1.5-3M15 20l-1.5-3"/>',
  park: '<path d="M12 3 18 12H6z"/><path d="M12 12v8"/>',
  pin: '<path d="M12 21s-6-5.5-6-10a6 6 0 0 1 12 0c0 4.5-6 10-6 10z"/><circle cx="12" cy="11" r="2"/>',
  arrow: '<path d="M4 12h15M13 6l6 6-6 6"/>',
  north: '<path d="M12 3l5 14-5-3-5 3z"/>',
};

export function iconSvg(name) {
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${PATHS[name] ?? '<circle cx="12" cy="12" r="4"/>'}</svg>`;
}
```

- [ ] **Step 2: `frontend/src/overlay/labels.js`**

```js
import { formatDistance, poiTitle } from '../format.js';
import { iconSvg } from '../icons.js';
import { categoryInfo } from '../palette.js';
import { edgePoint, resolveOverlaps } from './edge.js';

const NEAR_LABEL_HEIGHT_M = 16;
const BEARING_PROBE_M = 80;

function el(tag, className, parent) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (parent) parent.appendChild(node);
  return node;
}

function text(tag, value) {
  const node = document.createElement(tag);
  node.textContent = value;
  return node;
}

function icon(category) {
  const node = el('i', 'gm-icon');
  node.style.setProperty('--c', categoryInfo(category).color);
  node.innerHTML = iconSvg(category);
  return node;
}

function place(node, x, y, anchor) {
  node.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) ${anchor}`;
}

export function createOverlay(container, scene, project, anchor) {
  const root = el('div', 'gm-overlay', container);

  const tag = el('div', 'gm-tag', root);
  tag.textContent = 'Na predaj';

  const nears = scene.near_pois.map((p) => {
    const node = el('div', 'gm-near', root);
    node.append(icon(p.category), text('b', p.name || categoryInfo(p.category).label), text('em', formatDistance(p.distance_m)));
    return { p, node };
  });

  const fars = scene.far_pois.map((p) => {
    const node = el('div', 'gm-far', root);
    const label = el('span', 'gm-far-text');
    label.append(text('b', poiTitle(p)), text('em', formatDistance(p.distance_m)));
    const arrow = el('span', 'gm-arrow');
    arrow.innerHTML = iconSvg('arrow');
    node.title = p.name || categoryInfo(p.category).label;
    node.append(icon(p.category), label, arrow);
    return { p, node, arrow, w: 0, h: 0 };
  });

  if (scene.address) {
    const address = el('div', 'gm-address', root);
    const pin = el('i', 'gm-pin');
    pin.innerHTML = iconSvg('pin');
    address.append(pin, text('span', scene.address));
  }

  const north = el('div', 'gm-north', root);
  const needle = el('span', 'gm-needle', north);
  needle.innerHTML = iconSvg('north');
  north.append(text('b', 'S'));

  function measure() {
    for (const f of fars) {
      f.w = f.node.offsetWidth;
      f.h = f.node.offsetHeight;
    }
  }

  function update() {
    const W = container.clientWidth, H = container.clientHeight;
    const top = project(anchor.x, anchor.y, anchor.h);
    place(tag, top.x, top.y, 'translate(-50%, -100%)');

    for (const n of nears) {
      const q = project(n.p.x, n.p.y, NEAR_LABEL_HEIGHT_M);
      place(n.node, q.x, q.y, 'translate(-11px, -50%)');
    }

    const c = project(anchor.x, anchor.y, 0);
    const boxes = fars.map((f) => {
      const b = (f.p.bearing_deg * Math.PI) / 180;
      const q = project(anchor.x + Math.sin(b) * BEARING_PROBE_M, anchor.y + Math.cos(b) * BEARING_PROBE_M, 0);
      let dx = q.x - c.x, dy = q.y - c.y;
      const len = Math.hypot(dx, dy) || 1;
      dx /= len; dy /= len;
      f.arrow.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`;
      const pt = edgePoint(c, { x: dx, y: dy }, f.w / 2, f.h / 2, W, H);
      return { x: pt.x, y: pt.y, w: f.w, h: f.h };
    });
    resolveOverlaps(boxes, W, H);
    boxes.forEach((b, i) => place(fars[i].node, b.x, b.y, 'translate(-50%, -50%)'));

    const o = project(0, 0, 0), n = project(0, 50, 0);
    needle.style.transform = `rotate(${Math.atan2(n.y - o.y, n.x - o.x) + Math.PI / 2}rad)`;
  }

  measure();
  return { update, measure };
}
```

- [ ] **Step 3: `frontend/src/style.css`**

```css
[hidden] { display: none !important; }

html, body { margin: 0; background: transparent; }
body {
  font-family: "Figtree", system-ui, -apple-system, "Segoe UI", sans-serif;
  color: #1E2A2F;
  -webkit-font-smoothing: antialiased;
}

.gm-map {
  position: relative;
  width: 100%;
  min-width: 320px;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: 16px;
  background: radial-gradient(120% 90% at 50% 40%, #F7FBFF 0%, #DCEBF5 100%);
}
.gm-map canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }

/* loading / error */
.gm-status {
  position: absolute; inset: 0; z-index: 2;
  display: grid; place-content: center; justify-items: center; gap: 14px;
  padding-inline: 16px; text-align: center; font-size: 14px; color: #4A5A60;
}
.gm-slab {
  width: min(46%, 320px); aspect-ratio: 2 / 1; background: #CFE8B9;
  clip-path: polygon(50% 0, 100% 50%, 50% 100%, 0 50%);
  animation: gm-breathe 1.6s ease-in-out infinite;
}
.gm-status.is-error .gm-slab { animation: none; filter: grayscale(0.6); opacity: 0.6; }
.gm-status button {
  font: inherit; font-weight: 600; color: #fff; background: #FF5A5F;
  border: 0; border-radius: 999px; padding: 8px 18px; cursor: pointer;
}
.gm-status button:focus-visible { outline: 3px solid #1E2A2F; outline-offset: 2px; }
@keyframes gm-breathe { 50% { transform: scale(0.94); opacity: 0.7; } }

/* overlay */
.gm-overlay { position: absolute; inset: 0; pointer-events: none; }
.gm-overlay > div { position: absolute; left: 0; top: 0; white-space: nowrap; will-change: transform; }
.gm-icon {
  display: inline-grid; place-items: center; flex: none;
  width: 22px; height: 22px; border-radius: 50%; background: var(--c);
}
.gm-icon svg, .gm-pin svg, .gm-arrow svg, .gm-needle svg {
  width: 13px; height: 13px; fill: none; stroke: #fff;
  stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round;
}

.gm-tag {
  font-family: "Fredoka", "Figtree", system-ui, sans-serif; font-weight: 600;
  font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase;
  color: #fff; background: #FF5A5F; padding: 4px 10px 5px; border-radius: 999px;
  box-shadow: 0 4px 12px rgba(255, 90, 95, 0.35);
}
.gm-tag::after {
  content: ""; position: absolute; left: 50%; bottom: -5px; margin-left: -5px;
  border: 5px solid transparent; border-bottom: 0; border-top-color: #FF5A5F;
}

.gm-near {
  display: flex; align-items: center; gap: 5px; max-width: 220px;
  background: #fff; border-radius: 999px; padding: 2px 9px 2px 2px;
  font-size: 11.5px; box-shadow: 0 2px 8px rgba(30, 42, 47, 0.18);
}
.gm-near b { font-weight: 700; overflow: hidden; text-overflow: ellipsis; }
.gm-near em { font-style: normal; color: #5F6B6D; }

.gm-far {
  display: flex; align-items: center; gap: 7px;
  padding: 5px 8px 5px 5px; border-radius: 12px; font-size: 12px; line-height: 1.15;
  background: rgba(255, 255, 255, 0.94); box-shadow: 0 4px 14px rgba(40, 70, 100, 0.16);
}
.gm-far-text { display: grid; }
.gm-far b { font-weight: 700; }
.gm-far em { font-style: normal; color: #5F6B6D; font-variant-numeric: tabular-nums; }
.gm-arrow { display: inline-grid; place-items: center; }
.gm-arrow svg { width: 16px; height: 16px; stroke: #8A96A0; stroke-width: 2.6; }

.gm-address {
  left: 12px !important; top: auto !important; bottom: 12px;
  display: flex; align-items: center; gap: 6px; max-width: calc(100% - 24px);
  background: rgba(255, 255, 255, 0.9); border-radius: 999px; padding: 4px 12px 4px 6px;
  font-size: 12px; font-weight: 600; box-shadow: 0 2px 8px rgba(30, 42, 47, 0.12);
}
.gm-address span { overflow: hidden; text-overflow: ellipsis; }
.gm-pin { display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 50%; background: #FF5A5F; }

.gm-north {
  left: auto !important; right: 12px; top: 12px !important;
  display: grid; justify-items: center; gap: 1px;
  font: 700 11px "Fredoka", "Figtree", system-ui, sans-serif; color: #4A5A60;
}
.gm-needle { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: rgba(255, 255, 255, 0.9); }
.gm-needle svg { width: 16px; height: 16px; stroke: #FF5A5F; fill: #FF5A5F; stroke-width: 1.5; }

@media (prefers-reduced-motion: reduce) { .gm-slab { animation: none; } }
```

- [ ] **Step 4: `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="sk">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Okolie nehnuteľnosti</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fredoka:wght@600&family=Figtree:wght@500;600;700&display=swap" />
</head>
<body>
  <div id="map" class="gm-map">
    <div id="status" class="gm-status" role="status">
      <div class="gm-slab"></div>
      <p id="status-text">Načítavam okolie…</p>
      <button id="retry" type="button" hidden>Skúsiť znova</button>
    </div>
  </div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 5: `frontend/src/main.js`**

```js
import './style.css';
import { createStage } from './map/stage.js';
import { DEFAULT_COORDS, getCoordsFromURL, isFixture } from './url.js';

const mapEl = document.getElementById('map');
const statusEl = document.getElementById('status');
const statusText = document.getElementById('status-text');
const retryBtn = document.getElementById('retry');

function sceneUrl({ lat, lon }, fixture) {
  return `/api/scene?lat=${lat}&lon=${lon}${fixture ? '&fixture=true' : ''}`;
}

async function load() {
  statusEl.hidden = false;
  statusEl.classList.remove('is-error');
  statusText.textContent = 'Načítavam okolie…';
  retryBtn.hidden = true;
  const search = window.location.search;
  const coords = getCoordsFromURL(search) ?? DEFAULT_COORDS;
  try {
    const res = await fetch(sceneUrl(coords, isFixture(search)));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const scene = await res.json();
    createStage(mapEl, scene);
    statusEl.hidden = true;
  } catch (err) {
    console.error('genmap: scene load failed', err);
    statusEl.classList.add('is-error');
    statusText.textContent = 'Mapu sa nepodarilo načítať. Skúste to znova o chvíľu.';
    retryBtn.hidden = false;
  }
}

retryBtn.addEventListener('click', load);
load();
```

- [ ] **Step 6: Delete obsolete modules, run tests and build**

```bash
cd frontend
git rm -q src/animations.js src/frame.js src/frame.test.js src/infographic.js src/poi.js src/route.js src/ui.js src/colors.js src/geometry.js src/geometry.test.js src/scene.js src/main.test.js
npm test
npm run build
```
Expected: vitest all PASS. Vite build succeeds with no unresolved imports (a chunk-size warning for three.js is fine).

- [ ] **Step 7: Commit**

```bash
git add -A frontend/src frontend/index.html
git commit -m "feat(frontend): map-only widget — overlay labels, edge badges, loading/error states; remove old infographic"
```

---

### Task 9: Visual verification, tuning, docs

**Files:**
- Modify: `CLAUDE.md`, and small tuning edits in `frontend/src/palette.js` / `map/stage.js` if the screenshot shows problems.

- [ ] **Step 1: Run the app and time a cold live request**

```bash
.venv/bin/python src/api.py &          # backend on :8000
(cd frontend && npm run dev) &         # vite on :5173
rm -rf .cache/osm
time curl -s "localhost:8000/api/scene?lat=48.28646434486518&lon=17.27221245956356" -o /tmp/scene.json
```
Expected: under ~10 s, `warnings: []`, and around 8 POIs between `near_pois` and `far_pois`. A second identical request returns in under 1 s (cache).

- [ ] **Step 2: Screenshot fixture and live views**

```bash
chromium --headless=new --no-sandbox --enable-unsafe-swiftshader --use-angle=swiftshader \
  --window-size=1024,768 --virtual-time-budget=15000 --screenshot=shot_fixture.png "http://localhost:5173/?fixture=true"
chromium --headless=new --no-sandbox --enable-unsafe-swiftshader --use-angle=swiftshader \
  --window-size=400,300 --virtual-time-budget=15000 --screenshot=shot_narrow.png "http://localhost:5173/?fixture=true"
```
Check against mockup A:
- pastel colors, not washed out or too dark;
- property highlighted with pin and "Na predaj";
- far badges on the edges and not overlapping;
- near pills readable;
- 320–400 px view usable.

If the colors look washed out or too dark, adjust the light intensities in `stage.js` (hemisphere/sun multipliers) and re-check once.

- [ ] **Step 3: Update `CLAUDE.md`** to cover the new module structure (`osm.py`, `scene_builder.py`, and the frontend `map/` and `overlay/` folders), the pipeline, the POI table (the 8 categories with their tags and radii), the config example, and the removal of the legacy PNG renderer.

- [ ] **Step 4: Full test run and commit**

```bash
.venv/bin/python -m pytest -q && (cd frontend && npm test)
git add CLAUDE.md frontend/src
git commit -m "docs: update CLAUDE.md for playful isometric map; visual tuning"
```
