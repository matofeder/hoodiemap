# genmap — Visual Refresh v2

**Date:** 2026-05-28
**Status:** Approved
**Goal:** Replace the dark premium theme with a clean light blue-gray style, fix the north camera orientation, debug and fix animations (nothing currently moves), and widen the widget slightly.

---

## What Changes

### 1. Color Palette — Light Blue-Gray

| Element | Old | New |
|---|---|---|
| Body background | `#060d14` | `#E8EDF2` |
| Widget background | `#0d1b2a` | `#F5F7FA` |
| Three.js scene bg | `#0d1b2a` | `#F0F4F8` |
| Header title | `#e8c547` (gold) | `#1E2D3D` |
| Header address | `rgba(255,255,255,0.45)` | `#6B7A8D` |
| Panel background | `rgba(0,0,0,0.15)` | `#FFFFFF` |
| POI card background | `rgba(255,255,255,0.04)` | `#F0F4F8` |
| POI primary text | `#ffffff` | `#1E2D3D` |
| POI meta text | `rgba(255,255,255,0.4)` | `#6B7A8D` |
| Bar track | `rgba(255,255,255,0.08)` | `rgba(0,0,0,0.08)` |
| Transport strip bg | `rgba(0,0,0,0.1)` | `#F8FAFC` |
| Transport pill | `rgba(255,255,255,0.05)` bg | `#FFFFFF` bg, `rgba(0,0,0,0.12)` border |
| Transport pill text | `rgba(255,255,255,0.55)` | `#4A5568` |
| Widget border | `rgba(232,197,71,0.2)` | `rgba(0,0,0,0.10)` |
| Widget shadow | dark | `0 8px 40px rgba(0,0,0,0.12)` |
| Panel dividers | `rgba(255,255,255,0.06)` | `rgba(0,0,0,0.07)` |
| Header border-bottom | `rgba(232,197,71,0.15)` | `rgba(0,0,0,0.08)` |

POI category colors (left borders and bar fills) are **unchanged** — they provide the color accent against the neutral background.

---

### 2. Camera — South Oblique, North at Top

**Current:** `camera.position.set(-280, 320, 280)` — northwest angle, looking south-east. North is bottom-left on screen.

**New:**
```js
const camera = new THREE.PerspectiveCamera(42, W / H, 0.1, 2000);
camera.position.set(0, 380, 520);
camera.lookAt(0, 0, 0);
```

Camera sits due south, elevated. Looking north. North = top of screen. Buildings lean away from the viewer — classic 3D city map orientation.

**Sun position** adjusted to `(200, 500, 300)` — light comes from south-east, illuminating the south-facing and east-facing walls visible from this angle.

**Fog removed entirely** (`scene.fog` line deleted).

---

### 3. Animations — Debug and Fix

**Symptom:** Nothing moves — no cars, cyclists, pedestrians, no tree sway.

**Investigation plan (during implementation):**
1. Add `console.log` after `addAnimations` and `addCyclists` calls to log how many animatables were created
2. Log the number of roads available for animation curves
3. Test with live data (`?lat=48.28646&lon=17.27221`) to isolate whether it's a fixture issue or a code bug
4. Check `addAnimations` return value — confirm it includes tree sway tick functions

**Expected fixes (one or more):**
- If fixture roads are too short/missing: re-capture fixture after all other changes land
- If `addAnimations` silently returns `[]` due to road data format: fix the road filtering/curve-building logic
- If tree sway ticks are missing from `addAnimations` return: add them

**No new animation features** — existing cars/cyclists/pedestrians/trees are enough if they actually run.

---

### 4. Widget Size

| Dimension | Old | New |
|---|---|---|
| Widget total width | 1200px | 1340px |
| 3D canvas width | ~800px (flex: 1) | ~940px (flex: 1, auto-expands) |
| POI panels | 200px each | 200px each (unchanged) |
| Total height | 760px | 760px (unchanged) |
| Media query breakpoint | `max-width: 1260px` | `max-width: 1400px` |
| Scale at breakpoint | `scale(0.75)` | `scale(0.75)` (unchanged) |

`#app` and `.infographic-root` widths updated to `1340px`. Canvas slot uses `flex: 1` so it fills automatically.

---

## Files to Change

```
frontend/
  index.html           — update all CSS colors + widget/app widths + media query
  src/scene.js         — camera position, FOV, sun position, remove fog, scene background color
  src/animations.js    — debug and fix why animatables return empty (or tree sway missing)
```

**Not changed:** `infographic.js`, `poi.js`, `frame.js`, `colors.js`, `main.js`, all backend files.

---

## What Is Not Changed

- Layout structure (header / 3-column body / strip) — unchanged
- POI category colors — unchanged
- Transport strip content — unchanged
- Outer POI indicators — unchanged
- `scene.js` geometry/building/road rendering — unchanged
- All backend Python code — unchanged
- Widget height (760px) — unchanged
- Panel widths (200px) — unchanged
