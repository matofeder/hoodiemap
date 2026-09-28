# Local Overpass (Slovakia extract) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve all OSM queries for places in Slovakia from a local Overpass instance built from the Geofabrik Slovakia extract, so cold map loads drop from 10–60 s to about a second, with automatic fallback to the public servers.

**Architecture:** A `docker-compose.yml` runs `wiktorn/overpass-api` initialised from `slovakia-latest.osm.pbf` (345 MB) and kept current with Geofabrik's daily diffs. The backend gets an `overpass` config section (local URL, public endpoints, local coverage bbox). `build_scene` picks the endpoint list per scene: local first when the centre is inside the coverage bbox, public only otherwise. If the local instance is down, the public endpoints are tried next (the existing fallback loop). If the local area answer is empty (a point inside the bbox but outside the extract, e.g. Miskolc), the scene is refetched from the public endpoints. Nominatim stays public (throttled + cached).

**Tech Stack:** Docker + docker-compose v2 (installed: Docker 29.1, Compose v2.40, used as `docker-compose`), `wiktorn/overpass-api`, Python 3.14 / FastAPI / httpx / pytest.

**Spec:** none — this plan is its own design record (agreed in chat on 2026-09-27: "local OSM, option (a) own Overpass in Docker, no data-model change"). Rulings made without a spec are provisional.

## Design notes (decisions and their costs)

- **Why Overpass in Docker, not PostGIS:** the backend's queries stay byte-identical, so the JSON cache, the tests and every query builder keep working; the change is a URL list. PostGIS would mean rewriting every query (area, POIs, street) — weeks, not hours.
- **Market = Slovakia only** (decided 2026-09-28: Slovakia is the first market). The geocoder is limited to `sk` (Task 0), which also fixes bare "Senec" resolving to Czechia.
- **Coverage = Slovakia bbox** `(47.73, 16.83, 49.61, 22.57)` (south, west, north, east). Points outside (only reachable via a hand-edited `?lat=&lon=` URL now) go straight to the public servers.
- **Known limitation:** the extract ends at the border (plus Geofabrik's small buffer). For a property in Slovakia, POIs and cities across the border are not found locally — e.g. from Bratislava the "Wien 55 km" city badge disappears, and near-border hospitals/stations abroad are not candidates. Accepted: this is a Slovak real-estate tool. If it matters later, add neighbouring extracts (Austria, Czechia, Hungary) or cut a buffered extract from the Europe file with `osmium extract`.
- **Freshness:** diffs are applied hourly (`OVERPASS_UPDATE_SLEEP=3600`) from Geofabrik's daily updates; the backend's 30-day JSON cache still applies on top.
- **Resources:** the database for Slovakia is a few GB (disk has 553 GB free); the initial import takes roughly 15–40 min on this machine (16 cores, 45 GB RAM) and runs once.

## Global Constraints

- Local endpoint URL: `http://localhost:12345/api/interpreter` (container port 80 published on host port 12345).
- Public endpoints unchanged and in this order: `https://overpass-api.de/api/interpreter`, `https://overpass.kumi.systems/api/interpreter`, `https://maps.mail.ru/osm/tools/overpass/api/interpreter`.
- Coverage bbox (south, west, north, east): `47.73, 16.83, 49.61, 22.57`.
- Extract: `https://download.geofabrik.de/europe/slovakia-latest.osm.pbf`; diffs: `https://download.geofabrik.de/europe/slovakia-updates/`.
- Overpass query strings must not change (the JSON cache is keyed by the query text).
- With the container stopped the app must behave exactly as today (public servers only, no errors beyond one refused connection per query).
- Backend tests: `.venv/bin/python -m pytest -q` from the repo root; no test may hit the network or require Docker.
- Commit messages end with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
    ```

## Review Focus

- Local container stopped → every query must still succeed via the public list; the refused connection must not add seconds (Task 2 test with a transport that refuses the local URL).
- A centre inside the bbox but outside the extract (Miskolc 48.10, 20.78) → the empty local answer must trigger the public refetch, not an empty map (Task 3 test).
- A centre outside the bbox (Brno) → local never contacted (Task 2 test).
- `overpass` section missing from an old `config.yaml` → defaults keep today's behaviour (public list only, no local) (Task 1 test).
- Local instance still importing (answers with HTTP 5xx or a "runtime error" remark) → treated like any failing endpoint, falls through to public (existing `run_query` behaviour; Task 2 test).

## File Structure

| File | Responsibility |
|---|---|
| `docker-compose.yml` (new) | the local Overpass service and its data volume |
| `docs/local-overpass.md` (new) | how to start, watch the import, update, reset |
| `src/config.py`, `config.yaml` | `overpass` section: `local_url`, `public_endpoints`, `local_bbox` |
| `src/osm.py` | `endpoints_for(lat, lon, overpass_cfg)`; `run_query`/`fetch_*` take an `endpoints` list |
| `src/scene_builder.py` | pass the per-scene endpoint list; empty-local-area refetch from public |
| `scripts/time_tiers.py` | unchanged; re-run for the acceptance numbers |
| `CLAUDE.md` | running notes + known limitation |

---

### Task 0: Geocoder limited to Slovakia

**Files:**
- Modify: `src/config.py`, `config.yaml`, `CLAUDE.md` (the `countrycodes` line in the config snippet)
- Test: `tests/test_config.py`

- [ ] **Step 1: Failing test** — add to `tests/test_config.py`:

```python
def test_geocode_limited_to_slovakia():
    from config import Config, LocationConfig
    assert Config(location=LocationConfig(lat=48.0, lon=17.0)).geocode.countrycodes == "sk"
    assert load_config(Path(__file__).parent.parent / "config.yaml").geocode.countrycodes == "sk"
```

- [ ] **Step 2:** run `.venv/bin/python -m pytest tests/test_config.py -v` → FAIL.
- [ ] **Step 3:** default `countrycodes: str = "sk"` in `src/config.py`; `countrycodes: "sk"` in `config.yaml` (comment: Slovakia is the target market); same in the `CLAUDE.md` config snippet. The geocode cache key already includes `countrycodes`, so old `sk,cz` entries are simply not reused.
- [ ] **Step 4:** `.venv/bin/python -m pytest -q` → all pass (fix any test that asserted `"sk,cz"`).
- [ ] **Step 5: Commit**

```bash
git add src/config.py config.yaml CLAUDE.md tests/
git commit -m "feat(geocode): limit search to Slovakia, the target market" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 1: Config — `overpass` section

**Files:**
- Modify: `src/config.py`, `config.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `cfg.overpass.local_url: str | None` (default `None` = no local instance), `cfg.overpass.public_endpoints: list[str]` (default = today's three), `cfg.overpass.local_bbox: tuple[float, float, float, float]` (default the Slovakia bbox).

- [ ] **Step 1: Write the failing tests** — add to `tests/test_config.py`:

```python
def test_overpass_defaults_keep_todays_behaviour():
    from config import Config, LocationConfig
    cfg = Config(location=LocationConfig(lat=48.0, lon=17.0))
    assert cfg.overpass.local_url is None
    assert cfg.overpass.public_endpoints == [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]
    assert cfg.overpass.local_bbox == (47.73, 16.83, 49.61, 22.57)


def test_repo_config_enables_local_overpass():
    cfg = load_config(Path(__file__).parent.parent / "config.yaml")
    assert cfg.overpass.local_url == "http://localhost:12345/api/interpreter"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL (`Config` has no attribute `overpass`).

- [ ] **Step 3: Implement** — `src/config.py`:

```python
PUBLIC_OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


class OverpassConfig(BaseModel):
    local_url: str | None = None  # None: public servers only
    public_endpoints: list[str] = Field(default_factory=lambda: list(PUBLIC_OVERPASS))
    local_bbox: tuple[float, float, float, float] = (47.73, 16.83, 49.61, 22.57)  # S, W, N, E of the extract
```

and in `Config`: `overpass: OverpassConfig = Field(default_factory=OverpassConfig)`.

`config.yaml` — append:

```yaml
overpass:
  local_url: "http://localhost:12345/api/interpreter"   # docker-compose up -d overpass; null = public only
  local_bbox: [47.73, 16.83, 49.61, 22.57]             # Slovakia extract (S, W, N, E); outside -> public servers
```

- [ ] **Step 4: Run tests** — `.venv/bin/python -m pytest -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add src/config.py config.yaml tests/test_config.py
git commit -m "feat(config): overpass section — local URL, public endpoints, local coverage bbox" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Endpoint selection and pass-through in `osm.py`

**Files:**
- Modify: `src/osm.py`, `tests/test_osm.py`

**Interfaces:**
- Consumes: `OverpassConfig` (Task 1).
- Produces:
  - `osm.endpoints_for(lat: float, lon: float, ocfg) -> list[str]` — `[local_url, *public]` when `local_url` is set and the point is inside `local_bbox`, else `public` only.
  - `run_query(query, cache_dir, transport=None, timeout_s=TIMEOUT_S, stats=None, endpoints=None)` — `endpoints=None` means the module default `ENDPOINTS` (today's list).
  - `fetch_area(..., endpoints=None)`, `fetch_pois(..., endpoints=None)`, `fetch_street(..., endpoints=None)` — passed straight to `run_query`.
  - `run_query` no longer caches an answer whose `elements` list is empty (an empty local answer may only mean "outside the extract"; caching it would hide the public data later — the query text, i.e. the cache key, is the same for both).

- [ ] **Step 1: Write the failing tests** — add to `tests/test_osm.py`:

```python
from config import OverpassConfig
from osm import endpoints_for

LOCAL = "http://localhost:12345/api/interpreter"


def test_endpoints_local_first_inside_coverage_public_only_outside():
    ocfg = OverpassConfig(local_url=LOCAL)
    assert endpoints_for(48.2865, 17.2722, ocfg) == [LOCAL, *ocfg.public_endpoints]   # Pezinok
    assert endpoints_for(49.1951, 16.6068, ocfg) == ocfg.public_endpoints             # Brno
    assert endpoints_for(48.2865, 17.2722, OverpassConfig()) == OverpassConfig().public_endpoints


def test_run_query_uses_given_endpoints_and_falls_through_a_refused_local():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if str(request.url).startswith(LOCAL):
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json={"elements": [1]})

    out = run_query("q", None, transport=httpx.MockTransport(handler), endpoints=[LOCAL, "https://pub.example/api"])
    assert out == {"elements": [1]}
    assert calls == [LOCAL, "https://pub.example/api"]


def test_run_query_treats_an_importing_local_instance_as_failed():
    def handler(request):
        if str(request.url).startswith(LOCAL):
            return httpx.Response(200, json={"remark": "runtime error: database not ready", "elements": []})
        return httpx.Response(200, json={"elements": [2]})

    assert run_query("q", None, transport=httpx.MockTransport(handler),
                     endpoints=[LOCAL, "https://pub.example/api"]) == {"elements": [2]}


def test_empty_answers_are_not_cached(tmp_path):
    calls = []
    t = _transport([(200, {"elements": []}), (200, {"elements": [3]})], calls)
    assert run_query("q", str(tmp_path), transport=t) == {"elements": []}
    assert run_query("q", str(tmp_path), transport=t) == {"elements": [3]}   # second call went to the network
    assert len(calls) == 2


def test_fetchers_pass_endpoints_through(monkeypatch):
    seen = []
    monkeypatch.setattr(osm, "run_query", lambda q, cache, **kw: seen.append(kw.get("endpoints")) or {"elements": []})
    osm.fetch_area(48.0, 17.0, 140, None, endpoints=["x"])
    osm.fetch_pois(48.0, 17.0, ["pharmacy"], None, endpoints=["y"])
    osm.fetch_street("Hlavná", 48.0, 17.0, None, endpoints=["z"])
    assert seen == [["x"], ["y"], ["z"]]
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_osm.py -v`
Expected: FAIL (`endpoints_for` missing; unexpected `endpoints` keyword).

- [ ] **Step 3: Implement** in `src/osm.py`:

```python
def endpoints_for(lat: float, lon: float, ocfg) -> list[str]:
    """Local Overpass first when the point is inside its extract's bbox; public servers otherwise/after."""
    south, west, north, east = ocfg.local_bbox
    inside = south <= lat <= north and west <= lon <= east
    if ocfg.local_url and inside:
        return [ocfg.local_url, *ocfg.public_endpoints]
    return list(ocfg.public_endpoints)
```

In `run_query` add the keyword `endpoints: list[str] | None = None` and iterate `for url in endpoints or ENDPOINTS:`; change the cache write condition from `if cache_dir:` to `if cache_dir and data.get("elements"):` (errors and remarks behave as today). Add `endpoints: list[str] | None = None` as the last keyword of `fetch_area`, `fetch_pois`, `fetch_street` and pass `endpoints=endpoints` to `run_query`.

- [ ] **Step 4: Run tests** — `.venv/bin/python -m pytest -q` → all pass (existing positional callers unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/osm.py tests/test_osm.py
git commit -m "feat(osm): per-scene endpoint list with local Overpass first inside its coverage" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `build_scene` uses the endpoint list; empty local area → public refetch

**Files:**
- Modify: `src/scene_builder.py`, `tests/test_assemble.py`

**Interfaces:**
- Consumes: `endpoints_for`, `fetch_*(..., endpoints=)` (Task 2); `cfg.overpass` (Task 1).
- Produces: `build_scene` behaviour only (signature unchanged). Adds `"public_fallback"` to `warnings` when the local area answer was empty and the scene was refetched from the public servers.

- [ ] **Step 1: Write the failing tests** — add to `tests/test_assemble.py`:

```python
def _cfg_with_local(default_config):
    from config import OverpassConfig
    return default_config.model_copy(update={"overpass": OverpassConfig(local_url="http://local/api")})


def test_build_scene_sends_local_first_inside_slovakia(monkeypatch, default_config):
    seen = []

    def fake_area(*a, endpoints=None, **k):
        seen.append(endpoints)
        return {"elements": [way(rect(0, 0, 10, 10), {"building": "house"})]}

    monkeypatch.setattr(scene_builder, "fetch_area", fake_area)
    monkeypatch.setattr(scene_builder, "fetch_pois", lambda *a, **k: {"elements": []})
    build_scene(LAT0, LON0, _cfg_with_local(default_config))
    assert seen[0][0] == "http://local/api"


def test_empty_local_area_is_refetched_from_public(monkeypatch, default_config):
    seen = []

    def fake_area(*a, endpoints=None, **k):
        seen.append(endpoints)
        local = endpoints[0] == "http://local/api"
        return {"elements": [] if local else [way(rect(0, 0, 10, 10), {"building": "house"})]}

    monkeypatch.setattr(scene_builder, "fetch_area", fake_area)
    monkeypatch.setattr(scene_builder, "fetch_pois", lambda *a, **k: {"elements": []})
    s = build_scene(LAT0, LON0, _cfg_with_local(default_config))
    assert len(seen) == 2 and seen[1][0] != "http://local/api"
    assert len(s["buildings"]) == 1
    assert "public_fallback" in s["warnings"]


def test_no_local_configured_means_no_refetch(monkeypatch, default_config):
    calls = []
    monkeypatch.setattr(scene_builder, "fetch_area", lambda *a, **k: calls.append(1) or {"elements": []})
    monkeypatch.setattr(scene_builder, "fetch_pois", lambda *a, **k: {"elements": []})
    build_scene(LAT0, LON0, default_config)
    assert calls == [1]
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -v`
Expected: FAIL (endpoints never passed; no refetch).

- [ ] **Step 3: Implement** in `src/scene_builder.py`:

- import `endpoints_for` from `osm`;
- at the start of `build_scene`: `endpoints = endpoints_for(lat, lon, cfg.overpass)` and `public = list(cfg.overpass.public_endpoints)`;
- pass `endpoints=endpoints` to `fetch_street`, `fetch_area` and `fetch_pois` (keyword, after the existing positional arguments);
- after `area = area_job.result()` and the POI result handling, add:

```python
    # A point can lie inside the local extract's bbox but outside the extract itself (e.g. Miskolc):
    # an empty local answer means "no data here", not "nothing here" — ask the public servers.
    # (run_query never caches empty answers, so the public refetch is not shadowed by the cache.)
    local = cfg.overpass.local_url
    if local and endpoints[0] == local and not area.get("elements"):
        area = fetch_area(lat, lon, radius, cache_dir, tier == "city", stats, endpoints=public)
        try:
            pois_raw = fetch_pois(lat, lon, categories, cache_dir, radius, stats, endpoints=public)
        except OverpassError:
            pois_raw = {"elements": []}
        warnings.append("public_fallback")
```

- [ ] **Step 4: Run tests** — `.venv/bin/python -m pytest -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add src/scene_builder.py tests/test_assemble.py
git commit -m "feat(scene): local Overpass per scene, public refetch when the local extract has no data" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Docker service, import, and the acceptance timing

**Files:**
- Create: `docker-compose.yml`, `docs/local-overpass.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Verify the image's settings before writing the compose file**

Run: `docker run --rm --entrypoint sh wiktorn/overpass-api -c 'grep -o "OVERPASS_[A-Z_]*" /app/docker-entrypoint.sh | sort -u'`
Expected: the list contains at least `OVERPASS_MODE`, `OVERPASS_META`, `OVERPASS_PLANET_URL`, `OVERPASS_DIFF_URL`, `OVERPASS_PLANET_PREPROCESS`, `OVERPASS_COMPRESSION`, `OVERPASS_RULES_LOAD`, `OVERPASS_UPDATE_SLEEP`, `OVERPASS_USE_AREAS`, `OVERPASS_MAX_TIMEOUT`. If a name differs, use the image's name in Step 2 and note it in the report.

- [ ] **Step 2: `docker-compose.yml`**

```yaml
# Local Overpass API for Slovakia — see docs/local-overpass.md
services:
  overpass:
    image: wiktorn/overpass-api:latest
    container_name: hoodiemap-overpass
    ports:
      - "12345:80"
    volumes:
      - overpass-db:/db
    environment:
      OVERPASS_MODE: init
      OVERPASS_META: "no"
      OVERPASS_PLANET_URL: https://download.geofabrik.de/europe/slovakia-latest.osm.pbf
      OVERPASS_DIFF_URL: https://download.geofabrik.de/europe/slovakia-updates/
      # the image imports .osm.bz2; convert the Geofabrik .pbf first
      OVERPASS_PLANET_PREPROCESS: >-
        mv /db/planet.osm.bz2 /db/planet.osm.pbf &&
        osmium cat -o /db/planet.osm.bz2 /db/planet.osm.pbf &&
        rm /db/planet.osm.pbf
      OVERPASS_COMPRESSION: gz
      OVERPASS_RULES_LOAD: "10"
      OVERPASS_UPDATE_SLEEP: "3600"
      OVERPASS_USE_AREAS: "false"
      OVERPASS_MAX_TIMEOUT: "120s"
    restart: unless-stopped

volumes:
  overpass-db:
```

- [ ] **Step 3: `docs/local-overpass.md`** — contents:

```markdown
# Local Overpass (Slovakia)

Start (first run downloads 345 MB and imports; expect 15–40 min):

    docker-compose up -d overpass
    docker-compose logs -f overpass        # wait for "Overpass API ready" / dispatcher started

Check:

    curl -s 'http://localhost:12345/api/interpreter?data=[out:json];node(48.28,17.26,48.29,17.28)[amenity=pharmacy];out;' | head

Updates are applied hourly from Geofabrik's daily diffs. Stop: `docker-compose stop overpass`
(the app then uses the public servers). Rebuild from scratch: `docker-compose down -v && docker-compose up -d`.

Coverage: Slovakia only (`overpass.local_bbox` in config.yaml). Places across the border
(e.g. Wien as a city badge from Bratislava) are not found locally. Points outside the bbox
use the public servers; points inside the bbox but outside the extract fall back to them
automatically (`warnings: ["public_fallback"]`).
```

- [ ] **Step 4: Start and import**

Run: `docker-compose up -d overpass`, then poll `docker-compose logs --tail 20 overpass` every few minutes until the API answers the check query from the doc (Step 3). Record the import duration and `docker system df -v | grep overpass-db` (volume size).

- [ ] **Step 5: Acceptance timing** — clear only the OSM cache so every query is cold, then time:

Run:
```bash
mv .cache/osm .cache/osm.before-local
.venv/bin/python scripts/time_tiers.py
```
Expected: first run — every Slovak query (all except none; all five are in Slovakia) with `total` under ~3 s; second run all `cached=True`. Record both runs verbatim. Then restore the old cache only if something failed: `rm -rf .cache/osm && mv .cache/osm.before-local .cache/osm` (otherwise delete `.cache/osm.before-local`).

Also verify the fallback: `docker-compose stop overpass`, `mv .cache/osm .cache/osm.tmp`, run `curl -s "localhost:8000/api/scene?lat=48.2865&lon=17.2722" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['buildings']))"` → a non-zero building count (served by the public servers); then `rm -rf .cache/osm && mv .cache/osm.tmp .cache/osm` and `docker-compose start overpass`.

- [ ] **Step 6: `CLAUDE.md`** — under "Running the App" add the two lines `docker-compose up -d overpass   # local Overpass for Slovakia (optional, see docs/local-overpass.md)`; under "Known risks" replace the "Public Overpass servers are often overloaded" bullet with: local Overpass serves Slovakia in ~1 s; outside Slovakia or with the container stopped the public servers are used (10–60 s cold); cross-border POIs/cities are not found locally.

- [ ] **Step 7: Run everything and commit**

Run: `.venv/bin/python -m pytest -q` → all pass.

```bash
git add docker-compose.yml docs/local-overpass.md CLAUDE.md
git commit -m "feat: local Overpass service for Slovakia (docker-compose) with docs and timing" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
