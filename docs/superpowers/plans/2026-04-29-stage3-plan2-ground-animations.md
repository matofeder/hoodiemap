# Stage 3 — Urban Ground & Animations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the uniform green ground with OSM-based urban landuse coloring, and fix animated figures (cars, pedestrians) so they're clearly visible while adding cyclists.

**Architecture:** Task 1 adds `residential` landuse to the backend pipeline (fetcher → scene_builder → JSON). Task 2 renders it on the frontend. Tasks 3–4 are pure frontend animation fixes. Run Plan 1 first — this plan assumes display_meters=1000 and fog already removed.

**Tech Stack:** Python (osmnx, geopandas, pyproj), Three.js 0.168, Vite 5, Vitest, pytest. Frontend tests: `cd frontend && npm test`. Python tests: `python -m pytest tests/ -x -q` (run from repo root).

---

### Task 1: Backend — add residential landuse layer

**Files:**
- Modify: `src/fetcher.py`
- Modify: `src/scene_builder.py`
- Modify: `tests/test_scene_builder.py`

Context: `src/fetcher.py` has a `_GEO_LAYERS` dict that drives OSM feature fetching. `src/scene_builder.py` iterates a hardcoded list of layer names to build `geo_layers_out`. The existing test at line 202 in `tests/test_scene_builder.py` asserts `set(gl.keys()) == {"water", "forest", "park"}` — adding `residential` will break it, so we update the test first.

- [ ] **Step 1: Write failing test — residential key present in output**

In `tests/test_scene_builder.py`, find `test_geo_layers_in_scene_output` (~line 177). Update it:

1. Add `"residential": None` to the `mock_geo.return_value` dict (line ~191):
```python
        mock_geo.return_value = {
            "building": None,
            "water":  _make_mock_geo_layer_gdf(cx, cy, offset=100),
            "forest": _make_mock_geo_layer_gdf(cx, cy, offset=200),
            "park":   None,
            "railway": None,
            "residential": None,
        }
```

2. Update the assertion at line ~202:
```python
    assert set(gl.keys()) == {"water", "forest", "park", "residential"}
```

Also update `test_geo_layers_multipolygon` (~line 219): add `"residential": None` to its `mock_geo.return_value`:
```python
        mock_geo.return_value = {
            "building": None,
            "water": gdf,
            "forest": None,
            "park": None,
            "railway": None,
            "residential": None,
        }
```

Also update all other tests that set `mock_geo.return_value` with `{k: None for k in ["building", "water", "forest", "park", "railway"]}` — there are two such lines (in `test_roads_have_points_and_type` and `test_trees_projected`). Change both to:
```python
        mock_geo.return_value = {k: None for k in ["building", "water", "forest", "park", "railway", "residential"]}
```

Also update `test_build_scene_returns_required_keys` and `test_buildings_projected_near_center` which explicitly list keys — add `"residential": None` to each `mock_geo.return_value` dict.

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_scene_builder.py -x -q
```
Expected: FAIL — `AssertionError: assert set(...) == {'water', 'forest', 'park', 'residential'}` or KeyError.

- [ ] **Step 3: Add residential to fetcher**

In `src/fetcher.py`, find `_GEO_LAYERS` dict (~line 81). Add one entry after the `"park"` line:
```python
_GEO_LAYERS: dict[str, tuple[dict, list[str]]] = {
    "water":       ({"natural": ["water", "wetland"], "waterway": ["riverbank"]},
                    ["Polygon", "MultiPolygon"]),
    "forest":      ({"landuse": ["forest"], "natural": ["wood"]},
                    ["Polygon", "MultiPolygon"]),
    "park":        ({"leisure": ["park", "garden"], "landuse": ["grass", "meadow", "orchard"]},
                    ["Polygon", "MultiPolygon"]),
    "residential": ({"landuse": ["residential"]},
                    ["Polygon", "MultiPolygon"]),
    "building":    ({"building": True},
                    ["Polygon", "MultiPolygon"]),
    "railway":     ({"railway": ["rail", "tram"]},
                    ["LineString", "MultiLineString"]),
}
```

- [ ] **Step 4: Add residential to scene_builder**

In `src/scene_builder.py`, find `geo_layers_out` initialization (~line 105):
```python
    geo_layers_out: dict[str, list] = {"water": [], "forest": [], "park": []}
    for layer_name in ("water", "forest", "park"):
```
Replace with:
```python
    geo_layers_out: dict[str, list] = {"water": [], "forest": [], "park": [], "residential": []}
    for layer_name in ("water", "forest", "park", "residential"):
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python -m pytest tests/test_scene_builder.py -x -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/fetcher.py src/scene_builder.py tests/test_scene_builder.py
git commit -m "feat: add residential landuse layer to OSM fetch pipeline"
```

---

### Task 2: Frontend — render residential layer + neutral ground

**Files:**
- Modify: `frontend/src/colors.js`
- Modify: `frontend/src/scene.js`

Context: `_addGeoLayers` in `scene.js` loops over `['water', 'forest', 'park']` and renders each as a flat ShapeGeometry. We add `residential` and adjust y-offsets to prevent z-fighting. The ground plane color changes from grass green to neutral concrete gray.

- [ ] **Step 1: Add residential color to GEO_LAYER_COLORS**

In `frontend/src/colors.js`, find `GEO_LAYER_COLORS`:
```js
export const GEO_LAYER_COLORS = {
  water:  0x5ba0d0,
  forest: 0x4a7a4a,
  park:   0x6eae4e,
};
```
Replace with:
```js
export const GEO_LAYER_COLORS = {
  water:       0x5ba0d0,
  forest:      0x4a7a4a,
  park:        0x6eae4e,
  residential: 0xd4c9b8,
};
```

- [ ] **Step 2: Update ground color in scene.js**

In `frontend/src/scene.js`, find `_addGround`:
```js
  const mat = new THREE.MeshLambertMaterial({ color: 0x7ab648 });
```
Replace with:
```js
  const mat = new THREE.MeshLambertMaterial({ color: 0xc8bfb0 });
```

- [ ] **Step 3: Update _addGeoLayers — add residential + fix y-offsets**

In `frontend/src/scene.js`, find `_addGeoLayers`. Replace the entire function:
```js
function _addGeoLayers(scene, geoLayers) {
  const Y_OFFSET = { residential: 0.03, forest: 0.05, park: 0.05, water: 0.07 };

  ['residential', 'water', 'forest', 'park'].forEach(layerName => {
    const rings = geoLayers[layerName];
    if (!rings || rings.length === 0) return;
    const color = GEO_LAYER_COLORS[layerName];
    const yOff = Y_OFFSET[layerName] ?? 0.05;
    rings.forEach(ring => {
      if (!ring || ring.length < 3) return;
      try {
        const shape = new THREE.Shape(ring.map(([x, y]) => new THREE.Vector2(x, y)));
        const geo = new THREE.ShapeGeometry(shape);
        geo.rotateX(-Math.PI / 2);
        geo.translate(0, yOff, 0);
        const mat = new THREE.MeshLambertMaterial({ color });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.receiveShadow = true;
        scene.add(mesh);
      } catch (err) {
        console.warn('_addGeoLayers: skipped ring in', layerName, err);
      }
    });
  });
}
```

Note: `residential` is rendered first (lowest y-offset) so park/forest/water correctly layer on top of it.

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/colors.js frontend/src/scene.js
git commit -m "feat: neutral concrete ground + residential landuse layer from OSM"
```

---

### Task 3: Fix car and pedestrian visibility

**Files:**
- Modify: `frontend/src/animations.js`

Context: Cars run at `y=0.3` (partially inside road surface) and 3–5 m/s (hard to spot). Pedestrians use a small capsule and are offset only 2.5m from road center (inside road surface on narrow roads). Fix both.

- [ ] **Step 1: Fix car height and speed in _buildRoadCurves and _addCars**

In `frontend/src/animations.js`, find `_buildRoadCurves` (~line 97). Change `y=0.3` to `y=0.5`:
```js
      const pts = r.points.map(([x, y]) => new THREE.Vector3(x, 0.5, -y));
```

In `_addCars` (~line 118), change speed:
```js
    const carSpeed = (2 + Math.random() * 1) / curve.getLength();
```
(Was `3 + Math.random() * 2` — reduced to 2–3 m/s so cars are trackable by eye.)

- [ ] **Step 2: Fix pedestrian size and sidewalk offset**

In `frontend/src/animations.js`, find `_makePedestrian` (~line 138). Replace body and head geometry:
```js
  const bodyGeo = new THREE.CapsuleGeometry(0.28, 0.9, 4, 6);
```
(Was `0.22, 0.7` — slightly larger.)

```js
  const headGeo = new THREE.SphereGeometry(0.25, 6, 6);
```
(Was `0.2`.)

In `_addPedestrians` (~line 177), change sidewalk offset:
```js
    const sidewalk = _offsetCurve(baseCurve, 3.5 + (i % 2) * 1.0);
```
(Was `2.5 + (i % 2) * 1.5` — moved further from road center to clear road surface.)

In `_offsetCurve` (~line 154), the `pos.y` is inherited from the base curve. The base curve is built in `_buildRoadCurves` with `y=0.5` (fixed in Step 1), so pedestrians now also walk at `y=0.5`. No separate change needed.

- [ ] **Step 3: Run tests**

```bash
cd frontend && npm test
```
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/animations.js
git commit -m "fix: raise cars to y=0.5, slow to 2-3m/s, enlarge pedestrians and widen sidewalk"
```

---

### Task 4: Add cyclists

**Files:**
- Modify: `frontend/src/animations.js`
- Modify: `frontend/src/scene.js`

Context: Add 3 cyclists that ride along road lane edges (1.8m offset from road center) at 4 m/s. Each is a simple box-body + two cylinder wheels. Export `addCyclists` and call it in `scene.js` alongside `addAnimations`.

- [ ] **Step 1: Add cyclist model + addCyclists to animations.js**

In `frontend/src/animations.js`, append after the `_placeShrub` function (end of file):

```js
// ── Cyclists ─────────────────────────────────────────────────────────────────

const NUM_CYCLISTS = 3;
const CYCLIST_COLORS = [0x3d9970, 0x2980b9, 0xe67e22];

function _makeCyclist(color) {
  const group = new THREE.Group();
  const mat = new THREE.MeshLambertMaterial({ color });

  const bodyGeo = new THREE.BoxGeometry(0.4, 0.8, 1.2);
  const body = new THREE.Mesh(bodyGeo, mat);
  body.position.y = 1.1;
  body.castShadow = true;
  group.add(body);

  const headGeo = new THREE.SphereGeometry(0.22, 6, 6);
  const head = new THREE.Mesh(headGeo, mat);
  head.position.set(0, 1.7, -0.4);
  head.castShadow = true;
  group.add(head);

  const wheelGeo = new THREE.CylinderGeometry(0.3, 0.3, 0.1, 8);
  wheelGeo.rotateZ(Math.PI / 2);
  const wheelMat = new THREE.MeshLambertMaterial({ color: 0x222222 });
  for (const wz of [-0.5, 0.5]) {
    const wheel = new THREE.Mesh(wheelGeo, wheelMat);
    wheel.position.set(0, 0.3, wz);
    group.add(wheel);
  }
  return group;
}

export function addCyclists(scene, roads) {
  const curves = _buildRoadCurves(roads);
  if (curves.length === 0) return [];
  const tickers = [];
  for (let i = 0; i < NUM_CYCLISTS; i++) {
    const baseCurve = curves[i % curves.length];
    const lane = _offsetCurve(baseCurve, 1.8);
    const cyclist = _makeCyclist(CYCLIST_COLORS[i % CYCLIST_COLORS.length]);
    scene.add(cyclist);
    const baseT = (i + 0.5) / NUM_CYCLISTS;
    const speed = 4 / lane.getLength();
    tickers.push(t => {
      const tPath = (baseT + t * speed) % 1;
      const pos = lane.getPoint(tPath);
      const tangent = lane.getTangent(tPath);
      cyclist.position.copy(pos);
      cyclist.rotation.y = Math.atan2(tangent.x, tangent.z);
    });
  }
  return tickers;
}
```

- [ ] **Step 2: Import and call addCyclists in scene.js**

In `frontend/src/scene.js`, find the import line (~line 6):
```js
import { addAnimations, addShrubs } from './animations.js';
```
Replace with:
```js
import { addAnimations, addShrubs, addCyclists } from './animations.js';
```

In `createScene`, find:
```js
  const animatables = addAnimations(scene, sceneData);
  addShrubs(scene, sceneData);
```
Replace with:
```js
  const animatables = [
    ...addAnimations(scene, sceneData),
    ...addCyclists(scene, sceneData.roads),
  ];
  addShrubs(scene, sceneData);
```

- [ ] **Step 3: Run tests**

```bash
cd frontend && npm test
```
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/animations.js frontend/src/scene.js
git commit -m "feat: add 3 cyclists on road lane edges, visible at 4m/s"
```
