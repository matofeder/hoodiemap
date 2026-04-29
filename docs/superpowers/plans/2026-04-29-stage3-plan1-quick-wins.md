# Stage 3 — Quick Wins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the orange-block artifact, remove fog, widen roads, expand display radius to 1000m, make the layout full-width, and add a modern loading spinner.

**Architecture:** All changes are frontend-only except `config.yaml`. Each task touches one or two files in isolation. No new abstractions — only targeted edits to existing code.

**Tech Stack:** Three.js 0.168, Vite 5, CSS. Dev server: `http://localhost:5173`. Tests: `cd frontend && npm test` (Vitest).

---

### Task 1: Fix commercial attic artifact + remove fog

**Files:**
- Modify: `frontend/src/scene.js`

The `_buildRoof` function has a `COMMERCIAL_TYPES` branch that adds a `BoxGeometry` attic strip — this creates the orange floating-box artifact. Remove it; the flat roof cap is sufficient.

Also remove the fog line from `createScene`.

- [ ] **Step 1: Remove fog line**

In `frontend/src/scene.js`, find line 30:
```js
scene.fog = new THREE.Fog(0xc9e8f4, 600, 1200);
```
Delete this line entirely.

- [ ] **Step 2: Remove commercial attic strip**

In `frontend/src/scene.js`, find the `COMMERCIAL_TYPES` branch in `_buildRoof` (~line 309). Replace:
```js
  } else if (COMMERCIAL_TYPES.has(type)) {
    _addFlatRoofCap(group, footprint, height, baseColorHex);
    const atticGeo = new THREE.BoxGeometry(w + 1.0, 0.8, d + 1.0);
    const atticColor = new THREE.Color(baseColorHex).multiplyScalar(0.85);
    const atticMat = new THREE.MeshLambertMaterial({ color: atticColor });
    const attic = new THREE.Mesh(atticGeo, atticMat);
    attic.position.set(cx, height + 0.4, -cy);
    group.add(attic);
```
With:
```js
  } else if (COMMERCIAL_TYPES.has(type)) {
    _addFlatRoofCap(group, footprint, height, baseColorHex);
```

- [ ] **Step 3: Run existing tests to confirm nothing broke**

```bash
cd frontend && npm test
```
Expected: all tests pass (same count as before).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/scene.js
git commit -m "fix: remove commercial attic strip (orange block artifact) and fog"
```

---

### Task 2: Road widths ×1.4

**Files:**
- Modify: `frontend/src/colors.js`

- [ ] **Step 1: Update ROAD_COLORS widths**

In `frontend/src/colors.js`, replace the entire `ROAD_COLORS` export and `ROAD_COLOR_DEFAULT`:

```js
export const ROAD_COLORS = {
  motorway:    { fill: '#ffffff', width: 7 },
  trunk:       { fill: '#ffffff', width: 7 },
  primary:     { fill: '#f0f0f0', width: 5.6 },
  secondary:   { fill: '#e8e8e8', width: 4.2 },
  tertiary:    { fill: '#e0e0e0', width: 3.5 },
  residential: { fill: '#d8d8d8', width: 2.8 },
  unclassified:{ fill: '#d0d0d0', width: 2.1 },
  service:     { fill: '#cccccc', width: 1.4 },
};
export const ROAD_COLOR_DEFAULT = { fill: '#cccccc', width: 2.1 };
```

- [ ] **Step 2: Run tests**

```bash
cd frontend && npm test
```
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/colors.js
git commit -m "feat: road widths x1.4 for better visibility"
```

---

### Task 3: Display radius 600 → 1000m + camera adjustment

**Files:**
- Modify: `config.yaml`
- Modify: `frontend/src/scene.js`

- [ ] **Step 1: Update config.yaml**

In `config.yaml`, change `display_meters`:
```yaml
radii:
  fetch_meters: 3000
  display_meters: 1000
```

- [ ] **Step 2: Clear OSM cache**

The geo layer cache key includes bbox coordinates, which change with the new radius. Delete the old cache so the server fetches fresh data:
```bash
rm -rf .cache/
```

- [ ] **Step 3: Update camera position and max distance**

In `frontend/src/scene.js`, find `createScene`. Replace:
```js
  camera.position.set(0, 300, 350);
```
With:
```js
  camera.position.set(0, 450, 550);
```

And replace:
```js
  controls.maxDistance = 800;
```
With:
```js
  controls.maxDistance = 1200;
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test
```
Expected: all tests pass (camera values are not tested; Python tests use a fixture with display_meters=600 and are unaffected).

- [ ] **Step 5: Commit**

```bash
git add config.yaml frontend/src/scene.js
git commit -m "feat: expand display radius to 1000m, adjust camera for wider view"
```

---

### Task 4: Responsive full-width layout

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: Update #app CSS**

In `frontend/index.html`, find the `#app` style block:
```css
    #app {
      display: flex;
      flex-direction: column;
      max-width: 960px;
      height: 100vh;
      margin: 0 auto;
      background: #fff;
      box-shadow: 0 0 40px rgba(0,0,0,0.15);
    }
```
Replace with:
```css
    #app {
      display: flex;
      flex-direction: column;
      width: 100%;
      height: 100vh;
      background: #fff;
    }
```

- [ ] **Step 2: Run tests**

```bash
cd frontend && npm test
```
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "feat: full-width responsive layout — remove 960px cap"
```

---

### Task 5: Modern loading spinner

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/src/main.js`

Currently `#loading` contains just a text node. We need to add inner elements and update `main.js` to target `#loading-text` instead of the container.

- [ ] **Step 1: Update loading CSS in index.html**

Find the `#loading` CSS block:
```css
    #loading {
      position: absolute; inset: 0; background: #e8eef4;
      display: flex; align-items: center; justify-content: center;
      color: #c0392b; font-size: 16px; z-index: 200;
    }
```
Replace with:
```css
    @keyframes spin { to { transform: rotate(360deg); } }
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
      color: #c0392b; font-size: 14px; font-weight: 500; letter-spacing: 0.02em;
    }
```

- [ ] **Step 2: Update loading HTML in index.html**

Find:
```html
      <div id="loading">Načítavam mapu…</div>
```
Replace with:
```html
      <div id="loading">
        <div id="loading-spinner"></div>
        <div id="loading-text">Načítavam…</div>
      </div>
```

- [ ] **Step 3: Update main.js to use #loading-text**

In `frontend/src/main.js`, there are three places that set `.textContent` on `#loading`. Update each:

Line 29 — embed/view error message:
```js
      document.getElementById('loading').textContent = 'Chýbajú koordináty (lat/lon).';
```
→
```js
      document.getElementById('loading-text').textContent = 'Chýbajú koordináty (lat/lon).';
```

Line 46 — demo mode loading text:
```js
      document.getElementById('loading').textContent = 'Načítavam mapu…';
```
→
```js
      document.getElementById('loading-text').textContent = 'Načítavam mapu…';
```

Line 83 — error handler:
```js
    document.getElementById('loading').textContent = `Chyba: ${err.message}`;
```
→
```js
      document.getElementById('loading-text').textContent = `Chyba: ${err.message}`;
      document.getElementById('loading-spinner').style.display = 'none';
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/src/main.js
git commit -m "feat: modern CSS spinner for loading screen"
```
