# genmap Stage 3 — Visual Fixes & Urban Ground

**Date:** 2026-04-29
**Scope:** Two plans: Plan 1 (quick fixes, frontend only), Plan 2 (landuse backend+frontend, animations)

---

## Plan 1 — Quick Wins

### 1. Orange Blocks Fix

`_buildRoof` in `frontend/src/scene.js`: remove `BoxGeometry` attic strip from `COMMERCIAL_TYPES` branch entirely. Replace with `_addFlatRoofCap` only (same as default). The attic decoration caused a bright orange floating box artifact.

**Before:**
```js
} else if (COMMERCIAL_TYPES.has(type)) {
  _addFlatRoofCap(group, footprint, height, baseColorHex);
  const atticGeo = new THREE.BoxGeometry(w + 1.0, 0.8, d + 1.0);
  // ... attic mesh
```

**After:**
```js
} else if (COMMERCIAL_TYPES.has(type)) {
  _addFlatRoofCap(group, footprint, height, baseColorHex);
```

### 2. Remove Fog

`frontend/src/scene.js`, `createScene`:

```js
// Remove this line:
scene.fog = new THREE.Fog(0xc9e8f4, 600, 1200);
```

### 3. Road Widths ×1.4

`frontend/src/colors.js`, `ROAD_COLORS`:

| Type | Old width | New width |
|------|-----------|-----------|
| motorway / trunk | 5 | 7 |
| primary | 4 | 5.6 |
| secondary | 3 | 4.2 |
| tertiary | 2.5 | 3.5 |
| residential | 2 | 2.8 |
| unclassified | 1.5 | 2.1 |
| service | 1 | 1.4 |
| default | 1.5 | 2.1 |

### 4. Display Radius 600 → 1000m

`config.yaml`:
```yaml
radii:
  display_meters: 1000
```

`frontend/src/scene.js`, `createScene`:
```js
camera.position.set(0, 450, 550);   // was (0, 300, 350)
controls.maxDistance = 1200;         // was 800
```

Ground size (`bboxM * 2.2`) scales automatically.

### 5. Responsive Full-Width Layout

`frontend/index.html`, `#app` style:

```css
#app {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
  background: #fff;
}
```

Remove `max-width: 960px`, `margin: 0 auto`, `box-shadow`. The map fills the full viewport on every screen size.

### 6. Modern Loading Spinner

Replace static text `#loading` with CSS keyframe spinner.

```css
@keyframes spin {
  to { transform: rotate(360deg); }
}
#loading {
  position: absolute; inset: 0; background: #e8eef4;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 16px; z-index: 200;
}
#loading-spinner {
  width: 40px; height: 40px; border-radius: 50%;
  border: 3px solid #dde3ea;
  border-top-color: #c0392b;
  animation: spin 0.8s linear infinite;
}
#loading-text {
  color: #c0392b; font-size: 14px; font-weight: 500;
}
```

HTML:
```html
<div id="loading">
  <div id="loading-spinner"></div>
  <div id="loading-text">Načítavam…</div>
</div>
```

`main.js` references: replace `getElementById('loading').textContent = '...'` with `getElementById('loading-text').textContent = '...'` and keep `.style.display` on `#loading` as before.

---

## Plan 2 — Urban Ground & Animations

### 7. OSM Landuse — Residential Layer

**Backend: `src/fetcher.py`**

Add to `_GEO_LAYER_QUERIES`:
```python
"residential": ({"landuse": ["residential"]}, ["landuse"]),
```

**Backend: `src/scene_builder.py`**

Add `"residential"` to `geo_layers_out` init and loop:
```python
geo_layers_out: dict[str, list] = {"water": [], "forest": [], "park": [], "residential": []}
for layer_name in ("water", "forest", "park", "residential"):
    ...
```

**Frontend: `frontend/src/colors.js`**

```js
export const GEO_LAYER_COLORS = {
  water:       0x5ba0d0,
  forest:      0x4a7a4a,
  park:        0x6eae4e,
  residential: 0xd4c9b8,   // warm beige
};
```

**Frontend: `frontend/src/scene.js`**

Ground color change in `_addGround`:
```js
const mat = new THREE.MeshLambertMaterial({ color: 0xc8bfb0 }); // neutral concrete grey
```

`_addGeoLayers`: update hardcoded layer array to include `'residential'`:
```js
['water', 'forest', 'park', 'residential'].forEach(layerName => {
```

Layer y-offsets to avoid z-fighting:
```
ground:      y = 0
residential: y = 0.03
park/forest: y = 0.05
water:       y = 0.07
roads:       y = 0.15 (unchanged)
```

Update `_addGeoLayers` to use per-layer y offset:
```js
const Y_OFFSET = { water: 0.07, forest: 0.05, park: 0.05, residential: 0.03 };
// ...
geo.translate(0, Y_OFFSET[layerName] ?? 0.05, 0);
```

### 8. Animations — Visibility Fix + Cyclists

**File:** `frontend/src/animations.js`

#### Cars
- `y = 0.5` in `_buildRoadCurves` (was 0.3)
- Speed: `(2 + Math.random() * 1) / curve.getLength()` (was 3–5 m/s)

#### Pedestrians
- Scale body: `CapsuleGeometry(0.28, 0.9, 4, 6)` (was 0.22, 0.7)
- Head: `SphereGeometry(0.25, 6, 6)` (was 0.2)
- Sidewalk offset: `3.5 + (i % 2) * 1.0` (was 2.5 + i%2 * 1.5)
- `y = 0.4` in `_offsetCurve` (was inherited 0.3 from base curve)

#### Cyclists (new)

```js
const NUM_CYCLISTS = 3;
const CYCLIST_COLORS = [0x3d9970, 0x2980b9, 0xe67e22];

function _makeCyclist(color) {
  const group = new THREE.Group();
  const mat = new THREE.MeshLambertMaterial({ color });

  // Body
  const bodyGeo = new THREE.BoxGeometry(0.4, 0.8, 1.2);
  const body = new THREE.Mesh(bodyGeo, mat);
  body.position.y = 1.1;
  group.add(body);

  // Head
  const headGeo = new THREE.SphereGeometry(0.22, 6, 6);
  const head = new THREE.Mesh(headGeo, mat);
  head.position.set(0, 1.7, -0.4);
  group.add(head);

  // Wheels
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

`scene.js`: import `addCyclists` and call it alongside `addAnimations`:
```js
import { addAnimations, addShrubs, addCyclists } from './animations.js';
// ...
const animatables = [
  ...addAnimations(scene, sceneData),
  ...addCyclists(scene, sceneData.roads),
];
```

---

## Files Changed

### Plan 1
| File | Change |
|------|--------|
| `frontend/src/scene.js` | Remove fog, remove attic strip, wider camera |
| `frontend/src/colors.js` | Road widths ×1.4 |
| `frontend/index.html` | Full-width layout, spinner HTML |
| `config.yaml` | display_meters: 1000 |

### Plan 2
| File | Change |
|------|--------|
| `src/fetcher.py` | Add residential landuse query |
| `src/scene_builder.py` | Export residential rings |
| `frontend/src/colors.js` | Add residential color, ground color |
| `frontend/src/scene.js` | Ground color, y-offsets, import addCyclists |
| `frontend/src/animations.js` | Cars/pedestrian fixes, addCyclists export |

---

## Out of Scope

- Cyclist shadow casting (performance)
- Landuse: commercial/industrial zones (minor area in residential neighborhoods)
- Dynamic POI count based on radius change
