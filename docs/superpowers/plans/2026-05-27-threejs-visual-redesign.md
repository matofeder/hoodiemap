# Three.js Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Three.js frontend to match a compact isometric city infographic style — vivid lime-green background, detailed buildings with window textures, lush lollipop trees, visible shadows, and working animations.

**Architecture:** All changes are pure visual/CSS — no new data structures, no API changes, no new files beyond helpers added inline. Each task is self-contained and visually verifiable at `http://localhost:5173` by searching "Pezinok". Backend Python tests (`pytest -q`) are unaffected by all changes but run after each commit as a sanity check.

**Tech Stack:** Three.js r168, Vite 5, vanilla JS, HTML/CSS

---

## File Map

| File | What changes |
|------|-------------|
| `frontend/src/colors.js` | Replace `BUILDING_COLORS` and `BUILDING_COLOR_DEFAULT` |
| `frontend/src/scene.js` | Camera, lighting, background, ground color, `_makeWindowTexture`, `MeshStandardMaterial` for buildings, WebGL2 check |
| `frontend/src/animations.js` | Lollipop trees (`_makeTree`), procedural park/street trees, bigger cars, bigger pedestrians, cyclist scale, NUM_CARS 12, sway amplitude |
| `frontend/index.html` | Remove oval vignette from `#threejs-mount`, restyle `.outer-poi-pill` to white |

---

## Task 1: Building Color Palette

**Files:**
- Modify: `frontend/src/colors.js:23-37`

- [ ] **Step 1: Replace BUILDING_COLORS in colors.js**

Replace the entire `BUILDING_COLORS` block and `BUILDING_COLOR_DEFAULT` (lines 23–37):

```js
export const BUILDING_COLORS = {
  house:        '#E8DCC8', detached:    '#E8DCC8', bungalow:  '#E4D8C0',
  apartments:   '#E4E0DA', residential: '#E4E0DA', terrace:   '#DDD8D0',
  commercial:   '#C8DCE8', retail:      '#C8DCE8', shop:      '#C8DCE8',
  supermarket:  '#C8DCE8', kiosk:       '#D0D8E0',
  office:       '#B8CCE0', civic:       '#B8CCE0', public:    '#B8CCE0',
  government:   '#B8CCE0',
  church:       '#E0D8CC', cathedral:   '#E0D8CC', chapel:    '#E0D8CC',
  school:       '#D4E8D0', university:  '#D4E8D0', college:   '#D4E8D0',
  hospital:     '#E8E4DC', clinic:      '#E8E4DC',
  industrial:   '#D0CCC4', warehouse:   '#D0CCC4', factory:   '#D0CCC4',
  garage:       '#D4D0C8', garages:     '#D4D0C8',
  parking:      '#CCCCC4', yes:         '#E0DCD4',
};
export const BUILDING_COLOR_DEFAULT = '#E0DCD4';
```

- [ ] **Step 2: Run backend tests**

```bash
cd /home/mato/Dev/tf/genmap && pytest -q
```

Expected: all tests pass (green).

- [ ] **Step 3: Open browser and verify**

Open `http://localhost:5173`, search "Pezinok". Buildings should now show lighter, cleaner tones: white/gray residential, light-blue commercial/office.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/colors.js
git commit -m "feat: update building color palette to lighter isometric style"
```

---

## Task 2: Camera, Lighting, Background, Ground

**Files:**
- Modify: `frontend/src/scene.js:29,55,63-64,67,70-73,150`

- [ ] **Step 1: Change background color (line 29)**

```js
// was: scene.background = new THREE.Color(0x87ceeb);
scene.background = new THREE.Color(0x7ec850);
```

- [ ] **Step 2: Change camera position (line 55)**

```js
// was: camera.position.set(0, 380, 560);
camera.position.set(0, 220, 340);
```

- [ ] **Step 3: Change controls distances (lines 63–64)**

```js
// was: controls.minDistance = 50;
controls.minDistance = 80;
// was: controls.maxDistance = 1200;
controls.maxDistance = 700;
```

- [ ] **Step 4: Change ambient light intensity (line 67)**

```js
// was: const ambient = new THREE.AmbientLight(0xffffff, 1.0);
const ambient = new THREE.AmbientLight(0xffffff, 0.45);
```

- [ ] **Step 5: Change sun intensity, position, and shadow map (lines 70–73)**

```js
// was: const sun = new THREE.DirectionalLight(0xfff5e0, 1.4);
const sun = new THREE.DirectionalLight(0xfff5e0, 1.6);
// was: sun.position.set(300, 500, 200);
sun.position.set(200, 400, 150);
// was: sun.shadow.mapSize.set(1024, 1024);
sun.shadow.mapSize.set(2048, 2048);
```

- [ ] **Step 6: Add WebGL2 check after renderer is created (after line 38, before `container.appendChild`)**

Find the block after `renderer.setSize(...)` and before `container.innerHTML = ''`. Insert:

```js
if (!renderer.capabilities.isWebGL2) {
  console.warn('WebGL2 not available — animations may be slow');
}
```

The full renderer block at that point should look like:

```js
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.setSize(container.clientWidth || window.innerWidth, container.clientHeight || window.innerHeight);
if (!renderer.capabilities.isWebGL2) {
  console.warn('WebGL2 not available — animations may be slow');
}
container.innerHTML = '';
container.appendChild(renderer.domElement);
```

- [ ] **Step 7: Change ground color (line 150)**

In `_addGround`, change the material color:

```js
// was: const mat = new THREE.MeshLambertMaterial({ color: 0xc8bfb0 });
const mat = new THREE.MeshLambertMaterial({ color: 0xd8d4cc });
```

- [ ] **Step 8: Run backend tests**

```bash
cd /home/mato/Dev/tf/genmap && pytest -q
```

Expected: all tests pass.

- [ ] **Step 9: Open browser and verify**

Open `http://localhost:5173`, search "Pezinok". Verify:
- Background is vivid lime green (not sky blue)
- Scene is zoomed in — buildings fill the viewport (~40% closer than before)
- Building shadows are clearly visible on the ground (ambient was 1.0, now 0.45 lets sun dominate)

- [ ] **Step 10: Commit**

```bash
git add frontend/src/scene.js
git commit -m "feat: compact camera, vivid green background, shadows visible via lower ambient"
```

---

## Task 3: Window Texture + MeshStandardMaterial for Buildings

**Files:**
- Modify: `frontend/src/scene.js:240-414`

This task replaces the old box-geometry window approach with canvas-texture windows on building walls, and switches wall/roof materials to `MeshStandardMaterial` for better depth.

- [ ] **Step 1: Add `_makeWindowTexture` helper before `_addBuildings` (before line 240)**

Insert this function:

```js
function _makeWindowTexture(seed) {
  const W = 64, H = 128;
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#3a4050';
  ctx.fillRect(0, 0, W, H);

  const cols = 4, rows = 8, ww = 10, wh = 10, gx = 6, gy = 6;
  let s = seed;
  const rand = () => { s = (s * 1664525 + 1013904223) & 0xffffffff; return (s >>> 0) / 0xffffffff; };

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      ctx.fillStyle = rand() > 0.35 ? '#fffbe8' : '#222830';
      ctx.fillRect(gx + c * (ww + gx), gy + r * (wh + gy), ww, wh);
    }
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  return tex;
}
```

- [ ] **Step 2: Rewrite `_addBuildings` to use MeshStandardMaterial + window texture**

Replace the entire `_addBuildings` function (lines 240–268):

```js
function _addBuildings(scene, buildings) {
  buildings.forEach((b, i) => {
    const colorHex = BUILDING_COLORS[b.type] || BUILDING_COLOR_DEFAULT;

    const fp = b.footprint;
    if (!fp || fp.length < 3) return;

    try {
      const shape = new THREE.Shape(fp.map(([x, y]) => new THREE.Vector2(x, y)));
      const extGeo = new THREE.ExtrudeGeometry(shape, {
        depth: b.height,
        bevelEnabled: false,
      });
      extGeo.rotateX(-Math.PI / 2);

      let wallMat;
      if (b.height > 6) {
        const wallTex = _makeWindowTexture(i * 7919);
        wallMat = new THREE.MeshStandardMaterial({
          color: new THREE.Color(colorHex),
          map: wallTex,
          roughness: 0.85,
          metalness: 0.05,
        });
      } else {
        wallMat = new THREE.MeshStandardMaterial({
          color: new THREE.Color(colorHex),
          roughness: 0.85,
          metalness: 0.05,
        });
      }

      const mesh = new THREE.Mesh(extGeo, wallMat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      scene.add(mesh);

      const roofGroup = _buildRoof(b.type || 'yes', fp, b.height, colorHex);
      scene.add(roofGroup);
    } catch (err) {
      console.warn('_addBuildings: skipped footprint', b, err);
    }
  });
}
```

- [ ] **Step 3: Update `_buildRoof` — switch to MeshStandardMaterial + 0.82 scalar**

In `_buildRoof` (line 270), there are three places that create roof materials. Replace all three:

*HOUSE_TYPES block* (line 282):
```js
// was: const color = new THREE.Color(baseColorHex).multiplyScalar(0.75);
// was: const mat = new THREE.MeshLambertMaterial({ color, side: THREE.DoubleSide });
const color = new THREE.Color(baseColorHex).multiplyScalar(0.82);
const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.85, metalness: 0.05, side: THREE.DoubleSide });
```

*INDUSTRIAL_TYPES block* (line 331):
```js
// was: const color = new THREE.Color(baseColorHex).multiplyScalar(0.80);
// was: const mat = new THREE.MeshLambertMaterial({ color, side: THREE.DoubleSide });
const color = new THREE.Color(baseColorHex).multiplyScalar(0.82);
const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.85, metalness: 0.05, side: THREE.DoubleSide });
```

*Church spire* (line 313) — keep as-is (purple, not a wall color).

*Remove `_addWindows` calls* from `_buildRoof`:
- Line 323: Remove `_addWindows(group, footprint, height);` (in APARTMENT_TYPES block)
- Line 326: Remove `_addWindows(group, footprint, height);` (in OFFICE_TYPES block)

- [ ] **Step 4: Update `_addFlatRoofCap` — switch to MeshStandardMaterial + 0.82 scalar**

Replace the entire `_addFlatRoofCap` function (lines 359–369):

```js
function _addFlatRoofCap(group, footprint, height, baseColorHex) {
  const color = new THREE.Color(baseColorHex).multiplyScalar(0.82);
  try {
    const shape = new THREE.Shape(footprint.map(([x, y]) => new THREE.Vector2(x, y)));
    const geo = new THREE.ShapeGeometry(shape);
    geo.rotateX(-Math.PI / 2);
    geo.translate(0, height, 0);
    const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.85, metalness: 0.05 });
    group.add(new THREE.Mesh(geo, mat));
  } catch (_) {}
}
```

- [ ] **Step 5: Delete the `_addWindows` function (lines 371–414)**

Remove the entire `_addWindows` function. It is replaced by the canvas texture approach.

- [ ] **Step 6: Run backend tests**

```bash
cd /home/mato/Dev/tf/genmap && pytest -q
```

Expected: all tests pass.

- [ ] **Step 7: Open browser and verify**

Open `http://localhost:5173`, search "Pezinok". Verify:
- Taller buildings show a repeating window-grid texture on their walls
- Roofs appear slightly darker than walls
- Buildings have subtle specular highlights (MeshStandardMaterial effect)
- No box-geometry window strips visible on apartment/office buildings

- [ ] **Step 8: Commit**

```bash
git add frontend/src/scene.js
git commit -m "feat: canvas window textures and MeshStandardMaterial on buildings"
```

---

## Task 4: Lollipop Trees + Procedural Density

**Files:**
- Modify: `frontend/src/animations.js`
- Modify: `frontend/src/scene.js:97-101` (consume tickers from addShrubs)

- [ ] **Step 1: Add `_makeTree` helper in animations.js (before `_addTrees`)**

Insert after the existing import line at the top, before `export function addAnimations`:

```js
function _makeTree(scene, x, z, index) {
  const h = 5 + (index % 4);
  const r = 5 + (index % 5) * 0.8;
  const phase = index * 1.3;

  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x8b6343, roughness: 0.9 });
  const trunkGeo = new THREE.CylinderGeometry(0.35, 0.5, h, 6);
  const trunk = new THREE.Mesh(trunkGeo, trunkMat);
  trunk.position.set(x, h / 2, z);
  trunk.castShadow = true;
  scene.add(trunk);

  const palette = [0x5db84a, 0x4ea83c, 0x68c455, 0x52a040];
  const canopyMat = new THREE.MeshStandardMaterial({
    color: palette[index % palette.length],
    roughness: 0.8,
  });
  const canopyGeo = new THREE.SphereGeometry(r, 8, 6);
  const canopy = new THREE.Mesh(canopyGeo, canopyMat);
  canopy.position.set(x, h + r * 0.65, z);
  canopy.castShadow = true;
  scene.add(canopy);

  return { canopy, trunk, phase };
}
```

- [ ] **Step 2: Replace `_addTrees` with lollipop version**

Replace the entire `_addTrees` function (lines 21–61):

```js
function _addTrees(scene, trees) {
  const tickers = [];
  trees.forEach((tree, i) => {
    const { canopy, trunk, phase } = _makeTree(scene, tree.x, -tree.y, i);
    tickers.push(t => {
      const sway = Math.sin(t * 0.8 + phase) * 0.04;
      canopy.rotation.z = sway;
      trunk.rotation.z = sway * 0.4;
    });
  });
  return tickers;
}
```

- [ ] **Step 3: Add `_pointInPolygon` helper in animations.js (after `_makeTree`)**

```js
function _pointInPolygon(px, py, polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    if (((yi > py) !== (yj > py)) && (px < (xj - xi) * (py - yi) / (yj - yi) + xi)) {
      inside = !inside;
    }
  }
  return inside;
}
```

- [ ] **Step 4: Add `_addParkTrees` helper**

Insert after `_pointInPolygon`:

```js
function _addParkTrees(scene, geoLayers, startIndex) {
  const tickers = [];
  const parks = geoLayers?.park;
  if (!parks) return tickers;

  let idx = startIndex;
  const GRID = 20;

  for (const ring of parks) {
    if (!ring || ring.length < 3) continue;
    const xs = ring.map(([x]) => x);
    const ys = ring.map(([, y]) => y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);

    for (let gx = minX + GRID / 2; gx < maxX; gx += GRID) {
      for (let gy = minY + GRID / 2; gy < maxY; gy += GRID) {
        const jx = gx + (Math.random() - 0.5) * GRID * 0.8;
        const jy = gy + (Math.random() - 0.5) * GRID * 0.8;
        if (!_pointInPolygon(jx, jy, ring)) continue;
        const { canopy, trunk, phase } = _makeTree(scene, jx, -jy, idx);
        tickers.push(t => {
          const sway = Math.sin(t * 0.8 + phase) * 0.04;
          canopy.rotation.z = sway;
          trunk.rotation.z = sway * 0.4;
        });
        idx++;
      }
    }
  }
  return tickers;
}
```

- [ ] **Step 5: Add `_addStreetTrees` helper**

Insert after `_addParkTrees`:

```js
const STREET_TREE_TYPES = new Set(['residential', 'tertiary', 'unclassified']);

function _addStreetTrees(scene, roads, startIndex) {
  const tickers = [];
  let idx = startIndex;
  const SPACING = 18;
  const SIDE_OFFSET = 3;

  for (const road of roads) {
    if (!STREET_TREE_TYPES.has(road.type)) continue;
    const pts = road.points;
    if (pts.length < 2) continue;

    let accumulated = 0;
    const side = idx % 2 === 0 ? 1 : -1;

    for (let i = 0; i < pts.length - 1; i++) {
      const [x0, y0] = pts[i];
      const [x1, y1] = pts[i + 1];
      const segLen = Math.hypot(x1 - x0, y1 - y0);
      const dx = (x1 - x0) / segLen;
      const dy = (y1 - y0) / segLen;
      let t = accumulated === 0 ? 0 : SPACING - accumulated;

      while (t <= segLen) {
        const tx = x0 + dx * t + (-dy) * SIDE_OFFSET * side;
        const ty = y0 + dy * t + dx * SIDE_OFFSET * side;
        const { canopy, trunk, phase } = _makeTree(scene, tx, -ty, idx);
        tickers.push(tt => {
          const sway = Math.sin(tt * 0.8 + phase) * 0.04;
          canopy.rotation.z = sway;
          trunk.rotation.z = sway * 0.4;
        });
        idx++;
        t += SPACING;
      }
      accumulated = (accumulated + segLen) % SPACING;
    }
  }
  return tickers;
}
```

- [ ] **Step 6: Rewrite `addShrubs` to use the new helpers and return tickers**

Replace the entire `addShrubs` function and the old helper functions below it (`_placeShrub`, `SHRUB_COLORS`, `MAX_SHRUBS`). Remove lines 236–296 and replace with:

```js
const MAX_PROC_TREES = 400;

export function addShrubs(scene, sceneData) {
  const tickers = [];
  const osmCount = sceneData.trees?.length ?? 0;
  let remaining = MAX_PROC_TREES;

  const parkTickers = _addParkTrees(scene, sceneData.geo_layers, osmCount);
  const capped = parkTickers.slice(0, remaining);
  tickers.push(...capped);
  remaining -= capped.length;

  if (remaining > 0) {
    const streetTickers = _addStreetTrees(scene, sceneData.roads ?? [], osmCount + capped.length);
    tickers.push(...streetTickers.slice(0, remaining));
  }

  return tickers;
}
```

- [ ] **Step 7: Update scene.js to consume tickers from addShrubs**

In `frontend/src/scene.js`, find the animation setup block (around lines 97–101):

```js
// Change:
const animatables = [
  ...addAnimations(scene, sceneData),
  ...addCyclists(scene, sceneData.roads),
];
addShrubs(scene, sceneData);

// To:
const animatables = [
  ...addAnimations(scene, sceneData),
  ...addCyclists(scene, sceneData.roads),
  ...addShrubs(scene, sceneData),
];
```

- [ ] **Step 8: Run backend tests**

```bash
cd /home/mato/Dev/tf/genmap && pytest -q
```

Expected: all tests pass.

- [ ] **Step 9: Open browser and verify**

Open `http://localhost:5173`, search "Pezinok". Verify:
- All trees are round lollipop spheres — no cones visible
- Parks are densely filled with trees (not just perimeter shrubs)
- Trees appear along residential streets
- Trees sway gently in the animation loop
- Total visible trees is much higher than before (was 28 OSM points, now 150+ expected)

- [ ] **Step 10: Commit**

```bash
git add frontend/src/animations.js frontend/src/scene.js
git commit -m "feat: lollipop trees with procedural park and street placement"
```

---

## Task 5: Bigger Vehicles

**Files:**
- Modify: `frontend/src/animations.js:68,72-95,135-152,301-329,335`

- [ ] **Step 1: Change NUM_CARS to 12 (line 68)**

```js
// was: const NUM_CARS = 8;
const NUM_CARS = 12;
```

- [ ] **Step 2: Rewrite `_makeCar` with larger body**

Replace the entire `_makeCar` function (lines 70–95):

```js
function _makeCar(color) {
  const group = new THREE.Group();
  const bodyGeo = new THREE.BoxGeometry(3.5, 1.2, 6.0);
  const bodyMat = new THREE.MeshLambertMaterial({ color });
  const body = new THREE.Mesh(bodyGeo, bodyMat);
  body.position.y = 0.8;
  body.castShadow = true;
  group.add(body);

  const cabinGeo = new THREE.BoxGeometry(2.8, 1.0, 3.8);
  const cabin = new THREE.Mesh(cabinGeo, bodyMat);
  cabin.position.set(0, 1.9, -0.4);
  cabin.castShadow = true;
  group.add(cabin);

  const wheelGeo = new THREE.CylinderGeometry(0.5, 0.5, 0.35, 8);
  wheelGeo.rotateZ(Math.PI / 2);
  const wheelMat = new THREE.MeshLambertMaterial({ color: 0x222222 });
  [[-1.75, 2.2], [-1.75, -2.2], [1.75, 2.2], [1.75, -2.2]].forEach(([wx, wz]) => {
    const wheel = new THREE.Mesh(wheelGeo, wheelMat);
    wheel.position.set(wx, 0.5, wz);
    group.add(wheel);
  });

  return group;
}
```

- [ ] **Step 3: Rewrite `_makePedestrian` with height 2.2**

Replace the entire `_makePedestrian` function (lines 138–152):

```js
function _makePedestrian(color) {
  const group = new THREE.Group();
  const bodyGeo = new THREE.CapsuleGeometry(0.35, 1.3, 4, 6);
  const mat = new THREE.MeshLambertMaterial({ color });
  const body = new THREE.Mesh(bodyGeo, mat);
  body.position.y = 1.1;
  group.add(body);

  const headGeo = new THREE.SphereGeometry(0.3, 6, 6);
  const head = new THREE.Mesh(headGeo, mat);
  head.position.y = 2.1;
  group.add(head);

  return group;
}
```

- [ ] **Step 4: Scale each cyclist by 1.4× in `addCyclists`**

In `addCyclists`, after `const cyclist = _makeCyclist(...)` (around line 338), add:

```js
cyclist.scale.setScalar(1.4);
```

The block should look like:

```js
for (let i = 0; i < NUM_CYCLISTS; i++) {
  const baseCurve = curves[i % curves.length];
  const lane = _offsetCurve(baseCurve, 1.8);
  const cyclist = _makeCyclist(CYCLIST_COLORS[i % CYCLIST_COLORS.length]);
  cyclist.scale.setScalar(1.4);
  scene.add(cyclist);
  ...
```

- [ ] **Step 5: Run backend tests**

```bash
cd /home/mato/Dev/tf/genmap && pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Open browser and verify**

Open `http://localhost:5173`, search "Pezinok". Verify:
- Cars are visibly larger and more prominent
- 12 cars visible on roads (was 8)
- Pedestrians are taller/heavier
- Cyclists are noticeably bigger

- [ ] **Step 7: Commit**

```bash
git add frontend/src/animations.js
git commit -m "feat: bigger cars (3.5×1.2×6), taller pedestrians, larger cyclists, 12 cars"
```

---

## Task 6: Remove Oval Frame + Restyle Outer POI Pins

**Files:**
- Modify: `frontend/index.html`

The dark oval vignette is created by `border-radius: 50%` and `mask-image` on `#threejs-mount`. The outer POI pills currently use a dark background (`rgba(15, 20, 35, 0.88)`); they get a white background with the existing colored dot as the category accent.

- [ ] **Step 1: Remove oval vignette from `#threejs-mount`**

Find the `#threejs-mount` rule in the `<style>` block:

```css
/* Current: */
#threejs-mount {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  -webkit-mask-image: radial-gradient(circle, black 58%, transparent 100%);
  mask-image: radial-gradient(circle, black 58%, transparent 100%);
  overflow: hidden;
}
```

Replace with:

```css
#threejs-mount {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
```

- [ ] **Step 2: Change `#canvas-container` background**

Find the `#canvas-container` rule:

```css
/* Current includes: background: #111827; */
```

Change:

```css
/* was: background: #111827; */
background: transparent;
```

- [ ] **Step 3: Restyle `.outer-poi-pill` to white background**

Find the `.outer-poi-pill` rule:

```css
/* Current: */
.outer-poi-pill {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  background: rgba(15, 20, 35, 0.88);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 8px;
  padding: 5px 9px;
  min-width: 90px;
  max-width: 140px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.5);
  backdrop-filter: blur(4px);
}
```

Replace with:

```css
.outer-poi-pill {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  background: rgba(255,255,255,0.95);
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 8px;
  padding: 5px 9px;
  min-width: 90px;
  max-width: 140px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.15);
  backdrop-filter: blur(4px);
}
```

- [ ] **Step 4: Update POI text colors to match white background**

Find `.outer-poi-name`:
```css
/* was: color: #f0f0f0; */
color: #1a1a1a;
```

Find `.outer-poi-meta`:
```css
/* was: color: #9ca3af; */
color: #666666;
```

- [ ] **Step 5: Run backend tests**

```bash
cd /home/mato/Dev/tf/genmap && pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Open browser and verify**

Open `http://localhost:5173`, search "Pezinok". Verify:
- No dark oval ring around the 3D scene — full rectangular view
- Outer POI pills are white/light with dark text
- Colored dot in each pill still visible as the category accent
- Scene fills the full map area

- [ ] **Step 7: Commit**

```bash
git add frontend/index.html
git commit -m "feat: remove oval vignette, restyle outer POI pins to white"
```

---

## Self-Review Notes

**Spec coverage check:**
- Layer 1 (bg/camera/lighting): Task 2 ✓
- Layer 2 (building colors): Task 1 ✓; MeshStandardMaterial + `0.82` scalar: Task 3 ✓
- Layer 3 (window textures): Task 3 ✓
- Layer 4 (lollipop trees + procedural): Task 4 ✓
- Layer 5 (cars/pedestrians bigger, WebGL debug, oval removal): Tasks 5 + 6 ✓; WebGL check: Task 2 Step 6 ✓

**Execution order note:** Tasks 1–6 are independent enough to run in sequence. Task 4 Step 7 modifies `scene.js` — if Task 3 already touched `scene.js`, ensure both edits are applied to the same file state.
