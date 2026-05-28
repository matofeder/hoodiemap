# Visual Refresh v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dark theme with a clean light blue-gray style, fix the camera to face north, and fix the animation bug (cars/cyclists/pedestrians spawning on roads outside the visible area).

**Architecture:** Three independent changes across two files. Task 1 fixes the root cause of invisible animations (road proximity filter). Task 2 changes scene.js camera/fog/background. Task 3 rewrites the CSS in index.html. All changes are frontend-only — no backend code touched.

**Tech Stack:** Three.js r168+, Vite 5, vanilla JS/CSS, vitest

---

## File Map

```
frontend/
  src/animations.js   modify  — add maxDist filter to _buildRoadCurves; thread parameter through _addCars, _addPedestrians, addCyclists
  src/scene.js        modify  — camera position/FOV, remove fog, light background, sun position, addCyclists call
  index.html          modify  — full CSS color swap to light blue-gray, widget width 1200→1340px
```

---

## Task 1: Fix animation road filter in `animations.js` + `scene.js`

**Root cause:** `_buildRoadCurves` picks from all roads in `sceneData.roads`, which includes roads up to 3000m from center (the full OSM fetch radius). The display area is only 450m. 946 of 1151 qualifying roads are outside the visible area. Cars/cyclists/pedestrians spawn and drive on those invisible roads.

**Fix:** Filter roads to those with at least one point within `display_radius_m * 1.2` of center.

**Files:**
- Modify: `frontend/src/animations.js`
- Modify: `frontend/src/scene.js` (line 74 only)

- [ ] **Step 1: Update `_buildRoadCurves` to accept and apply `maxDist`**

In `frontend/src/animations.js`, find `function _buildRoadCurves(roads)` (line 97) and replace the entire function:

```js
function _buildRoadCurves(roads, maxDist = null) {
  return roads
    .filter(r => MAJOR_ROAD_TYPES.has(r.type) && r.points.length >= 2)
    .filter(r => maxDist == null || r.points.some(([x, y]) => Math.hypot(x, y) <= maxDist))
    .map(r => {
      const pts = r.points.map(([x, y]) => new THREE.Vector3(x, 0.5, -y));
      return new THREE.CatmullRomCurve3(pts);
    })
    .filter(c => c.getLength() > 30);
}
```

- [ ] **Step 2: Thread `maxDist` through `_addCars` and `_addPedestrians`**

Find `function _addCars(scene, roads)` (line 107). Change signature and internal call:

```js
function _addCars(scene, roads, maxDist) {
  const curves = _buildRoadCurves(roads, maxDist);
```

Find `function _addPedestrians(scene, roads)` (line 170). Same change:

```js
function _addPedestrians(scene, roads, maxDist) {
  const curves = _buildRoadCurves(roads, maxDist);
```

- [ ] **Step 3: Pass `maxDist` from `addAnimations`**

Find `export function addAnimations(scene, sceneData)` (line 7). Replace the function body:

```js
export function addAnimations(scene, sceneData) {
  const tickers = [];
  const maxDist = (sceneData.display_radius_m || 600) * 1.2;

  tickers.push(..._addTrees(scene, sceneData.trees));
  tickers.push(..._addCars(scene, sceneData.roads, maxDist));
  tickers.push(..._addPedestrians(scene, sceneData.roads, maxDist));
  tickers.push(_addCenterPin(scene));

  return tickers;
}
```

- [ ] **Step 4: Thread `maxDist` through `addCyclists`**

Find `export function addCyclists(scene, roads)` (line 331). Change signature and internal call:

```js
export function addCyclists(scene, roads, maxDist) {
  const curves = _buildRoadCurves(roads, maxDist);
```

- [ ] **Step 5: Update `addCyclists` call in `scene.js`**

In `frontend/src/scene.js`, find line 74:
```js
    ...addCyclists(scene, sceneData.roads),
```
Replace with:
```js
    ...addCyclists(scene, sceneData.roads, (sceneData.display_radius_m || 600) * 1.2),
```

- [ ] **Step 6: Verify build and tests pass**

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm test 2>&1 | tail -10
```
Expected: all tests pass (no animation tests exist, but no regressions either)

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm run build 2>&1 | tail -5
```
Expected: `✓ built in ...ms`

- [ ] **Step 7: Commit**

```bash
cd /home/mato/Dev/tf/genmap && git add frontend/src/animations.js frontend/src/scene.js && git commit -m "fix: filter animation roads to display radius — cars/cyclists/pedestrians were spawning off-screen"
```

---

## Task 2: Update `scene.js` — camera, remove fog, light background

**Files:**
- Modify: `frontend/src/scene.js`

- [ ] **Step 1: Replace scene background and remove fog**

In `frontend/src/scene.js`, find lines 27–28:
```js
  scene.background = new THREE.Color(0x0d1b2a);
  scene.fog = new THREE.Fog(0x0d1b2a, 500, 900);
```
Replace with:
```js
  scene.background = new THREE.Color(0xF0F4F8);
```
(Delete the fog line entirely — do not replace it with anything.)

- [ ] **Step 2: Fix camera position and FOV**

Find lines 43–45:
```js
  const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 2000);
  camera.position.set(-280, 320, 280);
  camera.lookAt(0, 0, 0);
```
Replace with:
```js
  const camera = new THREE.PerspectiveCamera(42, W / H, 0.1, 2000);
  camera.position.set(0, 380, 520);
  camera.lookAt(0, 0, 0);
```

- [ ] **Step 3: Adjust sun position for south-facing illumination**

Find line 52:
```js
  sun.position.set(300, 500, 200);
```
Replace with:
```js
  sun.position.set(200, 500, 300);
```

- [ ] **Step 4: Verify build and tests pass**

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm test 2>&1 | tail -10
```
Expected: all tests pass

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm run build 2>&1 | tail -5
```
Expected: `✓ built in ...ms`

- [ ] **Step 5: Commit**

```bash
cd /home/mato/Dev/tf/genmap && git add frontend/src/scene.js && git commit -m "feat: scene.js — south-oblique camera facing north, remove fog, light background"
```

---

## Task 3: Light theme CSS + widget size in `index.html`

**Files:**
- Modify: `frontend/index.html`

Replace the entire `<style>` block (lines 7–202) with the following. Keep `<html>`, `<head>` meta tags, `<body>` content and `<script>` tag unchanged — only the style block changes.

- [ ] **Step 1: Replace the `<style>` block**

Replace everything from `<style>` to `</style>` (inclusive) with:

```html
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      background: #E8EDF2;
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
      background: #E8EDF2;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #1E2D3D;
      font-size: 14px;
      z-index: 100;
    }

    /* ── Infographic shell ───────────────────────────────── */
    #app { width: 1340px; }

    .infographic-root {
      width: 1340px;
      background: #F5F7FA;
      border: 1px solid rgba(0, 0, 0, 0.10);
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 8px 40px rgba(0, 0, 0, 0.12);
    }

    /* ── Header ─────────────────────────────────────────── */
    .infographic-header {
      height: 44px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      border-bottom: 1px solid rgba(0, 0, 0, 0.08);
      background: rgba(255, 255, 255, 0.7);
    }
    .infographic-title {
      color: #1E2D3D;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 3px;
    }
    .infographic-address {
      color: #6B7A8D;
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
      background: #FFFFFF;
    }
    .infographic-panel-left {
      border-right: 1px solid rgba(0, 0, 0, 0.07);
    }
    .infographic-panel-right {
      border-left: 1px solid rgba(0, 0, 0, 0.07);
    }

    /* ── POI cards ───────────────────────────────────────── */
    .poi-card {
      background: #F0F4F8;
      border-left: 3px solid var(--cat-color, #888);
      border-radius: 0 5px 5px 0;
      padding: 8px 10px;
    }
    .poi-card-emoji-name {
      font-size: 11px;
      font-weight: 600;
      color: #1E2D3D;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-bottom: 3px;
    }
    .poi-card-meta {
      font-size: 10px;
      color: #6B7A8D;
      margin-bottom: 6px;
    }
    .poi-card-bar-track {
      height: 3px;
      background: rgba(0, 0, 0, 0.08);
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
      background: #F0F4F8;
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
      border-top: 1px solid rgba(0, 0, 0, 0.07);
      background: #F8FAFC;
      overflow-x: auto;
    }
    .infographic-strip::-webkit-scrollbar { display: none; }
    .transport-pill {
      flex-shrink: 0;
      background: #FFFFFF;
      border: 1px solid rgba(0, 0, 0, 0.12);
      border-radius: 12px;
      padding: 3px 11px;
      font-size: 10px;
      color: #4A5568;
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
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid rgba(0, 0, 0, 0.12);
      border-radius: 10px;
      padding: 3px 8px;
      font-size: 9px;
      color: #1E2D3D;
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
    .outer-poi-meta { color: #6B7A8D; font-size: 8px; }
    .outer-poi-indicator.active .outer-poi-pill {
      border-color: rgba(0, 0, 0, 0.25);
      background: rgba(255, 255, 255, 0.98);
    }

    /* ── Scale down on small screens ────────────────────── */
    @media (max-width: 1400px) {
      body { align-items: flex-start; padding: 16px; }
      #app {
        transform-origin: top left;
        transform: scale(0.75);
      }
    }
  </style>
```

- [ ] **Step 2: Verify build and tests pass**

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm test 2>&1 | tail -10
```
Expected: all tests pass

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm run build 2>&1 | tail -5
```
Expected: `✓ built in ...ms`

- [ ] **Step 3: Commit**

```bash
cd /home/mato/Dev/tf/genmap && git add frontend/index.html && git commit -m "feat: light blue-gray theme — CSS color refresh + widget width 1340px"
```

---

## Task 4: Visual smoke test

- [ ] **Step 1: Run Python tests (confirm backend unaffected)**

```bash
cd /home/mato/Dev/tf/genmap && pytest tests/ -v 2>&1 | tail -5
```
Expected: all 29 tests pass

- [ ] **Step 2: Start backend**

```bash
cd /home/mato/Dev/tf/genmap && python src/api.py &
sleep 2 && curl -s http://localhost:8000/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 3: Start frontend dev server**

```bash
cd /home/mato/Dev/tf/genmap/frontend && npm run dev &
sleep 2
```

- [ ] **Step 4: Open browser and verify**

Open `http://localhost:5173/?fixture=true`

Confirm all of the following:
- Light blue-gray body background (`#E8EDF2`) — no dark background
- Widget border is subtle gray, not gold
- Header text `◈ NEIGHBOURHOOD MAP` in dark navy, not gold
- POI panels are white with dark text
- 3D scene background is light (`#F0F4F8`), no fog
- Camera shows the scene from the south, north at top of screen (buildings lean away)
- Something moves — cars, cyclists, or pedestrians visible on the roads near center
- Transport pills are white with dark text

- [ ] **Step 5: Stop servers**

```bash
kill %1 %2 2>/dev/null; true
```

- [ ] **Step 6: Final commit**

```bash
cd /home/mato/Dev/tf/genmap
git commit --allow-empty -m "chore: visual refresh v2 integration verified"
```

---

## Spec Coverage

| Spec requirement | Task |
|---|---|
| Body bg `#E8EDF2` | Task 3 |
| Widget bg `#F5F7FA`, border `rgba(0,0,0,0.10)` | Task 3 |
| Scene bg `#F0F4F8` | Task 2 + Task 3 |
| Header title `#1E2D3D` (no gold) | Task 3 |
| Panel white, POI card `#F0F4F8`, dark text | Task 3 |
| Transport pill white, dark text | Task 3 |
| Outer POI pill white bg, dark text | Task 3 |
| Camera `(0, 380, 520)` FOV 42 looking north | Task 2 |
| Fog removed | Task 2 |
| Sun `(200, 500, 300)` | Task 2 |
| Widget 1340px, media query 1400px | Task 3 |
| Animations visible (road proximity fix) | Task 1 |
