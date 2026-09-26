# genmap — Playful Isometric Map

**Date:** 2026-09-26
**Status:** Draft, awaiting review
**Visual reference:** style mockup A "Pastelová izometria" — https://claude.ai/artifact/J56ciWjYW7PPxvaCZv4yn7

---

## Why

The current output (dense brown 3D city, ~1,300 identical buildings, 450 m radius, side panels) does not read as an infographic. Live data is also broken in practice: one `/api/scene` request took 4 min 14 s, Overpass returned 406 / "server load too high" for most POI queries, and only 2 of 8 POI categories arrived. Every inner POI showed direction "N" because `bearing_deg` is never sent for inner POIs.

## Goal

An attractive, lightweight, playful (not realistic) interactive widget that:

- shows only the immediate surroundings of a property for sale (a few streets, ±140 m),
- uses real OSM streets and building footprints, drawn in a stylized pastel isometric look,
- marks POIs inside the view directly on the map,
- hints POIs outside the view as badges on the map edge, placed in their direction, with distance in km ("Nemocnica · 2,4 km →"),
- loads in seconds, not minutes.

Success: a real estate agent would put it into a listing as is. It loads in under ~10 s cold and instantly from cache, and shows every POI category that exists within its search radius.

## Non-goals

- Travel time in minutes (straight-line distance only; minutes may come later).
- Side panels, transport strip, route hints, share links.
- Static image / PDF export (Stage 4, separate spec).
- User camera control (no orbit, no zoom).

---

## 1. Data (backend)

### 1.1 Fetching — new `src/osm.py`

Replaces `fetcher.py` and the `osmnx` / `overpy` / `geopandas` stack. Talks to Overpass directly with `httpx` (sync client, run in a thread from FastAPI as today).

- Header `User-Agent: genmap/1.0 (neighbourhood-map)` on every request (fixes the 406).
- Endpoints tried in order: `overpass-api.de`, `overpass.kumi.systems`, `maps.mail.ru`. Timeout 25 s per endpoint. First successful JSON response wins.
- Raises `OverpassError` when all endpoints fail.

**Query 1 — area** (bbox = display square + 20 m margin), `[out:json][timeout:25]`, `out geom;`:

| Layer    | Selector |
|----------|----------|
| building | `way["building"]`, `relation["building"]` |
| road     | `way["highway"]` |
| park     | `way/relation["leisure"~"^(park|garden|playground)$"]`, `["landuse"~"^(grass|meadow|recreation_ground|village_green)$"]` |
| water    | `way/relation["natural"="water"]`, `["waterway"="riverbank"]` |
| forest   | `way/relation["landuse"="forest"]`, `["natural"="wood"]` |
| tree     | `node["natural"="tree"]` |

Relations are handled by taking the geometry of their `outer` members.

**Query 2 — POIs**, one union query with per-category `around:` radius, `out center tags;`:

| Category     | OSM selector | Search radius |
|--------------|--------------|---------------|
| hospital     | `amenity=hospital` | 30 km |
| supermarket  | `shop=supermarket` | 5 km |
| school       | `amenity=school` | 5 km |
| kindergarten | `amenity=kindergarten` | 5 km |
| pharmacy     | `amenity=pharmacy` | 5 km |
| bus_stop     | `highway=bus_stop` | 3 km |
| train        | `railway~"^(station|halt)$"` | 30 km |
| park         | `leisure~"^(park|playground)$"` | 3 km |

Only categories enabled in `config.yaml` are queried. For each category the backend keeps only the single nearest result (haversine).

### 1.2 Cache

- JSON files in `<cache.dir>/osm/<sha256(query)[:16]>.json`, holding `{"fetched_at": ..., "data": ...}`.
- TTL 30 days; stale or unreadable files are ignored and refetched.
- Coordinates are rounded to 6 decimals inside the query text, so the same location hits the same key.
- `cache.enabled: false` bypasses read and write.

### 1.3 Scene building — rewritten `src/scene_builder.py`

**Local projection:** equirectangular around the center, `x = Δlon · cos(lat₀) · 111 320`, `y = Δlat · 110 540` (metres, x east, y north). Error is negligible at 140 m. `pyproj` is no longer needed.

**Clipping:** every polygon and line is clipped with `shapely` to the display square `[-r, r]²`. Buildings whose clipped area is < 40 % of the original are dropped, to avoid sliced stubs on the edge. Empty results are dropped.

**Building classification** (`kind`):

| kind | Rule (first match wins) |
|------|------|
| civic | `building` ∈ {school, kindergarten, church, chapel, hospital, public, civic, government, train_station} |
| commercial | `building` ∈ {retail, commercial, office, supermarket, industrial, warehouse, hotel} |
| other | `building` ∈ {garage, garages, shed, roof, carport, hut, service} |
| house | `building` ∈ {house, detached, semidetached_house, terrace, bungalow} or (`building` ∈ {yes, residential} and levels ≤ 2 and footprint area < 250 m²) |
| apartment | everything else (apartments; yes/residential with levels ≥ 3 or area ≥ 250 m²) |

**Height (walls, excluding roof):** `height` tag if parseable → else `building:levels × 3 m` → else default by kind: house 6, apartment 12, commercial 8, civic 10, other 3.

**Road kind:**

| kind | `highway` values |
|------|------|
| main | primary, secondary, tertiary and their `_link` variants |
| street | residential, unclassified, living_street, service, road |
| path | footway, path, cycleway, pedestrian, steps, track |

Other values (e.g. construction, proposed) are dropped.

**Property building:** the building whose footprint contains the center point. If there is none, the nearest building within 15 m. Otherwise `null`.

**Near vs. far POIs:** a category's nearest POI goes to `near_pois` if its local (x, y) lies inside the display square minus a 10 m inset, otherwise to `far_pois` with `bearing_deg` (computed by `geo.compute_bearing`). A category never appears in both lists.

### 1.4 Scene JSON — `GET /api/scene?lat=…&lon=…`

```json
{
  "center": {"lat": 48.2864, "lon": 17.2722},
  "address": "Záhradná, Pezinok",
  "radius_m": 140,
  "buildings": [{"footprint": [[x, y], ...], "kind": "house", "height": 6.0}],
  "property": {"building_index": 12},
  "roads": [{"points": [[x, y], ...], "kind": "main"}],
  "areas": {"park": [[[x, y], ...]], "water": [], "forest": []},
  "trees": [{"x": 10.2, "y": -4.1}],
  "near_pois": [{"category": "pharmacy", "name": "Lekáreň Pod Lipou", "distance_m": 48, "x": 30.1, "y": -38.4}],
  "far_pois": [{"category": "hospital", "name": "Nemocnica Pezinok", "distance_m": 2412, "bearing_deg": 34.8}],
  "warnings": []
}
```

`property.building_index` is `null` when no building matched. Coordinates are rounded to 0.1 m, and footprints drop the closing duplicate point.

### 1.5 Error handling

- Area query fails on all endpoints → HTTP 502, `{"detail": "Could not load map data from OpenStreetMap. Try again in a minute."}`.
- POI query fails → the scene is still returned with empty POI lists and `warnings: ["poi_fetch_failed"]`.
- Reverse geocode (Nominatim) fails → `address` falls back to `"lat, lon"` (unchanged from today).
- `?fixture=true` keeps working and serves `fixtures/pezinok-centrum.json`, regenerated in the new format by an updated `scripts/capture_fixture.py`.

### 1.6 Config changes (`config.yaml`, `config.py`)

```yaml
radii:
  display_meters: 140

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
```

Removed: `radii.fetch_meters` (search radii are per category, see 1.1), `poi.max_per_category`, and the `output` section.

### 1.7 Removals

- `src/fetcher.py`, `src/renderer.py`, `src/genmap.py`, `src/styles.py` (legacy PNG pipeline and old palettes).
- API endpoints `/api/route`, `/api/scene/share`, `/view/{id}`. `/api/geocode` stays.
- Dependencies: `osmnx`, `overpy`, `geopandas`, `matplotlib`, `Pillow`. `shapely` stays.
- `geo.py` keeps `haversine_m` and `compute_bearing`. Unused helpers are removed.

---

## 2. Visual (frontend)

Three.js (existing `three@^0.168` npm dependency). World mapping: backend (x, y) → Three (x, 0, −y).

### 2.1 Stage

- **Ground slab:** box `2r × 10 × 2r`, top `#CFE8B9`, sides `#B4D39C`, top surface at y = 0.
- **Camera:** `OrthographicCamera`, position direction (190, 215, 250) looking at the origin. The frustum is fitted so the slab plus a badge margin fits: `halfH = max(0.8·r, 1.22·r / aspect)`.
- **Lights:** hemisphere light (`#FFFFFF` / `#B7C9A8`, 0.72) + directional sun (`#FFF6E8`, 0.7) from (90, 160, 60) with a 2048² PCF soft shadow map covering the slab.
- **Materials:** `MeshLambertMaterial`, cached per color.
- **Background:** CSS radial gradient `#F7FBFF → #DCEBF5` behind a transparent canvas.
- **North arrow:** a small HTML element in the top-right corner, rotated to the projected north direction.

### 2.2 Ground layers

Each layer sits slightly above the previous one to avoid z-fighting:

- Areas: park `#B9E0A0`, forest `#9CCB86`, water `#8FD3F4`.
- Roads: cream `#FBF6EC` ribbons (main 9 m, street 6 m, path 2.5 m), with round joins drawn as discs at the vertices. Main roads get a yellow `#F6C85F` dashed center line. Paths are drawn as dashes rather than a continuous ribbon.

### 2.3 Buildings

- Extruded footprint up to `height`.
- Wall colors: `#FFF4E6 #FDE2E4 #E3F1EC #E2E8FD #FFF6CC`. Roof colors: `#F28482 #F6BD60 #84A59D #8E9AAF #E07A5F`. Colors are picked by a stable hash of the footprint centroid.
- Roofs (`roofs.js`) use the footprint's minimum-area oriented rectangle (OBR):
  - `house` whose area / OBR area ≥ 0.8 → **gable** roof on the OBR, ridge along the long side, height 0.45 × short side, 0.6 m overhang.
  - `house` otherwise → **hip** (pyramid) roof on the OBR, height 0.3 × short side.
  - `apartment`, `commercial`, `civic` → **flat** roof: the top 1 m of the footprint extrusion is drawn in the roof color as a cap.
  - `other` → flat with no cap; walls `#E9E4DA`.
- All building meshes cast and receive shadows.

### 2.4 Trees

- "Lollipop" trees: trunk (`#A1785C`, 3 m) plus a sphere crown in one of `#86C98A #A1D9B4 #6DB57A`, radius 2.6–4.5 m.
- Sources: OSM tree nodes, plus seeded fill inside parks (1 per 180 m²) and forest (1 per 60 m²). Seeded trees skip points within 3 m of a building or road.
- The seed is derived from center lat/lon, so layouts are stable across reloads.

### 2.5 Property

- The building at `property.building_index` gets white walls and a `#FF5A5F` roof.
- A pulsing ring (scale 0.7 → 1.8, fading) sits on the ground around its centroid.
- A map-pin mesh (sphere + cone, `#FF5A5F`) bobs above it.
- An HTML tag **"Na predaj"** floats above the pin.
- With no property building, the pin and ring sit on the center point.

### 2.6 Labels (HTML overlay, `overlay/`)

- Positioned each frame by projecting world points with the camera. `pointer-events: none`.
- **Near POI:** white pill with a colored icon circle, name (category label when the name is missing) and distance, anchored at the POI's world point, 16 m above ground.
- **Far POI badge (`edge.js`):**
  - Content: white card with icon, title and distance, plus an arrow rotated to the screen direction.
  - Title is the POI name when present and ≤ 14 characters, otherwise the category label.
  - Screen direction: project `center` and `center + 80 m in bearing direction`, then normalize the difference.
  - Placement: intersect the ray from the projected center with the container rectangle inset by the badge half-size + 10 px.
  - Overlap resolution: any two overlapping badges are pushed apart along their axis of least overlap until no overlap remains, at most 20 iterations, clamped to the inset rectangle.
- **Address chip:** "📍 Záhradná, Pezinok" in the bottom-left corner.

Category labels (Slovak) and colors:

| category | label | color |
|----------|-------|-------|
| hospital | Nemocnica | `#E05252` |
| supermarket | Supermarket | `#3E9E6B` |
| school | Škola | `#4A90D9` |
| kindergarten | Škôlka | `#F2A541` |
| pharmacy | Lekáreň | `#3AAFA9` |
| bus_stop | Zastávka | `#7B5EA7` |
| train | Stanica | `#7F8C8D` |
| park | Park | `#5FAF6E` |

**Distance format (`format.js`):**
- First round the distance to 10 m. If the result is < 1000 → `"350 m"`.
- Otherwise round the km value to one decimal. If that is < 10, show it with a Slovak decimal comma (`"2,4 km"`); if it is ≥ 10, show a whole number (`"25 km"`).
- Examples: 995 m → `"1,0 km"`, 9 950 m → `"10 km"`.

### 2.7 Motion

- **Cars:** 1 per 60 m of main + street road length, max 6. Each drives along a road polyline at 8–14 m/s, offset 2 m to the right lane, and loops. Colors: `#FF7B7B #5CA8FF #FFC94D #9C7CF4`.
- **Other motion:** pin bob (±1.6 m), ring pulse, tree crown sway (sideways offset of 4 % of crown height).
- **Pausing:** the render loop stops when an `IntersectionObserver` reports the widget off-screen, and when the tab is hidden.
- **Reduced motion:** with `prefers-reduced-motion: reduce`, one frame is rendered, plus a re-render on resize.

---

## 3. Widget

- `index.html` contains only the map container. The container fills its parent width at a 4:3 aspect ratio, minimum width 320 px. The page body has no chrome.
- **Embedding:** `<iframe src="https://<host>/?lat=…&lon=…" style="width:100%;aspect-ratio:4/3;border:0">`.
- **Loading state:** empty slab silhouette (CSS) with the text "Načítavam okolie…".
- **Error state:** "Mapu sa nepodarilo načítať. Skúste to znova o chvíľu." with a "Skúsiť znova" button.
- A `ResizeObserver` refits the camera and re-places labels.

### Frontend structure

```
frontend/src/
  main.js            URL params, fetch, loading/error states, mount
  map/stage.js       renderer, camera fit, lights, render loop, visibility pause
  map/ground.js      slab, areas, roads
  map/buildings.js   walls + roof meshes, colors
  map/roofs.js       OBR computation, roof type choice, roof geometry
  map/trees.js       OSM + seeded trees
  map/cars.js        road-following cars
  map/property.js    highlight, ring, pin
  overlay/labels.js  "Na predaj" tag, near POI pills, address chip, north arrow
  overlay/edge.js    far POI badge placement + overlap resolution
  palette.js         all colors above
  icons.js           inline SVG icons per category
  format.js          distance formatting
  random.js          seeded PRNG
```

Removed: `animations.js`, `frame.js`, `infographic.js`, `poi.js`, `route.js`, `ui.js`, `colors.js`, `geometry.js`, `scene.js`, and their tests.

---

## 4. Testing

**Backend (pytest, no network):**
- `osm.py`: query text contains the enabled categories and radii; endpoint fallback on 406 / timeout (mocked `httpx` transport); `OverpassError` when all fail; cache hit, miss, TTL expiry, disabled.
- `scene_builder.py`, using recorded Overpass JSON fixtures in `tests/data/`:
  - local projection accuracy (±0.5 m against haversine at 140 m),
  - clipping and dropping of sliced buildings,
  - building classification and height rules (table-driven),
  - road kind mapping,
  - property building selection (containing, nearest ≤ 15 m, none),
  - nearest-per-category and near/far split,
  - `bearing_deg` present on all far POIs.
- `api.py`: scene 200 shape, 502 on area failure, `warnings` on POI failure, fixture mode.

**Frontend (vitest):**
- `format.js` (boundary cases: 995 m, 1000 m, 9 950 m, 25 000 m).
- `edge.js`: placement for bearings 0/90/180/270 in a known container; overlap resolution separates two badges 5° apart.
- `roofs.js`: OBR of a rotated rectangle; gable vs. hip choice at the 0.8 ratio.

**Visual verification:** headless Chromium screenshot of `?fixture=true` and of live Pezinok. Compare against mockup A and check that the live request completes in < 10 s cold.

## 5. Docs

Update `CLAUDE.md`: architecture, pipeline, POI table, config example, removed legacy renderer.
