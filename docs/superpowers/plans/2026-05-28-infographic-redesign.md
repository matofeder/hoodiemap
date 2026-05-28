# Infographic Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the current full-screen interactive 3D map into a fixed-canvas animated infographic: Three.js city as the visual centrepiece, flanked by real-data POI panels, a transport strip, and directional edge indicators for distant POIs. No camera controls, no search bar.

**Architecture:** The frontend switches from a full-screen app with search to a fixed 1200×760px infographic canvas. A new `infographic.js` module builds the surrounding DOM (header, POI panels, transport strip); `scene.js` drops `OrbitControls`/`CSS2DRenderer` and uses a fixed camera. Two new backend pieces: `fetch_transport()` adds bus/bike/parking/train data, and `/api/scene` gains a reverse-geocoded `address` field. Cyclists already exist in `animations.js` — no change needed there.

**Tech Stack:** Python 3.12, FastAPI, httpx, overpy · Three.js r168+, Vite 5, vanilla JS · pytest, pytest-asyncio, vitest

---

## File Map

```
src/
  fetcher.py          modify  — add fetch_transport()
  scene_builder.py    modify  — add transport key to SceneJSON
  api.py              modify  — add address reverse-geocode after build_scene()

frontend/
  src/
    poi.js            modify  — strip CSS2D labels + click handler, keep spheres
    scene.js          modify  — remove OrbitControls/CSS2DRenderer, fix camera
    infographic.js    create  — builds infographic DOM (header, panels, strip)
    main.js           rewrite — simplified boot: fetchScene → infographic → scene
  index.html          rewrite — new infographic layout + CSS, no search bar

tests/
  test_scene_builder.py  modify  — add test for transport key
  test_api.py            modify  — update scene test + add address test
```

**Unchanged:** `animations.js` (cyclists already in), `frame.js`, `colors.js`, `geometry.js`, `route.js` (kept, just not called), `geo.py`, `config.py`, `styles.py`, `fetcher.py` existing functions.

---

## Task 1: `fetch_transport()` in `fetcher.py`

**Files:**
- Modify: `src/fetcher.py`
- Modify: `tests/test_scene_builder.py`

Transport query follows the same overpy/cache pattern as `fetch_pois`. Returns one nearest result per category.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_scene_builder.py` (after the existing imports block):

```python
def test_fetch_transport_returns_list(default_config):
    from fetcher import fetch_transport
    from geo import BBox
    from unittest.mock import patch, MagicMock

    bbox = BBox(north=48.29, south=48.28, east=17.28, west=17.26)

    with patch("fetcher.overpy.Overpass") as mock_overpass:
        mock_node = MagicMock()
        mock_node.lat = "48.287"
        mock_node.lon = "17.273"
        mock_node.tags = {"name": "Centrum"}
        mock_result = MagicMock()
        mock_result.nodes = [mock_node]
        mock_result.ways = []
        mock_result.relations = []
        mock_overpass.return_value.query.return_value = mock_result

        result = fetch_transport(default_config, bbox, 48.286, 17.272)

    assert isinstance(result, list)
    for item in result:
        assert "category" in item
        assert "name" in item
        assert "lat" in item
        assert "lon" in item


def test_fetch_transport_skips_empty_categories(default_config):
    from fetcher import fetch_transport
    from geo import BBox
    from unittest.mock import patch, MagicMock

    bbox = BBox(north=48.29, south=48.28, east=17.28, west=17.26)

    with patch("fetcher.overpy.Overpass") as mock_overpass:
        mock_result = MagicMock()
        mock_result.nodes = []
        mock_result.ways = []
        mock_result.relations = []
        mock_overpass.return_value.query.return_value = mock_result

        result = fetch_transport(default_config, bbox, 48.286, 17.272)

    assert result == []
```

- [ ] **Step 2: Run test — expect FAIL (ImportError)**

```bash
cd /home/mato/Dev/tf/genmap && pytest tests/test_scene_builder.py::test_fetch_transport_returns_list -v
```

Expected: `ImportError: cannot import name 'fetch_transport' from 'fetcher'`

- [ ] **Step 3: Add `TRANSPORT_TAGS` and `fetch_transport()` to `src/fetcher.py`**

Add after the `POI_TAGS` dict (around line 26):

```python
TRANSPORT_TAGS: dict[str, str] = {
    "bus_stop":     "highway=bus_stop",
    "bike_parking": "amenity=bicycle_parking",
    "parking":      "amenity=parking",
    "train":        "railway=station",
}
```

Add after `fetch_trees()` at the end of the file:

```python
def fetch_transport(cfg: Config, bbox: BBox, center_lat: float, center_lon: float) -> list[dict]:
    key = f"transport:{bbox.north:.5f}:{bbox.south:.5f}:{bbox.east:.5f}:{bbox.west:.5f}"
    cached = _cache_load(key, cfg.cache.dir, cfg.cache.enabled)
    if cached is not None:
        return cached

    results: list[dict] = []
    for category, osm_tag in TRANSPORT_TAGS.items():
        query = _build_overpass_query(bbox, osm_tag)
        for endpoint in _OVERPASS_ENDPOINTS:
            try:
                result = overpy.Overpass(url=endpoint).query(query)
                points = _extract_raw_points(result, category)
                if points:
                    nearest = min(
                        points,
                        key=lambda p: haversine_m(center_lat, center_lon, p[0], p[1]),
                    )
                    results.append({
                        "category": category,
                        "name": nearest[2],
                        "lat": nearest[0],
                        "lon": nearest[1],
                    })
                break
            except Exception as e:
                print(f"  [warn] transport {category} {endpoint}: {e}")
                time.sleep(1)

    _cache_save(key, results, cfg.cache.dir, cfg.cache.enabled)
    return results
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd /home/mato/Dev/tf/genmap && pytest tests/test_scene_builder.py::test_fetch_transport_returns_list tests/test_scene_builder.py::test_fetch_transport_skips_empty_categories -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/fetcher.py tests/test_scene_builder.py
git commit -m "feat: add fetch_transport() for bus/bike/parking/train OSM data"
```

---

## Task 2: `transport` key in `scene_builder.py`

**Files:**
- Modify: `src/scene_builder.py`
- Modify: `tests/test_scene_builder.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_scene_builder.py` after the existing tests:

```python
def test_build_scene_includes_transport_key(default_config):
    from scene_builder import build_scene
    from unittest.mock import patch, MagicMock
    import geopandas as gpd
    from shapely.geometry import Point
    from pyproj import CRS
    import networkx as nx

    lat, lon = 48.28646, 17.27221
    utm_crs = CRS.from_epsg(32633)
    center_gdf = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326").to_crs(utm_crs)
    cx = float(center_gdf.geometry.x.iloc[0])
    cy = float(center_gdf.geometry.y.iloc[0])

    G = nx.MultiDiGraph()
    G.graph["crs"] = utm_crs
    G.add_node(1, x=cx + 50, y=cy + 10)
    G.add_node(2, x=cx + 150, y=cy + 10)
    G.add_edge(1, 2, 0, highway="residential")

    mock_transport = [{"category": "bus_stop", "name": "Centrum", "lat": lat + 0.001, "lon": lon + 0.001}]

    with patch("scene_builder.fetch_street_network") as mock_net, \
         patch("scene_builder.fetch_geo_layers") as mock_geo, \
         patch("scene_builder.fetch_trees") as mock_trees, \
         patch("scene_builder.fetch_pois") as mock_pois, \
         patch("scene_builder.fetch_transport") as mock_tr, \
         patch("scene_builder.ox.project_graph") as mock_proj:

        mock_net.return_value = MagicMock()
        mock_proj.return_value = G
        mock_geo.return_value = {k: None for k in ["building", "water", "forest", "park", "residential", "railway"]}
        mock_trees.return_value = []
        mock_pois.return_value = []
        mock_tr.return_value = mock_transport

        result = build_scene(lat, lon, default_config)

    assert "transport" in result
    assert isinstance(result["transport"], list)
    assert len(result["transport"]) == 1
    t = result["transport"][0]
    assert t["category"] == "bus_stop"
    assert t["name"] == "Centrum"
    assert "x" in t and "y" in t and "distance_m" in t and "bearing_deg" in t
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd /home/mato/Dev/tf/genmap && pytest tests/test_scene_builder.py::test_build_scene_includes_transport_key -v
```

Expected: fails (no `transport` key in build_scene result yet)

- [ ] **Step 3: Update `src/scene_builder.py`**

Change the import line at the top from:
```python
from fetcher import fetch_geo_layers, fetch_pois, fetch_street_network, fetch_trees
```
to:
```python
from fetcher import fetch_geo_layers, fetch_pois, fetch_street_network, fetch_transport, fetch_trees
```

Add after the `trees = [...]` block (before the `return` statement):

```python
    transport_raw = fetch_transport(cfg, display_bbox, lat, lon)
    transport = []
    for tr in transport_raw:
        x, y = _latlon_to_local(tr["lat"], tr["lon"], cx, cy, utm_crs)
        transport.append({
            "category": tr["category"],
            "name": tr["name"],
            "x": round(x, 2),
            "y": round(y, 2),
            "lat": tr["lat"],
            "lon": tr["lon"],
            "distance_m": round(haversine_m(lat, lon, tr["lat"], tr["lon"])),
            "bearing_deg": round(compute_bearing(lat, lon, tr["lat"], tr["lon"]), 1),
        })
```

Add `"transport": transport,` to the return dict:

```python
    return {
        "center": {"lat": lat, "lon": lon},
        "display_radius_m": cfg.radii.display_meters,
        "bbox_m": cfg.radii.display_meters,
        "roads": roads,
        "buildings": buildings,
        "pois": inner_pois,
        "outer_pois": outer_pois,
        "trees": trees,
        "transport": transport,
        "geo_layers": geo_layers_out,
    }
```

- [ ] **Step 4: Run all scene_builder tests — expect PASS**

```bash
cd /home/mato/Dev/tf/genmap && pytest tests/test_scene_builder.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add src/scene_builder.py tests/test_scene_builder.py
git commit -m "feat: add transport key to SceneJSON (bus, bike, parking, train)"
```

---

## Task 3: `address` field via reverse geocode in `api.py`

**Files:**
- Modify: `src/api.py`
- Modify: `tests/test_api.py`

The `/api/scene` handler calls Nominatim `/reverse` after `build_scene()` returns, and merges an `address` string into the dict. Falls back to `"lat, lon"` on any error.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
@pytest.mark.asyncio
async def test_scene_endpoint_includes_address(sample_scene):
    from api import app
    mock_rg = {"address": {"road": "Hlavná ulica", "city": "Pezinok"}}
    with patch("api.build_scene", return_value=dict(sample_scene)):
        with patch("api.httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_rg
            mock_resp.raise_for_status = MagicMock()
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/scene?lat=48.28646&lon=17.27221")
    assert response.status_code == 200
    data = response.json()
    assert "address" in data
    assert data["address"] == "Hlavná ulica, Pezinok"


@pytest.mark.asyncio
async def test_scene_endpoint_address_fallback_on_geocode_error(sample_scene):
    from api import app
    with patch("api.build_scene", return_value=dict(sample_scene)):
        with patch("api.httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(side_effect=Exception("network error"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/scene?lat=48.28646&lon=17.27221")
    assert response.status_code == 200
    data = response.json()
    assert "address" in data
    assert "48.2865" in data["address"]
```

Also update `test_scene_endpoint_returns_scene_json` to mock httpx so it doesn't make real network calls. Replace the existing test body:

```python
@pytest.mark.asyncio
async def test_scene_endpoint_returns_scene_json(sample_scene):
    from api import app
    with patch("api.build_scene", return_value=dict(sample_scene)):
        with patch("api.httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"address": {"road": "Test", "city": "City"}}
            mock_resp.raise_for_status = MagicMock()
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/scene?lat=48.28646&lon=17.27221")
    assert response.status_code == 200
    data = response.json()
    assert data["center"]["lat"] == 48.28646
    assert "roads" in data and "buildings" in data
```

- [ ] **Step 2: Run new tests — expect FAIL**

```bash
cd /home/mato/Dev/tf/genmap && pytest tests/test_api.py::test_scene_endpoint_includes_address tests/test_api.py::test_scene_endpoint_address_fallback_on_geocode_error -v
```

Expected: both fail (no `address` key in response yet)

- [ ] **Step 3: Update `src/api.py` — add reverse geocode after `build_scene()`**

Replace the existing `/api/scene` handler body (the try/except block) with:

```python
@app.get("/api/scene")
async def scene(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    fixture: bool = False,
):
    if fixture:
        if not _FIXTURE_PATH.exists():
            raise HTTPException(
                status_code=404,
                detail="Fixture file not found. Run scripts/capture_fixture.py first.",
            )
        try:
            return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=500, detail="Fixture JSON is malformed.") from exc

    cfg = _get_cfg()
    try:
        data = await asyncio.to_thread(build_scene, lat, lon, cfg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "jsonv2"},
                headers={"User-Agent": "genmap/1.0 (neighbourhood-map)"},
            )
            resp.raise_for_status()
            rg = resp.json()
            addr = rg.get("address", {})
            road = addr.get("road") or addr.get("pedestrian") or addr.get("suburb") or ""
            city = addr.get("city") or addr.get("town") or addr.get("village") or ""
            data["address"] = ", ".join(p for p in [road, city] if p) or f"{lat:.4f}, {lon:.4f}"
    except Exception:
        data["address"] = f"{lat:.4f}, {lon:.4f}"

    return data
```

- [ ] **Step 4: Run all API tests — expect PASS**

```bash
cd /home/mato/Dev/tf/genmap && pytest tests/test_api.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "feat: add address field to /api/scene via Nominatim reverse geocode"
```

---

## Task 4: Simplify `poi.js` — sphere markers only, no CSS2D or click

**Files:**
- Modify: `frontend/src/poi.js`
- Modify: `frontend/src/scene.js`

- [ ] **Step 1: Replace `frontend/src/poi.js` entirely**

```js
import * as THREE from 'three';
import { POI_COLORS } from './colors.js';

export function addPOIMarkers(scene, pois) {
  pois.forEach(poi => {
    const color = new THREE.Color(POI_COLORS[poi.category] || '#888888');
    const geo = new THREE.SphereGeometry(3.5, 10, 10);
    const mat = new THREE.MeshLambertMaterial({ color });
    const sphere = new THREE.Mesh(geo, mat);
    sphere.position.set(poi.x, 5, -poi.y);
    sphere.castShadow = true;
    scene.add(sphere);
  });
}
```

- [ ] **Step 2: Update the import in `frontend/src/scene.js`**

Find line 7 in `scene.js`:
```js
import { addPOIs } from './poi.js';
```
Replace with:
```js
import { addPOIMarkers } from './poi.js';
```

- [ ] **Step 3: Update the call site in `scene.js`**

Find:
```js
  // POI markers
  if (sceneData.pois.length > 0) {
    addPOIs(scene, labelRenderer, camera, sceneData.pois);
  }
```
Replace with:
```js
  // POI markers
  if (sceneData.pois.length > 0) {
    addPOIMarkers(scene, sceneData.pois);
  }
```

- [ ] **Step 4: Run vitest to confirm no broken imports**

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm test 2>&1 | tail -20
```

Expected: tests pass (geometry and frame tests unaffected)

- [ ] **Step 5: Commit**

```bash
cd /home/mato/Dev/tf/genmap
git add frontend/src/poi.js frontend/src/scene.js
git commit -m "refactor: simplify poi.js to sphere markers only, remove CSS2D labels and click"
```

---

## Task 5: Fix `scene.js` — remove interactivity, fixed camera

**Files:**
- Modify: `frontend/src/scene.js`

Remove `OrbitControls` and `CSS2DRenderer`, fix camera position, make canvas fixed 800×676, clean up render loop.

- [ ] **Step 1: Remove unused imports from `scene.js`**

Remove lines:
```js
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js';
```

The top of `scene.js` should now read:
```js
import * as THREE from 'three';
import { BUILDING_COLORS, BUILDING_COLOR_DEFAULT, GEO_LAYER_COLORS, ROAD_COLORS, ROAD_COLOR_DEFAULT, POI_COLORS } from './colors.js';
import { buildRibbonGeometry, buildDashLineGeometry } from './geometry.js';
import { addAnimations, addShrubs, addCyclists } from './animations.js';
import { addPOIMarkers } from './poi.js';
```

- [ ] **Step 2: Replace the `createScene` function setup block**

Find the entire block from `export function createScene(container, sceneData, mode) {` through the closing of the resize handler and animation loop setup. Replace the function with the version below. This removes `mode` parameter, `OrbitControls`, `CSS2DRenderer`, fixes camera, and cleans the render loop:

```js
export function createScene(container, sceneData) {
  if (_activeScene) {
    _activeScene.dispose();
    _activeScene = null;
  }

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0d1b2a);
  scene.fog = new THREE.Fog(0x0d1b2a, 500, 900);

  // Fixed canvas size — infographic layout controls dimensions via CSS
  const W = container.clientWidth || 800;
  const H = container.clientHeight || 676;

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setSize(W, H);
  container.innerHTML = '';
  container.appendChild(renderer.domElement);

  // Fixed isometric-ish camera — no user control
  const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 2000);
  camera.position.set(-280, 320, 280);
  camera.lookAt(0, 0, 0);

  // Lights
  const ambient = new THREE.AmbientLight(0xffffff, 1.0);
  scene.add(ambient);

  const sun = new THREE.DirectionalLight(0xfff5e0, 1.4);
  sun.position.set(300, 500, 200);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.near = 10;
  sun.shadow.camera.far = 1200;
  sun.shadow.camera.left = -700;
  sun.shadow.camera.right = 700;
  sun.shadow.camera.top = 700;
  sun.shadow.camera.bottom = -700;
  scene.add(sun);

  _addGround(scene, sceneData.bbox_m);

  if (sceneData.geo_layers) {
    _addGeoLayers(scene, sceneData.geo_layers);
  }

  _addRoads(scene, sceneData.roads);
  _addBuildings(scene, sceneData.buildings);

  const animatables = [
    ...addAnimations(scene, sceneData),
    ...addCyclists(scene, sceneData.roads),
  ];
  addShrubs(scene, sceneData);

  if (sceneData.pois.length > 0) {
    addPOIMarkers(scene, sceneData.pois);
  }

  if (sceneData.outer_pois && sceneData.outer_pois.length > 0) {
    addOuterNeedles(scene, sceneData.outer_pois, sceneData.display_radius_m || 600);
  }

  let raf;
  function animate(time) {
    raf = requestAnimationFrame(animate);
    animatables.forEach(fn => fn(time * 0.001));
    renderer.render(scene, camera);
  }
  animate(0);

  function dispose() {
    cancelAnimationFrame(raf);
    renderer.dispose();
    container.innerHTML = '';
  }

  _activeScene = { dispose };
  return { dispose, scene };
}
```

- [ ] **Step 3: Verify Vite build succeeds**

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm run build 2>&1 | tail -15
```

Expected: build completes with no errors (warnings about unused exports are fine)

- [ ] **Step 4: Commit**

```bash
cd /home/mato/Dev/tf/genmap
git add frontend/src/scene.js
git commit -m "refactor: scene.js — fixed camera, remove OrbitControls/CSS2DRenderer"
```

---

## Task 6: New `frontend/src/infographic.js`

**Files:**
- Create: `frontend/src/infographic.js`

Builds the infographic DOM — header, left/right POI panels, canvas slot, transport strip — and wires `initFrame` for outer POI edge indicators.

- [ ] **Step 1: Create `frontend/src/infographic.js`**

```js
import { POI_COLORS } from './colors.js';
import { initFrame } from './frame.js';

const CATEGORY_EMOJI = {
  hospital:      '🏥',
  grocery:       '🛒',
  school:        '🏫',
  pharmacy:      '💊',
  pub:           '🍺',
  bar:           '🍸',
  restaurant:    '🍽',
  public_office: '🏛',
  bus_stop:      '🚌',
  bike_parking:  '🚲',
  parking:       '🅿',
  train:         '🚉',
};

/**
 * Builds the full infographic DOM inside `rootEl`.
 * Returns { canvasSlot } — the div where Three.js should mount.
 */
export function initInfographic(rootEl, sceneData) {
  rootEl.innerHTML = '';
  rootEl.className = 'infographic-root';

  const header = _buildHeader(sceneData.address || '');
  const body = document.createElement('div');
  body.className = 'infographic-body';

  const leftPanel = _buildPoiPanel(sceneData.pois.slice(0, 3), sceneData.bbox_m || 600);
  leftPanel.classList.add('infographic-panel-left');

  const canvasSlot = document.createElement('div');
  canvasSlot.className = 'infographic-canvas-slot';

  const rightPanel = _buildPoiPanel(sceneData.pois.slice(3, 6), sceneData.bbox_m || 600);
  rightPanel.classList.add('infographic-panel-right');

  body.append(leftPanel, canvasSlot, rightPanel);

  const strip = _buildTransportStrip(sceneData.transport || []);

  rootEl.append(header, body, strip);

  if (sceneData.outer_pois && sceneData.outer_pois.length > 0) {
    initFrame(
      canvasSlot,
      sceneData.outer_pois,
      sceneData.center.lat,
      sceneData.center.lon,
      () => {},
      () => {},
    );
  }

  return { canvasSlot };
}

function _buildHeader(address) {
  const el = document.createElement('div');
  el.className = 'infographic-header';

  const title = document.createElement('span');
  title.className = 'infographic-title';
  title.textContent = '◈ NEIGHBOURHOOD MAP';

  const addr = document.createElement('span');
  addr.className = 'infographic-address';
  addr.textContent = address;

  el.append(title, addr);
  return el;
}

function _buildPoiPanel(pois, displayRadiusM) {
  const el = document.createElement('div');
  el.className = 'infographic-panel';

  pois.forEach(poi => {
    const color = POI_COLORS[poi.category] || '#888888';
    const emoji = CATEGORY_EMOJI[poi.category] || '📍';
    const fill = Math.min(100, Math.round((poi.distance_m / displayRadiusM) * 100));
    const cardinal = _bearingToCardinal(poi.bearing_deg ?? poi.distance_m);
    const distLabel = poi.distance_m >= 1000
      ? `${(poi.distance_m / 1000).toFixed(1)} km`
      : `${poi.distance_m} m`;

    const card = document.createElement('div');
    card.className = 'poi-card';
    card.style.setProperty('--cat-color', color);

    card.innerHTML = `
      <div class="poi-card-emoji-name">${emoji} ${_escapeHtml(poi.name)}</div>
      <div class="poi-card-meta">${distLabel} · ${cardinal}</div>
      <div class="poi-card-bar-track">
        <div class="poi-card-bar-fill" style="width:${fill}%"></div>
      </div>
    `;
    el.appendChild(card);
  });

  return el;
}

function _buildTransportStrip(transport) {
  const el = document.createElement('div');
  el.className = 'infographic-strip';

  if (transport.length === 0) return el;

  transport.slice(0, 5).forEach(t => {
    const emoji = CATEGORY_EMOJI[t.category] || '🚏';
    const distLabel = t.distance_m >= 1000
      ? `${(t.distance_m / 1000).toFixed(1)} km`
      : `${t.distance_m} m`;
    const cardinal = _bearingToCardinal(t.bearing_deg ?? 0);

    const pill = document.createElement('span');
    pill.className = 'transport-pill';
    pill.textContent = `${emoji} ${_escapeHtml(t.name)} · ${distLabel} ${cardinal}`;
    el.appendChild(pill);
  });

  return el;
}

function _bearingToCardinal(deg) {
  if (deg == null) return '';
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  return dirs[Math.round(((deg % 360) + 360) % 360 / 45) % 8];
}

function _escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
```

- [ ] **Step 2: Run vitest — expect pass**

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm test 2>&1 | tail -10
```

Expected: all existing tests still pass (infographic.js has no tests itself — DOM logic is verified in Task 8 by running the app)

- [ ] **Step 3: Commit**

```bash
cd /home/mato/Dev/tf/genmap
git add frontend/src/infographic.js
git commit -m "feat: infographic.js — header, POI panel cards, transport strip, outer POI wiring"
```

---

## Task 7: New `index.html` and simplified `main.js`

**Files:**
- Rewrite: `frontend/index.html`
- Rewrite: `frontend/src/main.js`

- [ ] **Step 1: Replace `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="sk">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Neighbourhood Map</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      background: #060d14;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: 'Segoe UI', system-ui, sans-serif;
    }

    /* ── Loading ─────────────────────────────────────────── */
    #loading {
      position: fixed;
      inset: 0;
      background: #060d14;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #e8c547;
      font-size: 14px;
      z-index: 100;
    }

    /* ── Infographic shell ───────────────────────────────── */
    #app { width: 1200px; }

    .infographic-root {
      width: 1200px;
      background: #0d1b2a;
      border: 1px solid rgba(232, 197, 71, 0.2);
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 24px 80px rgba(0, 0, 0, 0.6);
    }

    /* ── Header ─────────────────────────────────────────── */
    .infographic-header {
      height: 44px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      border-bottom: 1px solid rgba(232, 197, 71, 0.15);
      background: rgba(0, 0, 0, 0.2);
    }
    .infographic-title {
      color: #e8c547;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 3px;
    }
    .infographic-address {
      color: rgba(255, 255, 255, 0.45);
      font-size: 11px;
    }

    /* ── Body: 3 columns ─────────────────────────────────── */
    .infographic-body {
      display: flex;
      height: 676px;
    }

    /* ── Panels ──────────────────────────────────────────── */
    .infographic-panel {
      width: 200px;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 14px 10px;
      background: rgba(0, 0, 0, 0.15);
    }
    .infographic-panel-left {
      border-right: 1px solid rgba(255, 255, 255, 0.06);
    }
    .infographic-panel-right {
      border-left: 1px solid rgba(255, 255, 255, 0.06);
    }

    /* ── POI cards ───────────────────────────────────────── */
    .poi-card {
      background: rgba(255, 255, 255, 0.04);
      border-left: 3px solid var(--cat-color, #888);
      border-radius: 0 5px 5px 0;
      padding: 8px 10px;
    }
    .poi-card-emoji-name {
      font-size: 11px;
      font-weight: 600;
      color: #ffffff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-bottom: 3px;
    }
    .poi-card-meta {
      font-size: 10px;
      color: rgba(255, 255, 255, 0.4);
      margin-bottom: 6px;
    }
    .poi-card-bar-track {
      height: 3px;
      background: rgba(255, 255, 255, 0.08);
      border-radius: 2px;
      overflow: hidden;
    }
    .poi-card-bar-fill {
      height: 100%;
      border-radius: 2px;
      background: var(--cat-color, #888);
      transition: width 0.8s ease;
    }

    /* ── 3D canvas slot ──────────────────────────────────── */
    .infographic-canvas-slot {
      flex: 1;
      position: relative;
      overflow: hidden;
      background: #0d1b2a;
    }
    .infographic-canvas-slot canvas {
      display: block;
      width: 100% !important;
      height: 100% !important;
    }

    /* ── Transport strip ─────────────────────────────────── */
    .infographic-strip {
      height: 40px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 0 16px;
      border-top: 1px solid rgba(255, 255, 255, 0.07);
      background: rgba(0, 0, 0, 0.1);
      overflow-x: auto;
    }
    .infographic-strip::-webkit-scrollbar { display: none; }
    .transport-pill {
      flex-shrink: 0;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 12px;
      padding: 3px 11px;
      font-size: 10px;
      color: rgba(255, 255, 255, 0.55);
      white-space: nowrap;
    }

    /* ── Outer POI indicators (from frame.js) ────────────── */
    .outer-poi-indicator {
      position: absolute;
      pointer-events: auto;
      cursor: default;
      z-index: 10;
    }
    .outer-poi-pill {
      background: rgba(13, 27, 42, 0.88);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 10px;
      padding: 3px 8px;
      font-size: 9px;
      color: rgba(255, 255, 255, 0.75);
      white-space: nowrap;
      backdrop-filter: blur(4px);
    }
    .outer-poi-header {
      display: flex;
      align-items: center;
      gap: 4px;
      margin-bottom: 1px;
    }
    .outer-poi-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    .outer-poi-name { font-weight: 600; }
    .outer-poi-meta { color: rgba(255, 255, 255, 0.45); font-size: 8px; }
    .outer-poi-indicator.active .outer-poi-pill {
      border-color: rgba(255, 255, 255, 0.35);
      background: rgba(13, 27, 42, 0.96);
    }

    /* ── Scale down on small screens ────────────────────── */
    @media (max-width: 1260px) {
      body { align-items: flex-start; padding: 16px; }
      #app {
        transform-origin: top left;
        transform: scale(0.75);
      }
    }
  </style>
</head>
<body>
  <div id="loading">Načítavam mapu…</div>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 2: Replace `frontend/src/main.js`**

```js
import { initInfographic } from './infographic.js';
import { createScene } from './scene.js';

const DEFAULT_LAT = 48.28646434486518;
const DEFAULT_LON = 17.27221245956356;

function getCoordsFromURL() {
  const params = new URLSearchParams(window.location.search);
  const lat = parseFloat(params.get('lat'));
  const lon = parseFloat(params.get('lon'));
  if (!isNaN(lat) && !isNaN(lon)) return { lat, lon };
  return null;
}

async function fetchScene(lat, lon) {
  const useFixture = new URLSearchParams(window.location.search).get('fixture') === 'true';
  const url = useFixture
    ? `/api/scene?lat=${lat}&lon=${lon}&fixture=true`
    : `/api/scene?lat=${lat}&lon=${lon}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Scene fetch failed: ${res.status}`);
  return res.json();
}

async function init() {
  const coords = getCoordsFromURL() || { lat: DEFAULT_LAT, lon: DEFAULT_LON };
  const appEl = document.getElementById('app');

  try {
    const sceneData = await fetchScene(coords.lat, coords.lon);
    const { canvasSlot } = initInfographic(appEl, sceneData);
    createScene(canvasSlot, sceneData);
    document.getElementById('loading').style.display = 'none';
  } catch (err) {
    document.getElementById('loading').textContent = `Chyba: ${err.message}`;
  }
}

init();
```

- [ ] **Step 3: Run vitest — expect pass**

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm test 2>&1 | tail -10
```

Expected: tests pass. (The old `main.test.js` tests `getMode` / `getCoordsFromURL` — `getCoordsFromURL` still exists with the same contract, `getMode` is now gone. Delete or update `main.test.js`.)

Update `frontend/src/main.test.js` — remove the `getMode` describe block (function no longer exists), keep `getCoordsFromURL` and `colors` tests:

```js
import { describe, it, expect } from 'vitest';

describe('getCoordsFromURL', () => {
  it('parses lat/lon from search params', () => {
    function getCoordsFromURL(search) {
      const params = new URLSearchParams(search);
      const lat = parseFloat(params.get('lat'));
      const lon = parseFloat(params.get('lon'));
      if (!isNaN(lat) && !isNaN(lon)) return { lat, lon };
      return null;
    }
    expect(getCoordsFromURL('?lat=48.286&lon=17.272')).toEqual({ lat: 48.286, lon: 17.272 });
    expect(getCoordsFromURL('')).toBeNull();
    expect(getCoordsFromURL('?lat=abc&lon=17')).toBeNull();
  });
});

describe('colors', () => {
  it('has entries for all POI categories', async () => {
    const { POI_COLORS } = await import('./colors.js');
    const cats = ['hospital', 'school', 'restaurant', 'bar', 'pub', 'grocery', 'pharmacy', 'public_office'];
    cats.forEach(cat => expect(POI_COLORS[cat]).toMatch(/^#[0-9a-fA-F]{6}$/));
  });
});
```

- [ ] **Step 4: Run vitest again — expect pass**

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm test 2>&1 | tail -10
```

Expected: all tests pass

- [ ] **Step 5: Verify Vite build succeeds**

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm run build 2>&1 | tail -15
```

Expected: `dist/` created, no errors

- [ ] **Step 6: Commit**

```bash
cd /home/mato/Dev/tf/genmap
git add frontend/index.html frontend/src/main.js frontend/src/main.test.js
git commit -m "feat: new infographic layout — index.html redesign and simplified main.js"
```

---

## Task 8: Integration smoke test

Verify the full stack renders the infographic correctly in the browser.

- [ ] **Step 1: Run Python tests**

```bash
cd /home/mato/Dev/tf/genmap && pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass

- [ ] **Step 2: Start the backend**

```bash
cd /home/mato/Dev/tf/genmap/src && python api.py &
API_PID=$!
sleep 2
curl -s http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: Start the frontend dev server**

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm run dev &
sleep 3
curl -s http://localhost:5173/ | head -5
```

Expected: HTML containing `Neighbourhood Map`

- [ ] **Step 4: Open browser and verify**

Open `http://localhost:5173/?fixture=true` in the browser.

Verify visually:
- Dark `#0d1b2a` background with the infographic frame visible
- Gold `◈ NEIGHBOURHOOD MAP` title in the header
- Address shown in header (right side)
- Left panel: up to 3 POI cards with color-coded left borders and distance bars
- Right panel: up to 3 more POI cards
- 3D city scene in the centre: buildings, roads, green ground
- Trees swaying, cars moving, cyclists on road edges, pedestrians on sidewalks, center pin pulsing
- Transport strip at the bottom with pills
- Outer POI indicator pills on the edge of the 3D canvas (for distant POIs)

- [ ] **Step 5: Test with real coordinates**

Open `http://localhost:5173/?lat=48.28646&lon=17.27221`

Verify the scene loads with live OSM data (may take 30–60s first run; subsequent runs use cache). Confirm all panels show real POI names and distances.

- [ ] **Step 6: Stop servers**

```bash
kill $API_PID
# Ctrl+C the Vite server
```

- [ ] **Step 7: Commit final integration note**

```bash
cd /home/mato/Dev/tf/genmap
git commit --allow-empty -m "chore: infographic redesign integration verified"
```

---

## Spec Coverage Checklist

| Spec requirement | Task |
|---|---|
| Fixed canvas 1200×760px | Task 7 (index.html CSS) |
| Dark premium `#0d1b2a` + gold accents | Task 7 |
| Header with title + address | Task 6 + Task 3 |
| Left/right POI panels, 3 cards each | Task 6 |
| POI card: color border, name, distance, direction, bar | Task 6 |
| Transport strip (bus/bike/parking/train) | Task 1 + Task 2 + Task 6 |
| Edge indicators for outer POIs | Task 6 (wires existing frame.js) |
| Fixed camera, no OrbitControls | Task 5 |
| No search bar, no demo UI | Task 7 |
| CSS2D labels removed | Task 4 |
| Click popups removed | Task 4 |
| Trees sway | unchanged (animations.js) |
| Cars on road splines | unchanged (animations.js) |
| Pedestrians on sidewalks | unchanged (animations.js) |
| Cyclists / bicycles | unchanged (already in animations.js) |
| Center pin pulse | unchanged (animations.js) |
| `address` field in SceneJSON | Task 3 |
| `transport` field in SceneJSON | Task 1 + Task 2 |
| Fog as soft edge fade | Task 5 |
| `fetch_transport()` cached | Task 1 |
