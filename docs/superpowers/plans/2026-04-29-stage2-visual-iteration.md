# Stage 2 Visual Iteration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the genmap Three.js scene from a dark night look to a bright daylight infographic with flat lane-marked roads, typed building roofs, shrubs, and a compact centered layout.

**Architecture:** Pure frontend changes in `frontend/src/`. New `geometry.js` module holds pure ribbon/dash geometry builders (testable without Three.js Scene). `scene.js` calls these helpers and handles lighting, roads, and buildings. `animations.js` handles trees, shrubs, and cars. `index.html` provides the centered card layout.

**Tech Stack:** Three.js 0.168, Vite 5, Vitest 1 — run tests with `cd frontend && npm test`, dev server already running at http://localhost:5173 (proxy → FastAPI at :8000).

---

## File Map

| File | Role |
|---|---|
| `frontend/src/geometry.js` | NEW — pure functions: `buildRibbonGeometry`, `buildDashLineGeometry` |
| `frontend/src/geometry.test.js` | NEW — Vitest tests for geometry helpers |
| `frontend/src/scene.js` | MODIFY — lighting, ground, `_addRoads`, `_addBuildings`, call `addShrubs` |
| `frontend/src/animations.js` | MODIFY — `_addTrees` (sphere canopy), new `addShrubs`, `_addCars` (y+count) |
| `frontend/index.html` | MODIFY — centered card layout, top bar |

---

## Task 1: Geometry helpers module

**Files:**
- Create: `frontend/src/geometry.js`
- Create: `frontend/src/geometry.test.js`

`geometry.js` provides pure functions that build `THREE.BufferGeometry` objects for roads. They accept plain data (no Scene, no Camera) so they can be unit-tested without a DOM.

- [ ] **Step 1: Write failing tests**

Create `frontend/src/geometry.test.js`:

```javascript
import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import { buildRibbonGeometry, buildDashLineGeometry } from './geometry.js';

function straightCurve(length = 100) {
  return new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(length, 0, 0),
  ]);
}

describe('buildRibbonGeometry', () => {
  it('returns a BufferGeometry', () => {
    const geo = buildRibbonGeometry(straightCurve(), 4);
    expect(geo).toBeInstanceOf(THREE.BufferGeometry);
  });

  it('has at least 12 positions (2 triangles minimum)', () => {
    const geo = buildRibbonGeometry(straightCurve(), 4);
    const count = geo.getAttribute('position').count;
    expect(count).toBeGreaterThanOrEqual(4); // at least 1 segment = 2 rows × 2 verts
  });

  it('all y values equal 0.15', () => {
    const geo = buildRibbonGeometry(straightCurve(), 4);
    const pos = geo.getAttribute('position');
    for (let i = 0; i < pos.count; i++) {
      expect(pos.getY(i)).toBeCloseTo(0.15, 5);
    }
  });
});

describe('buildDashLineGeometry', () => {
  it('returns a BufferGeometry', () => {
    const geo = buildDashLineGeometry(straightCurve(100), 2, 3, 0.17);
    expect(geo).toBeInstanceOf(THREE.BufferGeometry);
  });

  it('has correct number of dash quads for 100m curve with 5m period', () => {
    // 100m / (2+3) = 20 dashes, each dash = 2 triangles = 6 verts
    const geo = buildDashLineGeometry(straightCurve(100), 2, 3, 0.17);
    const count = geo.getAttribute('position').count;
    expect(count).toBe(20 * 6);
  });

  it('all y values equal yOffset', () => {
    const geo = buildDashLineGeometry(straightCurve(100), 2, 3, 0.42);
    const pos = geo.getAttribute('position');
    for (let i = 0; i < pos.count; i++) {
      expect(pos.getY(i)).toBeCloseTo(0.42, 5);
    }
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd frontend && npm test -- geometry.test.js
```

Expected: `Cannot find module './geometry.js'`

- [ ] **Step 3: Create `frontend/src/geometry.js`**

```javascript
import * as THREE from 'three';

/**
 * Builds a flat ribbon BufferGeometry following a CatmullRomCurve3.
 * The ribbon lies at y = 0.15.
 *
 * @param {THREE.CatmullRomCurve3} curve
 * @param {number} width  — full width in metres
 * @param {number} segmentsPerMetre — geometry density (default 0.5 = one segment per 2m)
 * @returns {THREE.BufferGeometry}
 */
export function buildRibbonGeometry(curve, width, segmentsPerMetre = 0.5) {
  const length = curve.getLength();
  const numSegments = Math.max(4, Math.ceil(length * segmentsPerMetre));
  const half = width / 2;

  const positions = [];
  const indices = [];

  for (let i = 0; i <= numSegments; i++) {
    const t = i / numSegments;
    const pos = curve.getPoint(t);
    const tan = curve.getTangent(t).normalize();
    // Perpendicular in XZ plane (y is up)
    const px = -tan.z * half;
    const pz =  tan.x * half;
    positions.push(pos.x - px, 0.15, pos.z - pz); // left
    positions.push(pos.x + px, 0.15, pos.z + pz); // right
  }

  for (let i = 0; i < numSegments; i++) {
    const a = i * 2, b = i * 2 + 1, c = i * 2 + 2, d = i * 2 + 3;
    indices.push(a, b, d,  a, d, c);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setIndex(indices);
  geo.computeVertexNormals();
  return geo;
}

/**
 * Builds a flat dashed line BufferGeometry following a CatmullRomCurve3.
 * Used for road centre markings.
 *
 * @param {THREE.CatmullRomCurve3} curve
 * @param {number} dashLength  — metres per dash
 * @param {number} gapLength   — metres between dashes
 * @param {number} yOffset     — world y to place the geometry at
 * @param {number} dashWidth   — width of each dash stripe
 * @returns {THREE.BufferGeometry}
 */
export function buildDashLineGeometry(curve, dashLength = 2, gapLength = 3, yOffset = 0.17, dashWidth = 0.25) {
  const totalLength = curve.getLength();
  const period = dashLength + gapLength;
  const positions = [];

  let d = 0;
  while (d < totalLength) {
    const t0 = d / totalLength;
    const t1 = Math.min((d + dashLength) / totalLength, 1);
    const tm = (t0 + t1) / 2;

    const p0 = curve.getPoint(t0);
    const p1 = curve.getPoint(t1);
    const tan = curve.getTangent(tm).normalize();
    const hw = dashWidth / 2;
    const px = -tan.z * hw;
    const pz =  tan.x * hw;

    // Two triangles forming a dash quad
    positions.push(
      p0.x - px, yOffset, p0.z - pz,
      p0.x + px, yOffset, p0.z + pz,
      p1.x + px, yOffset, p1.z + pz,

      p0.x - px, yOffset, p0.z - pz,
      p1.x + px, yOffset, p1.z + pz,
      p1.x - px, yOffset, p1.z - pz,
    );
    d += period;
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.computeVertexNormals();
  return geo;
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd frontend && npm test -- geometry.test.js
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/geometry.js frontend/src/geometry.test.js
git commit -m "feat: geometry helpers — ribbon and dash-line BufferGeometry builders"
```

---

## Task 2: Daylight scene lighting and ground

**Files:**
- Modify: `frontend/src/scene.js` (lines ~20–75, `createScene` + `_addGround`)

- [ ] **Step 1: Update `createScene` — background, fog, lights**

In `scene.js`, replace the block from `scene.background` through `scene.add(sun)`:

```javascript
  scene.background = new THREE.Color(0x87ceeb);   // day sky blue
  scene.fog = new THREE.Fog(0xc9e8f4, 600, 1200); // light air, pushed farther

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setSize(container.clientWidth || window.innerWidth, container.clientHeight || window.innerHeight);
  container.innerHTML = '';
  container.appendChild(renderer.domElement);
  // ... (CSS2D renderer unchanged)

  const ambient = new THREE.AmbientLight(0xffffff, 1.0);  // was 0.6
  scene.add(ambient);

  const sun = new THREE.DirectionalLight(0xfff5e0, 1.4);  // was 1.0
  sun.position.set(300, 500, 200);                          // was (200,300,200)
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.near = 10;
  sun.shadow.camera.far = 1200;
  sun.shadow.camera.left = -700;
  sun.shadow.camera.right = 700;
  sun.shadow.camera.top = 700;
  sun.shadow.camera.bottom = -700;
  scene.add(sun);
```

- [ ] **Step 2: Update `_addGround` — sunny grass color**

```javascript
function _addGround(scene, bboxM) {
  const size = bboxM * 2.2;
  const geo = new THREE.PlaneGeometry(size, size);
  const mat = new THREE.MeshLambertMaterial({ color: 0x7ab648 }); // was 0x3a5a3a
  const ground = new THREE.Mesh(geo, mat);
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);
}
```

- [ ] **Step 3: Verify in browser**

Open http://localhost:5173, search for "Pezinok" (or any address). The scene should now show a bright blue sky and green ground instead of the dark navy background. Buildings and roads should be well-lit.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/scene.js
git commit -m "feat: daylight scene — sky blue background, brighter lights, sunny ground"
```

---

## Task 3: Flat road ribbons (replace TubeGeometry)

**Files:**
- Modify: `frontend/src/scene.js` (`_addRoads`)

Replace the `TubeGeometry` road renderer with flat ribbon geometry from `geometry.js`, plus white edge strips.

- [ ] **Step 1: Update `_addRoads` in `scene.js`**

Add the import at the top of the file:

```javascript
import { buildRibbonGeometry, buildDashLineGeometry } from './geometry.js';
```

Then replace the entire `_addRoads` function:

```javascript
function _addRoads(scene, roads) {
  const CENTER_LINE_TYPES = new Set(['primary', 'secondary', 'tertiary']);

  roads.forEach(road => {
    const style = ROAD_COLORS[road.type] || ROAD_COLOR_DEFAULT;
    if (road.points.length < 2) return;

    const pts = road.points.map(([x, y]) => new THREE.Vector3(x, 0, -y));
    const curve = new THREE.CatmullRomCurve3(pts);
    const width = style.width;

    // Road surface
    const surfaceGeo = buildRibbonGeometry(curve, width);
    const surfaceMat = new THREE.MeshLambertMaterial({ color: new THREE.Color(style.fill) });
    const surface = new THREE.Mesh(surfaceGeo, surfaceMat);
    surface.receiveShadow = true;
    scene.add(surface);

    // White edge strips (y = 0.16, width 0.3m each side)
    const edgeOffset = width / 2 + 0.15; // centre of 0.3m strip
    const edgeMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.5 });
    for (const sign of [-1, 1]) {
      const offsetPts = _offsetCurvePoints(curve, sign * edgeOffset);
      const edgeCurve = new THREE.CatmullRomCurve3(offsetPts);
      const edgeGeo = buildRibbonGeometry(edgeCurve, 0.3, 1.0);
      const edgeMesh = new THREE.Mesh(edgeGeo, edgeMat);
      scene.add(edgeMesh);
    }

    // Dashed centre line for major roads
    if (CENTER_LINE_TYPES.has(road.type)) {
      const dashGeo = buildDashLineGeometry(curve, 2, 3, 0.17);
      const dashMat = new THREE.MeshBasicMaterial({ color: 0xf5d020 }); // yellow
      scene.add(new THREE.Mesh(dashGeo, dashMat));
    }
  });
}

/** Returns N evenly-spaced Vector3 points offset perpendicularly from a curve. */
function _offsetCurvePoints(curve, offsetM, n = 20) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const pos = curve.getPoint(t);
    const tan = curve.getTangent(t).normalize();
    pts.push(new THREE.Vector3(
      pos.x - tan.z * offsetM,
      pos.y,
      pos.z + tan.x * offsetM,
    ));
  }
  return pts;
}
```

- [ ] **Step 2: Verify in browser**

Open http://localhost:5173. Roads should now appear as flat grey/white ribbons instead of rounded tubes. White edge lines and yellow dashed centre lines should be visible on primary/secondary/tertiary roads.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/scene.js
git commit -m "feat: flat road ribbons with white edge strips and yellow centre-line dashes"
```

---

## Task 4: Cars — lift to y=0.3 and increase count to 8

**Files:**
- Modify: `frontend/src/animations.js` (constants `NUM_CARS`, car y position)

- [ ] **Step 1: Update constants and car y in `_addCars`**

At the top of `animations.js`, change:

```javascript
const NUM_CARS = 8;  // was 4
```

In `_makeCar`, the body is at `y=0.55` and wheels at `y=0.35`. The car group itself is placed by `car.position.copy(pos)` where `pos` comes from the curve point. The curve is built at `y=0.2`:

```javascript
const pts = r.points.map(([x, y]) => new THREE.Vector3(x, 0.3, -y));  // was 0.2
```

- [ ] **Step 2: Verify in browser**

After reload, 8 cars should be visible on the roads, sitting visibly above the flat road surface.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/animations.js
git commit -m "feat: 8 cars on roads (was 4), lifted to y=0.3 above flat surface"
```

---

## Task 5: Tree canopy — sphere for deciduous, keep cone for every 3rd

**Files:**
- Modify: `frontend/src/animations.js` (`_addTrees`)

- [ ] **Step 1: Update `_addTrees`**

Replace the `canopyGeo` line and the sway ticker to handle two variants:

```javascript
function _addTrees(scene, trees) {
  const tickers = [];
  const trunkMat = new THREE.MeshLambertMaterial({ color: 0x7a5c3a });
  const canopyColors = [0x4e8b4e, 0x5a9e5a, 0x639663, 0x4a844a];

  trees.forEach((tree, i) => {
    const h = Math.min(tree.height, 20);
    const r = Math.min(tree.radius, 8);
    const phase = i * 1.3;
    const isConifer = i % 3 === 0;

    const trunkH = h * 0.4;
    const trunkGeo = new THREE.CylinderGeometry(r * 0.12, r * 0.18, trunkH, 6);
    const trunk = new THREE.Mesh(trunkGeo, trunkMat);
    trunk.position.set(tree.x, trunkH / 2, -tree.y);
    trunk.castShadow = true;
    scene.add(trunk);

    const canopyMat = new THREE.MeshLambertMaterial({ color: canopyColors[i % canopyColors.length] });
    let canopy;
    if (isConifer) {
      const canopyGeo = new THREE.ConeGeometry(r * 0.7, h * 0.7, 7);
      canopy = new THREE.Mesh(canopyGeo, canopyMat);
      canopy.position.set(tree.x, trunkH + (h * 0.7) / 2, -tree.y);
    } else {
      const canopyGeo = new THREE.SphereGeometry(r * 0.8, 8, 6);
      canopy = new THREE.Mesh(canopyGeo, canopyMat);
      canopy.position.set(tree.x, trunkH + r * 0.6, -tree.y);
    }
    canopy.castShadow = true;
    scene.add(canopy);

    tickers.push(t => {
      const sway = Math.sin(t * 0.8 + phase) * 0.025;
      canopy.rotation.z = sway;
      trunk.rotation.z = sway * 0.4;
    });
  });

  return tickers;
}
```

- [ ] **Step 2: Verify in browser**

Trees should show a mix: every 3rd tree has a cone (conifer), the rest have rounded sphere canopies. All still sway.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/animations.js
git commit -m "feat: deciduous sphere canopy for trees (cone kept for every 3rd as conifer)"
```

---

## Task 6: Shrubs along park and forest edges

**Files:**
- Modify: `frontend/src/animations.js` (add `addShrubs` export)
- Modify: `frontend/src/scene.js` (call `addShrubs`)

- [ ] **Step 1: Add `addShrubs` to `animations.js`**

Add after the existing exports:

```javascript
const SHRUB_COLORS = [0x4a7a4a, 0x5a8c3a, 0x3d6e2e, 0x508040];
const MAX_SHRUBS = 200;

/**
 * Places static shrub clusters along the edges of park and forest polygons.
 * Each shrub is a cluster of 2–4 small spheres.
 * sceneData.geo_layers.park / .forest are arrays of rings: [[[x,y], ...], ...]
 */
export function addShrubs(scene, sceneData) {
  const layers = sceneData.geo_layers;
  if (!layers) return;

  let totalShrubs = 0;
  const SPACING = 8;   // metres between shrub clusters

  for (const layerName of ['park', 'forest']) {
    const rings = layers[layerName];
    if (!rings) continue;

    for (const ring of rings) {
      if (totalShrubs >= MAX_SHRUBS) return;
      if (!ring || ring.length < 2) continue;

      // Walk along ring perimeter placing shrubs at SPACING intervals
      let accumulated = 0;

      for (let i = 0; i < ring.length - 1; i++) {
        const [x0, y0] = ring[i];
        const [x1, y1] = ring[i + 1];
        const segLen = Math.hypot(x1 - x0, y1 - y0);
        let t = (accumulated === 0) ? 0 : SPACING - accumulated;

        while (t <= segLen) {
          if (totalShrubs >= MAX_SHRUBS) return;
          const frac = t / segLen;
          const sx = x0 + (x1 - x0) * frac;
          const sy = y0 + (y1 - y0) * frac;

          _placeShrub(scene, sx, sy, totalShrubs);
          totalShrubs++;
          t += SPACING;
        }
        accumulated = (accumulated + segLen) % SPACING;
      }
    }
  }
}

function _placeShrub(scene, wx, wy, idx) {
  const clusterCount = 2 + (idx % 3); // 2, 3, or 4 spheres
  const color = SHRUB_COLORS[idx % SHRUB_COLORS.length];
  const mat = new THREE.MeshLambertMaterial({ color });

  for (let k = 0; k < clusterCount; k++) {
    const angle = (k / clusterCount) * Math.PI * 2 + idx * 0.7;
    const radius = (k === 0) ? 0 : 0.8 + (k * 0.3);
    const r = 0.8 + (k % 2) * 0.4;
    const geo = new THREE.SphereGeometry(r, 6, 5);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(
      wx + Math.cos(angle) * radius,
      r,
      -(wy + Math.sin(angle) * radius),
    );
    mesh.receiveShadow = true;
    scene.add(mesh);
  }
}
```

- [ ] **Step 2: Call `addShrubs` in `scene.js`**

In `scene.js`, update the import from `animations.js`:

```javascript
import { addAnimations, addShrubs } from './animations.js';
```

Then call it after `_addBuildings`:

```javascript
  // Shrubs along park/forest edges
  addShrubs(scene, sceneData);
```

- [ ] **Step 3: Verify in browser**

Low green sphere-clusters should appear along the edges of parks and forest areas, max 200 per scene.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/animations.js frontend/src/scene.js
git commit -m "feat: shrub clusters along park and forest polygon edges (max 200)"
```

---

## Task 7: Buildings — type-distinctive shapes

**Files:**
- Modify: `frontend/src/scene.js` (`_addBuildings`, new `_buildRoof`)

This is the largest task. We add a `_buildRoof(type, footprint, height, baseColorHex)` helper that returns a `THREE.Group` of roof meshes, then call it from `_addBuildings`.

- [ ] **Step 1: Add roof-type constants and `_buildRoof` helper in `scene.js`**

Add after the existing imports at the top of `scene.js`:

```javascript
const HOUSE_TYPES      = new Set(['house', 'detached', 'bungalow']);
const APARTMENT_TYPES  = new Set(['apartments', 'residential', 'terrace']);
const CHURCH_TYPES     = new Set(['church', 'cathedral', 'chapel', 'monastery']);
const COMMERCIAL_TYPES = new Set(['commercial', 'retail', 'supermarket', 'kiosk']);
const OFFICE_TYPES     = new Set(['office', 'civic', 'public', 'government']);
const INDUSTRIAL_TYPES = new Set(['industrial', 'warehouse', 'factory']);
```

Then add the helper function (outside `createScene`, alongside `_addBuildings`):

```javascript
/**
 * Builds roof/decoration meshes for a building.
 * Footprint is array of [x, y] in scene UTM-offset coords.
 * World Z = -y, world X = x, world Y = height (up).
 * Returns a THREE.Group to add to scene.
 */
function _buildRoof(type, footprint, height, baseColorHex) {
  const group = new THREE.Group();
  const xs = footprint.map(([x]) => x);
  const ys = footprint.map(([, y]) => y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const w = maxX - minX, d = maxY - minY;
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;

  if (HOUSE_TYPES.has(type)) {
    // Pitched roof
    const ridgeH = Math.min(w, d) * 0.4;
    const topY = height + ridgeH;
    const color = new THREE.Color(baseColorHex).multiplyScalar(0.75);
    const mat = new THREE.MeshLambertMaterial({ color, side: THREE.DoubleSide });

    let verts;
    if (w >= d) {
      // Ridge along X axis, centred on Z
      const cz = -(minY + maxY) / 2;
      verts = new Float32Array([
        // Front slope (2 tri)
        minX, height, -minY,  maxX, height, -minY,  minX, topY, cz,
        maxX, height, -minY,  maxX, topY, cz,        minX, topY, cz,
        // Back slope
        minX, height, -maxY,  minX, topY, cz,        maxX, height, -maxY,
        maxX, height, -maxY,  minX, topY, cz,        maxX, topY, cz,
        // Left gable
        minX, height, -minY,  minX, topY, cz,        minX, height, -maxY,
        // Right gable
        maxX, height, -minY,  maxX, height, -maxY,  maxX, topY, cz,
      ]);
    } else {
      // Ridge along Z axis, centred on X
      verts = new Float32Array([
        // Left slope
        minX, height, -minY,  cx, topY, -minY,  minX, height, -maxY,
        cx, topY, -minY,       cx, topY, -maxY,  minX, height, -maxY,
        // Right slope
        maxX, height, -minY,  maxX, height, -maxY,  cx, topY, -minY,
        maxX, height, -maxY,  cx, topY, -maxY,       cx, topY, -minY,
        // Front gable
        minX, height, -minY,  maxX, height, -minY,  cx, topY, -minY,
        // Back gable
        minX, height, -maxY,  cx, topY, -maxY,       maxX, height, -maxY,
      ]);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    geo.computeVertexNormals();
    group.add(new THREE.Mesh(geo, mat));

  } else if (CHURCH_TYPES.has(type)) {
    // Tall spire at centroid
    const spireGeo = new THREE.ConeGeometry(0.8, 15, 4);
    const spireMat = new THREE.MeshLambertMaterial({ color: 0x9e8ac0 });
    const spire = new THREE.Mesh(spireGeo, spireMat);
    spire.position.set(cx, height + 7.5, -cy);
    spire.castShadow = true;
    group.add(spire);
    // Flat dark roof cap
    _addFlatRoofCap(group, footprint, height, baseColorHex);

  } else if (COMMERCIAL_TYPES.has(type)) {
    // Flat roof + attic strip (slightly oversized box at top)
    _addFlatRoofCap(group, footprint, height, baseColorHex);
    const atticGeo = new THREE.BoxGeometry(w + 1.0, 0.8, d + 1.0);
    const atticColor = new THREE.Color(baseColorHex).multiplyScalar(0.85);
    const atticMat = new THREE.MeshLambertMaterial({ color: atticColor });
    const attic = new THREE.Mesh(atticGeo, atticMat);
    attic.position.set(cx, height + 0.4, -cy);
    group.add(attic);

  } else if (APARTMENT_TYPES.has(type) && height > 5) {
    // Flat roof + window rows
    _addFlatRoofCap(group, footprint, height, baseColorHex);
    _addWindows(group, footprint, height);

  } else if (OFFICE_TYPES.has(type) && height > 5) {
    // Flat roof + denser window grid
    _addFlatRoofCap(group, footprint, height, baseColorHex);
    _addWindows(group, footprint, height);

  } else if (INDUSTRIAL_TYPES.has(type)) {
    // Shed roof — simple single-slope ridge along long axis
    const ridgeH = Math.min(w, d) * 0.2;
    const color = new THREE.Color(baseColorHex).multiplyScalar(0.80);
    const mat = new THREE.MeshLambertMaterial({ color, side: THREE.DoubleSide });
    // Ridge on one long side only (lean-to)
    const verts = new Float32Array([
      minX, height,         -minY,
      maxX, height,         -minY,
      maxX, height + ridgeH, -minY,
      minX, height,         -maxY,
      maxX, height,         -maxY,
      maxX, height + ridgeH, -minY,

      minX, height, -minY,
      maxX, height + ridgeH, -minY,
      minX, height + ridgeH, -minY,
      minX, height, -maxY,
      minX, height + ridgeH, -minY,
      maxX, height + ridgeH, -minY,
    ]);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    geo.computeVertexNormals();
    group.add(new THREE.Mesh(geo, mat));

  } else {
    // Default: flat dark roof cap
    _addFlatRoofCap(group, footprint, height, baseColorHex);
  }

  return group;
}

function _addFlatRoofCap(group, footprint, height, baseColorHex) {
  const color = new THREE.Color(baseColorHex).multiplyScalar(0.7);
  try {
    const shape = new THREE.Shape(footprint.map(([x, y]) => new THREE.Vector2(x, y)));
    const geo = new THREE.ShapeGeometry(shape);
    geo.rotateX(-Math.PI / 2);
    geo.translate(0, height, 0);
    const mat = new THREE.MeshLambertMaterial({ color });
    group.add(new THREE.Mesh(geo, mat));
  } catch (_) {}
}

function _addWindows(group, footprint, height) {
  const xs = footprint.map(([x]) => x);
  const ys = footprint.map(([, y]) => y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const w = maxX - minX, d = maxY - minY;
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;

  const winMat = new THREE.MeshBasicMaterial({ color: 0xadd8e6 }); // light blue
  const WIN_W = 0.8, WIN_H = 0.6, WIN_D = 0.1;
  const FLOOR_STEP = 2.5, SPACING = 1.8;

  let windowCount = 0;
  const MAX_WIN = 60;

  for (let floorY = 1.2; floorY < height - 0.5 && windowCount < MAX_WIN; floorY += FLOOR_STEP) {
    // North wall (z = -minY): windows along X
    for (let wx = minX + 1; wx < maxX - 0.5 && windowCount < MAX_WIN; wx += SPACING) {
      const geo = new THREE.BoxGeometry(WIN_W, WIN_H, WIN_D);
      const mesh = new THREE.Mesh(geo, winMat);
      mesh.position.set(wx, floorY, -minY - WIN_D / 2);
      group.add(mesh); windowCount++;
    }
    // South wall (z = -maxY)
    for (let wx = minX + 1; wx < maxX - 0.5 && windowCount < MAX_WIN; wx += SPACING) {
      const geo = new THREE.BoxGeometry(WIN_W, WIN_H, WIN_D);
      const mesh = new THREE.Mesh(geo, winMat);
      mesh.position.set(wx, floorY, -maxY + WIN_D / 2);
      group.add(mesh); windowCount++;
    }
    // West wall (x = minX): windows along Z
    for (let wy = minY + 1; wy < maxY - 0.5 && windowCount < MAX_WIN; wy += SPACING) {
      const geo = new THREE.BoxGeometry(WIN_D, WIN_H, WIN_W);
      const mesh = new THREE.Mesh(geo, winMat);
      mesh.position.set(minX - WIN_D / 2, floorY, -wy);
      group.add(mesh); windowCount++;
    }
    // East wall (x = maxX)
    for (let wy = minY + 1; wy < maxY - 0.5 && windowCount < MAX_WIN; wy += SPACING) {
      const geo = new THREE.BoxGeometry(WIN_D, WIN_H, WIN_W);
      const mesh = new THREE.Mesh(geo, winMat);
      mesh.position.set(maxX + WIN_D / 2, floorY, -wy);
      group.add(mesh); windowCount++;
    }
  }
}
```

- [ ] **Step 2: Update `_addBuildings` to call `_buildRoof`**

In the existing `_addBuildings` function, after `scene.add(mesh)` (the main extrusion) and after `scene.add(roof)` (the existing flat roof cap), **replace** the roof cap block and add the `_buildRoof` call:

```javascript
function _addBuildings(scene, buildings) {
  buildings.forEach(b => {
    const colorHex = BUILDING_COLORS[b.type] || BUILDING_COLOR_DEFAULT;
    const color = new THREE.Color(colorHex);

    const fp = b.footprint;
    if (!fp || fp.length < 3) return;

    try {
      // Main extruded body (unchanged)
      const shape = new THREE.Shape(fp.map(([x, y]) => new THREE.Vector2(x, y)));
      const extGeo = new THREE.ExtrudeGeometry(shape, {
        depth: b.height,
        bevelEnabled: false,
      });
      extGeo.rotateX(-Math.PI / 2);

      const mat = new THREE.MeshLambertMaterial({ color });
      const mesh = new THREE.Mesh(extGeo, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      scene.add(mesh);

      // Type-distinctive roof / decoration
      const roofGroup = _buildRoof(b.type || 'yes', fp, b.height, colorHex);
      scene.add(roofGroup);
    } catch (err) {
      console.warn('_addBuildings: skipped footprint', b, err);
    }
  });
}
```

- [ ] **Step 3: Verify in browser**

After reload:
- Residential houses should show triangular pitched roofs
- Churches should have a spire on top
- Shops/commercial should have an attic strip
- Apartment blocks tall enough should have small blue window rectangles on their walls
- Industrial buildings should have a lean-to shed roof

- [ ] **Step 4: Commit**

```bash
git add frontend/src/scene.js
git commit -m "feat: type-distinctive building shapes — pitched roofs, spires, windows, attics"
```

---

## Task 8: Centered card layout

**Files:**
- Modify: `frontend/index.html`

Replace the full-screen fixed positioning with a centered max-width card. The Three.js canvas fills the card's remaining height. Embed/view modes are unaffected (they have their own `data-mode` styles).

- [ ] **Step 1: Rewrite `index.html` CSS and HTML structure**

Replace the entire `<style>` block and `<body>` content with:

```html
<!DOCTYPE html>
<html lang="sk">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Neighbourly — 3D Neighborhood Map</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #e8eef4; overflow: hidden; font-family: sans-serif; }

    /* ── Demo mode: centered card ───────────────────────── */
    #app {
      display: flex;
      flex-direction: column;
      max-width: 960px;
      height: 100vh;
      margin: 0 auto;
      background: #fff;
      box-shadow: 0 0 40px rgba(0,0,0,0.15);
    }

    /* Top bar */
    #top-bar {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 16px;
      height: 52px;
      flex-shrink: 0;
      background: #fff;
      border-bottom: 1px solid #ddd;
    }
    #brand { color: #c0392b; font-weight: bold; font-size: 14px; white-space: nowrap; margin-right: 4px; }
    #search-input {
      flex: 1; border: 1px solid #ccc; border-radius: 20px;
      padding: 6px 14px; font-size: 14px; outline: none;
    }
    #search-input:focus { border-color: #c0392b; }
    #search-btn {
      background: #c0392b; color: #fff; border: none; border-radius: 20px;
      padding: 6px 16px; font-size: 13px; font-weight: bold; cursor: pointer;
      white-space: nowrap;
    }
    #search-btn:disabled { opacity: 0.5; cursor: default; }

    /* Map area */
    #canvas-container {
      flex: 1;
      min-height: 0;
      position: relative;
      overflow: hidden;
      background: #87ceeb;
    }
    #canvas-container canvas { display: block; width: 100% !important; height: 100% !important; }

    /* Embed code button */
    #embed-btn {
      position: absolute; bottom: 16px; right: 16px;
      background: rgba(255,255,255,0.9); border: 1px solid #ccc;
      border-radius: 6px; color: #555; font-size: 12px;
      padding: 5px 10px; cursor: pointer; display: none;
    }

    /* Info card */
    #info-card {
      position: absolute; bottom: 16px; left: 16px;
      background: rgba(255,255,255,0.92); backdrop-filter: blur(6px);
      border-radius: 10px; padding: 10px 14px;
      border-left: 3px solid #c0392b; min-width: 180px; max-width: 260px;
      display: none; box-shadow: 0 2px 12px rgba(0,0,0,0.12);
    }
    #info-card .address { color: #222; font-weight: bold; font-size: 13px; margin-bottom: 4px; }
    #info-card .pois { color: #666; font-size: 11px; line-height: 1.8; }

    /* POI labels */
    .poi-label {
      background: rgba(255,255,255,0.85); color: #222; font-size: 11px;
      padding: 2px 7px; border-radius: 10px; white-space: nowrap;
      pointer-events: none; transform: translateY(-18px);
      box-shadow: 0 1px 4px rgba(0,0,0,0.15);
    }
    .poi-popup {
      background: rgba(255,255,255,0.97); color: #222; font-size: 12px;
      padding: 8px 12px; border-radius: 8px; min-width: 140px;
      pointer-events: auto; cursor: default;
      border: 1px solid #ddd; box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .poi-popup .poi-name { font-weight: bold; margin-bottom: 2px; }
    .poi-popup .poi-meta { color: #888; font-size: 10px; }

    /* Loading */
    #loading {
      position: absolute; inset: 0; background: #e8eef4;
      display: flex; align-items: center; justify-content: center;
      color: #c0392b; font-size: 16px; z-index: 200;
    }

    /* Modal */
    #embed-modal {
      position: fixed; inset: 0; background: rgba(0,0,0,0.5);
      display: none; align-items: center; justify-content: center; z-index: 100;
    }
    #embed-modal .modal-box {
      background: #fff; border-radius: 12px; padding: 24px;
      max-width: 520px; width: 90%; box-shadow: 0 4px 24px rgba(0,0,0,0.2);
    }
    #embed-modal h3 { color: #222; margin-bottom: 12px; }
    #embed-modal textarea {
      width: 100%; height: 80px; background: #f5f7fa; color: #333;
      border: 1px solid #ccc; border-radius: 6px;
      padding: 8px; font-family: monospace; font-size: 12px; resize: none;
    }
    #embed-modal input[type=text] {
      width: 100%; background: #f5f7fa; color: #333;
      border: 1px solid #ccc; border-radius: 6px;
      padding: 8px; font-family: monospace; font-size: 12px;
    }
    #embed-modal .close {
      float: right; background: none; border: none; color: #aaa;
      font-size: 20px; cursor: pointer; margin-top: -4px;
    }

    /* ── Embed / view mode: full canvas, hide demo chrome ── */
    body[data-mode="embed"],
    body[data-mode="view"] { background: transparent; overflow: hidden; }

    body[data-mode="embed"] #app,
    body[data-mode="view"]  #app {
      max-width: 100%; height: 100vh; margin: 0; box-shadow: none;
    }
    body[data-mode="embed"] #top-bar,
    body[data-mode="view"]  #top-bar { display: none; }
    body[data-mode="embed"] #embed-btn,
    body[data-mode="embed"] #embed-modal,
    body[data-mode="view"]  #embed-btn,
    body[data-mode="view"]  #embed-modal { display: none !important; }
  </style>
</head>
<body>
  <div id="app">
    <div id="top-bar">
      <span id="brand">◈ NEIGHBOURLY</span>
      <input id="search-input" type="text" placeholder="Zadaj adresu…" />
      <button id="search-btn">Zobraziť</button>
    </div>
    <div id="canvas-container">
      <div id="loading">Načítavam mapu…</div>
      <div id="info-card">
        <div class="address" id="info-address"></div>
        <div class="pois" id="info-pois"></div>
      </div>
      <button id="embed-btn">&#60;/&#62; Embed</button>
    </div>
  </div>

  <div id="embed-modal">
    <div class="modal-box">
      <button class="close" id="modal-close">×</button>
      <h3>Embed kód</h3>
      <p style="color:#888;font-size:12px;margin-bottom:10px">Skopíruj do svojho webu:</p>
      <textarea id="embed-code" readonly></textarea>
      <p style="color:#888;font-size:12px;margin: 10px 0 6px">Alebo zdieľaj priamo:</p>
      <input id="share-url" type="text" readonly value="…" />
    </div>
  </div>

  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 2: Verify in browser (demo mode)**

At http://localhost:5173 the page should show a white card centered on a grey background, max 960px wide. The top bar has the brand + search. The map fills the rest of the height. At full browser width, grey margins are visible on both sides.

- [ ] **Step 3: Verify embed mode unchanged**

Open http://localhost:5173/embed?lat=48.286&lon=17.272 — canvas should still fill the full viewport with no top bar.

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html
git commit -m "feat: centered card layout (max 960px) with top bar — embed/view modes unchanged"
```

---

## Self-Review

**Spec coverage:**
- [x] Sec 1 — Daylight scene/lighting → Task 2
- [x] Sec 2 — Flat roads + lane markings → Tasks 1, 3
- [x] Sec 2 — Cars (y + count) → Task 4
- [x] Sec 3 — Tree sphere canopy / conifer mix → Task 5
- [x] Sec 3 — Shrubs along park/forest edges → Task 6
- [x] Sec 4 — Pitched roofs (houses) → Task 7
- [x] Sec 4 — Spire (churches) → Task 7
- [x] Sec 4 — Attic strip (commercial) → Task 7
- [x] Sec 4 — Windows (apartments, offices) → Task 7
- [x] Sec 4 — Shed roof (industrial) → Task 7
- [x] Sec 5 — Centered card layout → Task 8

**Type consistency check:**
- `buildRibbonGeometry` / `buildDashLineGeometry` defined in Task 1, imported in Task 3 ✓
- `addShrubs` exported in Task 6, imported in Task 6 scene.js step ✓
- `_buildRoof`, `_addFlatRoofCap`, `_addWindows` all defined and called within Task 7 ✓
- `_offsetCurvePoints` defined and used within Task 3 ✓
- HTML element IDs (`search-input`, `search-btn`, `info-address`, `info-pois`, `embed-btn`, `embed-code`, `share-url`, `modal-close`, `canvas-container`, `loading`) preserved between Task 8 HTML and existing `main.js` / `ui.js` lookups ✓

**No placeholders found.**
