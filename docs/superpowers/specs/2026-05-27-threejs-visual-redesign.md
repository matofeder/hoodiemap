# Three.js Visual Redesign

**Date:** 2026-05-27  
**Status:** Approved

## Goal

Redesign the Three.js frontend to match a compact isometric city infographic style — vivid colors, detailed buildings with window textures, lush lollipop trees, visible shadows, and working animations. Reference: freepik-style isometric city illustration (white/gray buildings, blue glass offices, dense green trees, vivid lime-green background).

## Current Problems

- Flat muted building colors (beige/gray tones)
- No window detail on building walls
- Camera too high/far — scene looks spread out
- Ambient light 1.0 kills all shadows → flat look
- Only 28 trees (OSM points only) → sparse
- Trees mix cones and spheres → inconsistent
- Oval dark vignette frame — remove completely
- Animations exist in code but likely not visible due to WebGL browser issue

## Scope

All changes are in `frontend/src/`. No backend changes. Five layers:

1. Background, camera, lighting
2. Building color palette
3. Window textures on building walls
4. Trees — lollipop style + procedural density
5. Animation fixes + UI frame removal

---

## Layer 1: Background, Camera, Lighting

**File:** `frontend/src/scene.js`

### Background
```js
scene.background = new THREE.Color(0x7ec850);  // vivid lime green
```

### Ground plane
Change ground color from current neutral to light concrete:
```js
// _addGround: MeshStandardMaterial color
new THREE.Color(0xd8d4cc)  // light gray concrete
```

### Camera
```js
camera.position.set(0, 220, 340);  // was: (0, 380, 560)
camera.lookAt(0, 0, 0);
controls.maxDistance = 700;  // was: 1200
controls.minDistance = 80;
```

### Lighting
```js
const ambient = new THREE.AmbientLight(0xffffff, 0.45);  // was: 1.0
const sun = new THREE.DirectionalLight(0xfff5e0, 1.6);   // slightly brighter
sun.position.set(200, 400, 150);  // was: (300, 500, 200) — more side-angle for longer shadows
sun.shadow.mapSize.set(2048, 2048);  // was: 1024 — sharper shadows
```

---

## Layer 2: Building Color Palette

**File:** `frontend/src/colors.js`

Replace `BUILDING_COLORS` with lighter, cleaner tones:

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

**Roof color:** In `_buildRoof` and `_addFlatRoofCap`, compute roof color as wall color multiplied by `0.82` (darker). Replace all hardcoded `multiplyScalar(...)` values (`0.75`, `0.80`, `0.7`) with `0.82` throughout both functions.

**Material:** Change `MeshLambertMaterial` → `MeshStandardMaterial` for building walls and roofs. Adds subtle specular that gives depth. Set `roughness: 0.85, metalness: 0.05`.

---

## Layer 3: Window Textures on Building Walls

**File:** `frontend/src/scene.js` — new helper `_makeWindowTexture(seed)`

### Texture generation
```js
function _makeWindowTexture(seed) {
  const W = 64, H = 128;
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#3a4050';  // wall base color
  ctx.fillRect(0, 0, W, H);

  const cols = 4, rows = 8;
  const ww = 10, wh = 10, gx = 6, gy = 6;
  // pseudo-random from seed
  let s = seed;
  const rand = () => { s = (s * 1664525 + 1013904223) & 0xffffffff; return (s >>> 0) / 0xffffffff; };

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const lit = rand() > 0.35;
      ctx.fillStyle = lit ? '#fffbe8' : '#222830';
      const x = gx + c * (ww + gx);
      const y = gy + r * (wh + gy);
      ctx.fillRect(x, y, ww, wh);
    }
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  return tex;
}
```

### Application
In `_addBuildings`, create one window texture per building (using building index as seed) and apply to the wall material:

```js
buildings.forEach((b, i) => {
  const wallTex = _makeWindowTexture(i * 7919);
  const wallMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(colorHex),
    map: wallTex,
    roughness: 0.85,
    metalness: 0.05,
  });
  // use wallMat for ExtrudeGeometry walls
  // use separate roofMat (no texture) for roof cap
});
```

Window texture is only applied to buildings taller than 6m (shorter structures like garages/kiosks get plain material).

---

## Layer 4: Trees — Lollipop Style + Procedural Density

**File:** `frontend/src/animations.js` — replace `_addTrees`

### New tree geometry
All trees use sphere canopy only (no cones):

```js
function _makeTree(scene, x, z, index) {
  const h = 5 + (index % 4);           // trunk height 5–8m
  const r = 5 + (index % 5) * 0.8;     // canopy radius 5–9m
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

### Procedural trees
In addition to OSM `sceneData.trees`, generate trees in:

1. **Park geo layer:** for each park polygon, fill with trees at ~1 per 400m² using a grid + jitter pattern
2. **Street trees:** for each road of type `residential`, `tertiary`, or `unclassified`, place trees every ~18m offset ±3m perpendicular to road direction (sidewalk side)

Cap total procedural trees at 400 to avoid performance issues.

### Animation
Canopy sway amplitude: `0.04` (was `0.025`). Frequency unchanged (`0.8`).

---

## Layer 5: Animation Debug + UI Frame Removal

### Animation debug
**File:** `frontend/src/scene.js`

Before creating the scene, check WebGL availability and log a warning:
```js
if (!renderer.capabilities.isWebGL2) {
  console.warn('WebGL2 not available — animations may be slow');
}
```

Car and pedestrian sizes increased:
- Car body: `3.5 × 1.2 × 6.0` (was `2.2 × 0.8 × 4.4`)
- Pedestrian: height `2.2` (was `1.5`)
- Cyclist group scale: `1.4×`
- `NUM_CARS`: 12 (was 8)

### Oval frame removal
**File:** `frontend/src/frame.js` + `frontend/index.html`

Remove the dark vignette overlay from `canvas-container`. The outer POI indicators (needle pins) are kept but restyled: white background with category color accent instead of dark ring. No change to the indicator logic — only CSS/style.

**CSS change:** Remove `box-shadow` inset and `border-radius: 50%` on `#canvas-container` that creates the oval vignette effect.

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/scene.js` | Camera, lighting, background, window texture helper, MeshStandardMaterial |
| `frontend/src/colors.js` | New BUILDING_COLORS palette |
| `frontend/src/animations.js` | Lollipop trees, bigger cars/pedestrians, procedural tree placement |
| `frontend/index.html` or CSS | Remove oval vignette |
| `frontend/src/frame.js` | Restyle outer POI pins |

No changes to `geometry.js`, `poi.js`, `route.js`, `main.js`, `ui.js`, or any backend files.

---

## Success Criteria

1. Background is vivid lime green, buildings white/gray/blue-glass
2. Building shadows clearly visible on ground
3. Buildings show window grid texture on walls
4. Scene is ~40% more compact/closer than current
5. Trees are round lollipop style, ~150+ visible in parks and along streets
6. Cars and cyclists visibly moving
7. No dark oval frame — full-screen 3D scene
8. All existing tests still pass (no JS logic changed)
