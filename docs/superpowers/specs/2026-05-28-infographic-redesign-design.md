# genmap — Infographic Redesign

**Date:** 2026-05-28
**Status:** Approved
**Goal:** Transform the current full-screen interactive 3D map into a fixed-canvas animated infographic. The Three.js city is the visual centrepiece, flanked by real-data POI panels, edge directional indicators for distant POIs, and a transport strip. No camera controls, no search bar — embed as iframe or open directly.

---

## Visual Style

**Dark premium.** Background `#0d1b2a`, gold (`#e8c547`) title accent, POI panel cards with thin color-coded left borders (category color from `styles.py`). Buildings retain full color. Soft edge fog on the 3D canvas to blend into the frame. No neon, no pixel art — moody and professional.

Reference aesthetic: the structural infographic layout (map + surrounding panels) of the city infographic poster style, rendered in the existing dark palette.

---

## Canvas Layout

Fixed 1200 × 760 px logical canvas, scales down via CSS transform on smaller viewports.

```
┌──────────────────────────────────────────────────────────────┐
│  ◈ NEIGHBOURHOOD MAP                    [Address / coords]   │
├─────────────┬──────────────────────────────┬─────────────────┤
│ Left panel  │                              │ Right panel     │
│             │    Three.js 3D scene         │                 │
│  3 POI      │    fixed isometric camera    │  3 POI cards    │
│  cards      │    animations running        │                 │
│             │    [edge indicators on rim]  │                 │
├─────────────┴──────────────────────────────┴─────────────────┤
│                 Transport / infrastructure strip             │
└──────────────────────────────────────────────────────────────┘
```

Column widths: left panel 200px · 3D canvas 800px · right panel 200px.
Header height: 44px. Transport strip height: 40px. 3D canvas height: 676px.

---

## POI Panel Cards

Left panel: 3 nearest POIs by `distance_m`.
Right panel: next 3 POIs by `distance_m`.

Each card contains:
- Thin (3px) left border in category color
- Category emoji + POI name (truncated to 1 line)
- Distance + cardinal direction: `320m · SW`
- Horizontal distance bar: fill = `distance_m / display_meters`, capped at 100%

Category color map (from `styles.py`):

| Category | Color |
|---|---|
| hospital | `#E05252` |
| grocery | `#4CAF7D` |
| school | `#4A90D9` |
| pharmacy | `#3AAFA9` |
| pub | `#7B5EA7` |
| bar | `#9B72CF` |
| restaurant | `#E8A838` |
| public_office | `#7F8C8D` |

Cards are omitted if the category has no result. Panels may have fewer than 3 cards.

Cardinal direction is computed from `bearing` (already available via `geo.py`): 0–22.5° and 337.5–360° → N, 22.5–67.5° → NE, etc.

---

## Edge Indicators (Distant POI Arrows)

For POIs with `distance_m > display_meters` (outer POIs — beyond the visible map area):

- Small pill rendered on the rim of the 3D canvas at the compass bearing toward the POI
- Content: `{emoji} {name} {distance}km →` (or ← / ↑ / ↓ based on side)
- Background: category color at 85% opacity, white text
- Positioned using: `left/top` offset derived from bearing angle placed on the canvas border ellipse

Up to 4 edge indicators rendered (one per cardinal quadrant, nearest POI wins per quadrant).

This extends the existing `frame.js` outer POI indicator system.

---

## Transport / Infrastructure Strip

Single-row pill strip at the bottom. Each pill: `{emoji} {label} · {distance}m {direction}`.

OSM sources queried (added to `fetcher.py` or as a new `fetch_transport` function):

| Pill | OSM tag |
|---|---|
| 🚌 Bus stop | `highway=bus_stop` |
| 🚲 Bike stand | `amenity=bicycle_parking` |
| 🅿 Parking | `amenity=parking` |
| 🚉 Train | `railway=station` or `railway=halt` |

If a type has no result within `fetch_meters`, that pill is omitted. Strip shows a maximum of 5 pills.

---

## 3D Scene

### Camera
Fixed `PerspectiveCamera`, FOV 45. Position: `(−280, 320, 280)`, looking at `(0, 0, 0)`. No `OrbitControls`. No user interaction with the canvas.

### Fog
`THREE.Fog` with near = 500, far = 900. Creates a soft circular fade at the canvas edges that blends into the dark frame.

### Animations

| Element | Behaviour |
|---|---|
| Trees | Sine sway on canopy — unchanged |
| Cars (4) | CatmullRomCurve3 road spline loop — unchanged |
| Pedestrians (5) | Sidewalk-offset curve loop — unchanged |
| **Bicycles (3)** | **New.** Road-edge offset (1m from kerb, opposite side to pedestrians). CapsuleGeometry body + two wheel rings. Speed ~2× pedestrian. Slight forward lean (rotation.x −0.15 rad). |
| Center pin | Pulse scale sine — unchanged |

### What is removed from the scene module
- `OrbitControls` import and instantiation
- Resize handler (canvas is fixed size)
- `CSS2DRenderer` and floating POI labels
- Click raycaster / popup logic

---

## Frontend Module Changes

### New: `frontend/src/infographic.js`

```
initInfographic(container, sceneData)
  → renders header, left panel, right panel, transport strip
  → returns { updateEdgeIndicators(outerPois) }
```

Pure DOM/CSS — no Three.js dependency. Takes `sceneData` (SceneJSON) and builds the surrounding frame.

### Modified: `frontend/src/scene.js`
- Remove `OrbitControls`, fixed camera position
- Remove `CSS2DRenderer`
- Remove resize handler
- Return canvas element (800 × 676 px) for embedding in infographic layout

### Modified: `frontend/src/animations.js`
- Add `_addBicycles(scene, roads)` — returns array of tick functions
- Called from `addAnimations()` alongside existing cars/pedestrians

### Modified: `frontend/src/main.js`
- Remove mode detection (embed/view/demo)
- Remove `initDemoUI` call
- Simplified boot: `fetchScene(lat, lon)` → `initInfographic(root, sceneData)` → `createScene(canvasContainer, sceneData)`
- `lat`/`lon` read from URL params (`?lat=&lon=`) with fallback to config defaults

### Modified: `frontend/index.html`
- Remove search bar, info card, embed modal, loading spinner text
- Single full-page dark container for the infographic canvas

### Removed: `frontend/src/ui.js`
No longer needed — search UI is gone.

### Removed: `frontend/src/route.js`
OSRM route hints not needed in infographic mode.

---

## Backend Changes

### `src/fetcher.py`
Add `fetch_transport(cfg, display_bbox)` function:
- Queries Overpass for bus stops, bike parking, car parking, train stations within `fetch_meters`
- Returns list of dicts: `[{category, name, lat, lon}]`
- Uses same pickle cache system as other fetch functions

### `src/scene_builder.py`
Add `transport` key to SceneJSON output:
```json
"transport": [
  {"category": "bus_stop", "name": "Centrum", "x": 45.0, "y": -80.0,
   "distance_m": 78, "bearing": 12.3}
]
```
Computed exactly like POIs — UTM projected, distance + bearing from center.

### `src/api.py`
No changes needed — `/api/scene` endpoint returns the enriched SceneJSON including `transport`.

---

## SceneJSON Contract (updated)

```json
{
  "center": { "lat": 48.286, "lon": 17.272 },
  "bbox_m": 600,
  "address": "Centrum, Pezinok",
  "roads":     [...],
  "buildings": [...],
  "pois":      [...],
  "trees":     [...],
  "transport": [
    { "category": "bus_stop", "name": "Centrum",
      "x": 45.0, "y": -80.0, "distance_m": 78, "bearing": 12.3 }
  ]
}
```

`address` field: added to `scene_builder.py` — reverse-geocoded from lat/lon via Nominatim (same `httpx` client already used in `api.py`), cached with scene data.

---

## What Is Not Changed

- `fetcher.py` existing functions (`fetch_street_network`, `fetch_geo_layers`, `fetch_pois`, `fetch_trees`)
- `geo.py`, `config.py`, `styles.py`
- `scene_builder.py` existing keys (`roads`, `buildings`, `pois`, `trees`)
- `/api/scene`, `/api/geocode`, `/health` endpoints
- OSM cache system
- `colors.js` — already has all needed color tables
- `poi.js` — repurposed: remove CSS2D labels, keep sphere markers for visual depth in scene (no click handler)
- Docker / deployment setup

---

## Out of Scope

- User camera control or pan/zoom
- Search bar or address input
- Embed / share / demo modes
- Day/night cycle
- PDF/PNG export (Stage 4)
- Mobile-specific layout (infographic scales down via CSS transform)
- Billing, accounts, white-label
