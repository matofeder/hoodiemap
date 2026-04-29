# Sub-project A: Two-Zone Infographic Layout + Outer POI Panel

**Date:** 2026-04-29
**Status:** Approved

## Overview

Transform the current full-area 3D map into a premium real estate infographic with two distinct zones:

1. **Inner zone** — detailed 3D map of the immediate neighbourhood (450 m radius), with circular clip and fade-out vignette
2. **Outer zone** — HTML frame surrounding the 3D canvas, showing distant POIs as compass-style indicators with interactive route hints

Target audience: real estate agencies who want a modern, editorial-quality neighbourhood infographic for listings.

---

## 1. Layout & Visual Structure

The page has two layers:

```
┌─────────────────────────────────────────┐
│          [outer POI indicators]         │  ← HTML frame (#infographic-frame)
│    ┌───────────────────────────┐        │
│    │                           │        │
│    │      3D Three.js          │        │
│    │       inner scene         │        │
│    │      (450 m circle)       │        │
│    └───────────────────────────┘        │
│                                         │
└─────────────────────────────────────────┘
```

- `#infographic-frame` — `position: relative`, dark/neutral background, contains everything
- `#threejs-mount` — `position: absolute; inset: 0`, the Three.js canvas
- Outer POI indicators — `position: absolute` elements placed around the frame perimeter by bearing

**Camera:** default angle raised to ~60° polar for better overview. OrbitControls remain active. Outer POI indicators are fixed in the HTML frame — they do **not** move when the camera orbits. This ensures labels are always readable regardless of camera orientation.

---

## 2. Inner Area, Vignette & Radius

**Circular clip + fade** via CSS on `#threejs-mount`:
```css
border-radius: 50%;
mask-image: radial-gradient(circle, black 60%, transparent 100%);
-webkit-mask-image: radial-gradient(circle, black 60%, transparent 100%);
```
The outer 40% of the circle area fades to transparent — buildings and roads dissolve toward the edge. No shader required.

**Display radius:** 450 m (configurable via `display_meters` in `config.yaml`). The backend returns `display_radius_m` in the scene JSON so the frontend can use it for camera framing and needle placement.

**POI threshold:** Any POI with `distance_m > display_radius_m` is classified as outer. Uses `cfg.radii.display_meters` directly — no new config field needed.

---

## 3. Backend Changes

### `scene_builder.py`

`build_scene()` output gains a new field:

```json
{
  "display_radius_m": 450,
  "pois": [
    { "name": "Café Antik", "category": "bar", "distance_m": 23, "x": -12.4, "y": 8.1, ... }
  ],
  "outer_pois": [
    {
      "name": "Nemocnica Pezinok",
      "category": "hospital",
      "distance_m": 2100,
      "bearing_deg": 335.5,
      "lat": 48.301,
      "lon": 17.268
    }
  ]
}
```

- `outer_pois` have no `x`/`y` — they have no position in the 3D scene, only direction and distance
- `lat`/`lon` are included so the frontend can call `/api/route` for the route hint
- Classification: `distance_m > cfg.radii.display_meters` → outer

### `config.py`

No new fields required. `display_meters` serves as the outer threshold.

### New endpoint: `GET /api/route`

```
/api/route?from_lat=…&from_lon=…&to_lat=…&to_lon=…
```

Proxies to `https://router.project-osrm.org/route/v1/driving/{from_lon},{from_lat};{to_lon},{to_lat}?overview=full&geometries=geojson`.

Returns the OSRM JSON response as-is. The frontend extracts the GeoJSON polyline and takes the first ~450 m of it.

**Cache:** responses cached in `cfg.cache.dir` by a hash of the coordinate pair (rounded to 5 decimal places) to avoid hammering OSRM.

---

## 4. Outer POI Frame Indicators

### Positioning

Each outer POI is placed at a point on the frame perimeter calculated from its bearing:

```js
const x = cx + rx * Math.sin(bearing_rad);
const y = cy - ry * Math.cos(bearing_rad);
```

Where `cx`, `cy` are the frame center and `rx`, `ry` are half the frame width/height. The indicator element is centered on this point via `transform: translate(-50%, -50%)`.

### Visual design

```
╭──────────────────────╮
│ ●  Nemocnica         │
│    2.1 km  ↖ SZ      │
╰──────────────────────╯
```

- Coloured dot (category colour from `POI_COLORS`)
- Name (truncated to 20 chars if needed)
- Distance formatted: `< 1 km` → `"850 m"`, `≥ 1 km` → `"2.1 km"`
- Cardinal direction: 8-point (S, SV, V, JV, J, JZ, Z, SZ)
- Style: dark pill, white text, subtle border matching category colour, hover highlight

### 3D needle in scene

A small `ConeGeometry` (height 15 m, radius 3 m) placed at `r = 430 m` from center, rotated to point outward along the POI bearing. Same colour as the POI category. On hover of the HTML label, the needle's `emissiveIntensity` increases to highlight it.

### Collision handling

If two outer POIs have bearings within 15° of each other, the later one (by priority order) is offset ±20 px along the perimeter. Maximum 8 outer POIs displayed; priority order:

`hospital > school > pharmacy > grocery > public_office > restaurant > pub > bar`

---

## 5. Route Hint (Hover / Click Interaction)

### Trigger

On `mouseenter` or `click` of an outer POI indicator.

### Info card

A CSS-styled `div` (absolute positioned near the 3D needle) appears with:
```
╭─────────────────────────╮
│  Nemocnica Pezinok      │
│  Nemocnica · 2.1 km     │
│  Smer: severozápad      │
╰─────────────────────────╯
```

### Route tube

1. Frontend calls `GET /api/route?from_lat=…&from_lon=…&to_lat=…&to_lon=…`
2. From the returned GeoJSON polyline, takes coordinates corresponding to the first ~450 m of the route
3. Converts each lat/lon to local UTM coordinates (same projection used for the rest of the scene)
4. Renders as `TubeGeometry` — width ~2 m, category colour, opacity 0.8

**Lifecycle:** tube is created on hover/click, removed when hover ends or user clicks elsewhere. Only one tube active at a time.

**Fallback:** if OSRM fails (timeout or unavailable), a dashed straight line from center to the needle is shown instead. No error is surfaced to the user.

---

## 6. New Frontend Files

| File | Role |
|------|------|
| `frontend/src/frame.js` | Outer POI frame: create indicators, handle positioning, collision resolution |
| `frontend/src/route.js` | Fetch route from `/api/route`, convert to local coords, render/dispose TubeGeometry |

### Modified files

| File | Change |
|------|--------|
| `scene.js` | Add 3D needles for outer POIs; adjust default camera angle to 60° |
| `main.js` | Pass `sceneData.outer_pois` to `initFrame()` after scene creation |
| `index.html` | Wrap `#threejs-mount` in `#infographic-frame` |
| `index.css` / styles | Circular clip mask on mount; frame background; indicator pill styles |
| `scene_builder.py` | Classify outer POIs, include `bearing_deg` + `lat`/`lon` |
| `api.py` | Add `/api/route` proxy endpoint with cache |

---

## 7. Out of Scope (Deferred)

- **Full routing UI** (turn-by-turn, full route line beyond 450 m) → Sub-project D
- **Satellite/aerial imagery** → Sub-project C (under consideration)
- **Visual style upgrade** (pedestrian zones, people near shops, etc.) → Sub-project B (next)
