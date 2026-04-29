# genmap Stage 2 — Visual Quality Iteration

**Date:** 2026-04-29  
**Scope:** Three.js frontend only (`frontend/src/`)  
**Approach:** B — Full visual iteration (daylight, lane roads, shrubs, typed buildings)

---

## 1. Scene & Lighting

**Goal:** Replace dark night scene with a bright daylight look.

| Property | Current | New |
|---|---|---|
| `scene.background` | `0x0d1b2a` (dark navy) | `0x87ceeb` (day sky blue) |
| `scene.fog` color | `0x0d1b2a` | `0xc9e8f4` (light air blue) |
| Fog near/far | 400 / 900 | 600 / 1200 |
| `AmbientLight` intensity | 0.6 | 1.0 |
| `DirectionalLight` intensity | 1.0 | 1.4 |
| Sun position | `(200, 300, 200)` | `(300, 500, 200)` |
| Ground color | `0x3a5a3a` (dark green) | `0x7ab648` (sunny grass green) |

**Files:** `scene.js` (`createScene`, `_addGround`)

---

## 2. Roads — Flat Planes + Lane Markings

**Goal:** Replace TubeGeometry tubes with flat planes; add visible lane markings.

### Road surface
- Replace `TubeGeometry` with a flat ribbon `BufferGeometry`: sample CatmullRomCurve3 at N points, build quads (2 triangles each) offset left/right by `width/2` along the perpendicular of each tangent
- Width per type preserved from `ROAD_COLORS` table
- Road surface at `y = 0.15`
- Add edge strips: same ribbon approach, width=0.3m, offset to each edge at `y = 0.16`, color `#ffffff`, opacity 0.5

### Center line markings
- Applied to: `primary`, `secondary`, `tertiary`
- Dashed yellow line: sample spline at fixed intervals, draw short `PlaneGeometry` segments at `y = 0.17`
- Dash length: 2m, gap: 3m

### Cars
- Lift car start position from `y=0.2` to `y=0.3` to sit above new flat road surface
- Increase car count: `NUM_CARS = 4 → 8`

**Files:** `scene.js` (`_addRoads`), `animations.js` (`_addCars`)

---

## 3. Vegetation — Shrubs + Better Trees

**Goal:** Green areas look richer; add low shrub clusters alongside parks and sidewalks.

### Trees (existing, improved)
- Keep swaying cone canopy from `animations.js`
- Change `ConeGeometry` to `SphereGeometry` for deciduous look (radius = `r * 0.8`, widthSegments=8)
- Keep cone for conifer variant (every 3rd tree)
- Trunk stays `CylinderGeometry`

### Shrubs (new)
- Add `_addShrubs(scene, sceneData)` in `animations.js`
- Source: scatter along park/forest polygon edges (passed from `sceneData.geo_layers`)
- Each shrub: cluster of 2–4 small `SphereGeometry` (`r = 0.8–1.4`) slightly offset, color from `[0x4a7a4a, 0x5a8c3a, 0x3d6e2e]`
- Place shrubs every ~8m along polygon boundary, slight random offset
- No animation (static), `receiveShadow = true`
- Cap at 200 shrubs per scene to limit GPU load

**Files:** `animations.js` (`_addTrees`, new `_addShrubs`), `scene.js` (call `_addShrubs`)

---

## 4. Buildings — Type-Distinctive Shapes

**Goal:** Building type readable at a glance from 3D shape, not just color.

### Tier system

| Type group | Types | Shape |
|---|---|---|
| **House** | `house`, `detached`, `bungalow` | ExtrudeGeometry body + pitched roof (ridge along long axis) |
| **Apartments** | `apartments`, `residential`, `terrace` | ExtrudeGeometry body + flat roof + window rows (LineSegments) |
| **Church** | `church`, `cathedral`, `chapel`, `monastery` | ExtrudeGeometry body + thin tall spire (`ConeGeometry`, r=0.8, h=15) at centroid |
| **Commercial** | `commercial`, `retail`, `supermarket`, `kiosk` | ExtrudeGeometry body + flat roof + attic strip (thin box, slightly wider than footprint) |
| **Office/Civic** | `office`, `civic`, `public`, `government` | ExtrudeGeometry body + flat roof + window column grid (LineSegments) |
| **Industrial** | `industrial`, `warehouse`, `factory` | ExtrudeGeometry body + sawtooth/shed roof (simple ridge) |
| **Default** | everything else | ExtrudeGeometry body + flat dark roof cap (current behavior) |

### Pitched roof (houses)
- Compute footprint bounding box, find long axis
- Two triangular `BufferGeometry` end-caps + two rectangular slope faces
- Ridge height = `footprint_width * 0.4`
- Color: `adjust_color(base, 0.75)` (darker than walls)

### Spire (churches)
- `ConeGeometry(0.8, 15, 4)` at footprint centroid, placed at top of building
- Color: `0x9e8ac0` (same purple as church)

### Window rows (apartments, offices)
- For each floor (step 2.5m from ground to top): draw a row of small `BoxGeometry` windows (0.8×0.6×0.1m) spaced every 1.8m along each cardinal wall of the footprint bounding box
- Color: `0xadd8e6` (light blue glass), `MeshBasicMaterial` so they glow regardless of lighting
- Only drawn if building height > 5m; cap at 60 windows per building

### Attic strip (commercial)
- Thin `BoxGeometry` (height=0.8m, slightly wider than footprint by 0.5m on each side)
- Placed at top of building
- Color: `adjust_color(base, 0.85)`

**Files:** `scene.js` (`_addBuildings`), new helper `_buildRoof(type, footprint, height)` in `scene.js`

---

## 5. Data contract (scene_builder.py → frontend)

No changes needed to the scene JSON schema. All additions are purely visual, computed from existing fields (`b.type`, `b.height`, `b.footprint`, geo_layers rings).

---

## Out of scope

- Full-screen layout (user explicitly declined)
- Texture maps / image-based materials
- Shadow-casting shrubs (performance)
- Animated pedestrians changes (keep as-is)

---

## Files changed

| File | Changes |
|---|---|
| `frontend/src/scene.js` | Lighting, ground, roads (flat), buildings (typed), call `_addShrubs` |
| `frontend/src/animations.js` | Trees (sphere canopy), new `_addShrubs`, cars lift + count |
| `frontend/src/colors.js` | No changes expected |
