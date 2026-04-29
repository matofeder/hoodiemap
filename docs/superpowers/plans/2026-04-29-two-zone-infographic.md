# Two-Zone Infographic Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the full-area 3D map into a premium infographic with an inner circular 3D scene (450 m, vignette fade) surrounded by an HTML frame showing distant POIs as interactive compass indicators with OSRM route hints.

**Architecture:** `scene_builder.py` classifies POIs as inner (within `display_meters`) or outer (beyond it), returning `outer_pois` with bearing/distance but no scene coordinates. The frontend renders the inner scene with a CSS vignette mask and positions HTML pill indicators around the frame perimeter; a new `/api/route` endpoint proxies OSRM so the frontend can draw a 3D route tube on hover.

**Tech Stack:** Python/FastAPI (backend), Three.js + Vitest (frontend), OSRM public API (routing)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/scene_builder.py` | Modify | Classify POIs as inner/outer, add `outer_pois` + `display_radius_m` to JSON |
| `src/api.py` | Modify | Add `/api/route` OSRM proxy with in-memory cache |
| `tests/test_scene_builder.py` | Modify | Tests for outer POI classification and `display_radius_m` |
| `tests/test_api.py` | Modify | Tests for `/api/route` endpoint |
| `frontend/index.html` | Modify | Add vignette CSS on `#threejs-mount`; dark background on `#canvas-container`; outer POI indicator styles |
| `frontend/src/frame.js` | Create | `initFrame()`, position calculation, collision resolution, hover handlers |
| `frontend/src/frame.test.js` | Create | Tests for `_formatDistance`, `_bearingToCardinal`, `_resolveCollisions` |
| `frontend/src/route.js` | Create | `showRouteHint()`, `hideRouteHint()`, `_latLonToLocal()` |
| `frontend/src/scene.js` | Modify | Camera raised to ~60°; `_addOuterNeedles()` for boundary 3D pins |
| `frontend/src/main.js` | Modify | Wire `initFrame()` and route hint after scene creation |

---

## Task 1: Backend — outer POI classification in `scene_builder.py`

**Files:**
- Modify: `src/scene_builder.py`
- Modify: `tests/test_scene_builder.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_scene_builder.py` (after the existing imports — add `from geo import POI`):

```python
from geo import POI


def _make_poi(lat, lon, name, category, distance_m):
    return POI(name=name, lat=lat, lon=lon, category=category, distance_m=distance_m, bearing_deg=0.0)


def _patches(cx, cy, pois):
    """Context manager factory returning the standard patch stack with custom pois."""
    from unittest.mock import patch, MagicMock
    return (
        patch("scene_builder.fetch_street_network", return_value=MagicMock()),
        patch("scene_builder.fetch_geo_layers", return_value={k: None for k in ["building", "water", "forest", "park", "railway", "residential"]}),
        patch("scene_builder.fetch_trees", return_value=[]),
        patch("scene_builder.fetch_pois", return_value=pois),
        patch("scene_builder.ox.project_graph", return_value=_make_mock_graph(cx, cy)),
    )


def test_scene_includes_display_radius_m(default_config):
    from scene_builder import build_scene
    lat, lon = 48.28646, 17.27221
    cx, cy = _get_utm_center(lat, lon)
    with patch("scene_builder.fetch_street_network") as m1, \
         patch("scene_builder.fetch_geo_layers") as m2, \
         patch("scene_builder.fetch_trees") as m3, \
         patch("scene_builder.fetch_pois") as m4, \
         patch("scene_builder.ox.project_graph") as m5:
        m1.return_value = MagicMock()
        m2.return_value = {k: None for k in ["building", "water", "forest", "park", "railway", "residential"]}
        m3.return_value = []
        m4.return_value = []
        m5.return_value = _make_mock_graph(cx, cy)
        result = build_scene(lat, lon, default_config)
    assert result["display_radius_m"] == 600  # default_config.radii.display_meters == 600


def test_outer_pois_classified_and_have_bearing(default_config):
    from scene_builder import build_scene
    lat, lon = 48.28646, 17.27221
    cx, cy = _get_utm_center(lat, lon)
    # 200 m → inner (< 600); 800 m → outer (> 600)
    near = _make_poi(lat, lon + 200 / 111320, "Kaviarnen", "bar", 200)
    far = _make_poi(lat + 800 / 111320, lon, "Nemocnica", "hospital", 800)
    with patch("scene_builder.fetch_street_network") as m1, \
         patch("scene_builder.fetch_geo_layers") as m2, \
         patch("scene_builder.fetch_trees") as m3, \
         patch("scene_builder.fetch_pois") as m4, \
         patch("scene_builder.ox.project_graph") as m5:
        m1.return_value = MagicMock()
        m2.return_value = {k: None for k in ["building", "water", "forest", "park", "railway", "residential"]}
        m3.return_value = []
        m4.return_value = [near, far]
        m5.return_value = _make_mock_graph(cx, cy)
        result = build_scene(lat, lon, default_config)
    assert len(result["pois"]) == 1
    assert result["pois"][0]["name"] == "Kaviarnen"
    assert len(result["outer_pois"]) == 1
    op = result["outer_pois"][0]
    assert op["name"] == "Nemocnica"
    assert "bearing_deg" in op
    assert "lat" in op and "lon" in op
    assert "x" not in op and "y" not in op


def test_outer_poi_north_has_bearing_near_zero(default_config):
    from scene_builder import build_scene
    lat, lon = 48.28646, 17.27221
    cx, cy = _get_utm_center(lat, lon)
    dlat = 800 / 111320
    north_poi = _make_poi(lat + dlat, lon, "Hospital", "hospital", 800)
    with patch("scene_builder.fetch_street_network") as m1, \
         patch("scene_builder.fetch_geo_layers") as m2, \
         patch("scene_builder.fetch_trees") as m3, \
         patch("scene_builder.fetch_pois") as m4, \
         patch("scene_builder.ox.project_graph") as m5:
        m1.return_value = MagicMock()
        m2.return_value = {k: None for k in ["building", "water", "forest", "park", "railway", "residential"]}
        m3.return_value = []
        m4.return_value = [north_poi]
        m5.return_value = _make_mock_graph(cx, cy)
        result = build_scene(lat, lon, default_config)
    bearing = result["outer_pois"][0]["bearing_deg"]
    assert bearing < 1.0 or bearing > 359.0  # ~0°
```

Also update the existing `test_build_scene_returns_required_keys` — replace the key-set assertion:

```python
# OLD:
assert set(result.keys()) == {"center", "bbox_m", "roads", "buildings", "pois", "trees", "geo_layers"}
# NEW:
assert set(result.keys()) == {"center", "bbox_m", "display_radius_m", "roads", "buildings", "pois", "outer_pois", "trees", "geo_layers"}
assert result["display_radius_m"] == 600
assert isinstance(result["outer_pois"], list)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/mato/Dev/tf/genmap
python -m pytest tests/test_scene_builder.py::test_scene_includes_display_radius_m tests/test_scene_builder.py::test_outer_pois_classified_and_have_bearing tests/test_scene_builder.py::test_outer_poi_north_has_bearing_near_zero -v
```

Expected: `FAILED` — `KeyError: 'display_radius_m'` or similar.

- [ ] **Step 3: Implement outer POI classification in `src/scene_builder.py`**

Change the import line at the top:
```python
# OLD:
from geo import compute_bbox
# NEW:
from geo import compute_bbox, compute_bearing
```

Replace the `pois = []` block (lines ~123–132) and the `return` statement (lines ~143–151):

```python
    threshold_m = cfg.radii.display_meters
    inner_pois = []
    outer_pois = []
    for poi in pois_raw:
        if poi.distance_m <= threshold_m:
            x, y = _latlon_to_local(poi.lat, poi.lon, cx, cy, utm_crs)
            inner_pois.append({
                "x": x, "y": y,
                "lat": poi.lat, "lon": poi.lon,
                "category": poi.category,
                "name": poi.name,
                "distance_m": round(poi.distance_m),
            })
        else:
            bearing = compute_bearing(lat, lon, poi.lat, poi.lon)
            outer_pois.append({
                "name": poi.name,
                "category": poi.category,
                "distance_m": round(poi.distance_m),
                "bearing_deg": round(bearing, 1),
                "lat": poi.lat,
                "lon": poi.lon,
            })

    # (keep trees block unchanged)
    ...

    return {
        "center": {"lat": lat, "lon": lon},
        "display_radius_m": cfg.radii.display_meters,
        "bbox_m": cfg.radii.display_meters,
        "roads": roads,
        "buildings": buildings,
        "pois": inner_pois,
        "outer_pois": outer_pois,
        "trees": trees,
        "geo_layers": geo_layers_out,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_scene_builder.py -v
```

Expected: all `PASSED`. The existing `test_build_scene_returns_required_keys` must also pass after the key-set update from Step 1.

- [ ] **Step 5: Commit**

```bash
git add src/scene_builder.py tests/test_scene_builder.py
git commit -m "feat: classify outer POIs with bearing in build_scene output"
```

---

## Task 2: Backend — `/api/route` OSRM proxy

**Files:**
- Modify: `src/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_api.py`:

```python
@pytest.mark.asyncio
async def test_route_endpoint_returns_osrm_response():
    from api import app
    from unittest.mock import AsyncMock, MagicMock
    mock_osrm = {
        "routes": [{
            "geometry": {"type": "LineString", "coordinates": [[17.272, 48.286], [17.273, 48.287]]},
            "distance": 1200,
        }]
    }
    with patch("api.httpx.AsyncClient") as mock_cls:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_osrm
        mock_resp.raise_for_status = MagicMock()
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/route?from_lat=48.286&from_lon=17.272&to_lat=48.290&to_lon=17.275"
            )
    assert response.status_code == 200
    assert "routes" in response.json()


@pytest.mark.asyncio
async def test_route_endpoint_osrm_failure_returns_502():
    from api import app
    import httpx as real_httpx
    with patch("api.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=real_httpx.RequestError("timeout"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/route?from_lat=48.286&from_lon=17.272&to_lat=48.290&to_lon=17.275"
            )
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_route_endpoint_cached_on_second_call():
    from api import app, _route_cache
    _route_cache.clear()
    mock_osrm = {"routes": [{"geometry": {"type": "LineString", "coordinates": []}, "distance": 500}]}
    call_count = 0
    with patch("api.httpx.AsyncClient") as mock_cls:
        async def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            m = MagicMock()
            m.json.return_value = mock_osrm
            m.raise_for_status = MagicMock()
            return m
        from unittest.mock import MagicMock
        mock_http = AsyncMock()
        mock_http.get = fake_get
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/api/route?from_lat=48.28600&from_lon=17.27200&to_lat=48.29000&to_lon=17.27500")
            await client.get("/api/route?from_lat=48.28600&from_lon=17.27200&to_lat=48.29000&to_lon=17.27500")
    assert call_count == 1  # second call served from cache
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_api.py::test_route_endpoint_returns_osrm_response tests/test_api.py::test_route_endpoint_osrm_failure_returns_502 -v
```

Expected: `FAILED` — `404 Not Found` (endpoint doesn't exist yet).

- [ ] **Step 3: Add `/api/route` endpoint to `src/api.py`**

After the `_share_store` declaration, add:

```python
_route_cache: dict[str, dict] = {}
```

After the `scene_share` endpoint, add:

```python
@app.get("/api/route")
async def route_hint(
    from_lat: Annotated[float, Query(ge=-90, le=90)],
    from_lon: Annotated[float, Query(ge=-180, le=180)],
    to_lat: Annotated[float, Query(ge=-90, le=90)],
    to_lon: Annotated[float, Query(ge=-180, le=180)],
):
    cache_key = f"{from_lat:.5f},{from_lon:.5f},{to_lat:.5f},{to_lon:.5f}"
    if cache_key in _route_cache:
        return _route_cache[cache_key]
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{from_lon:.6f},{from_lat:.6f};{to_lon:.6f},{to_lat:.6f}"
        f"?overview=full&geometries=geojson"
    )
    headers = {"User-Agent": "genmap/1.0 (neighbourhood-map)"}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise HTTPException(status_code=502, detail="Routing upstream error") from exc
    data = resp.json()
    _route_cache[cache_key] = data
    return data
```

- [ ] **Step 4: Run all API tests**

```bash
python -m pytest tests/test_api.py -v
```

Expected: all `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "feat: add /api/route OSRM proxy with in-memory cache"
```

---

## Task 3: Frontend HTML/CSS — frame structure and styles

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: Add vignette and dark frame CSS**

In `frontend/index.html`, find the `#canvas-container` CSS block and replace it:

```css
/* OLD: */
#canvas-container {
  flex: 1;
  min-height: 0;
  position: relative;
  overflow: hidden;
  background: #87ceeb;
}
/* NEW: */
#canvas-container {
  flex: 1;
  min-height: 0;
  position: relative;
  overflow: hidden;
  background: #111827;
}
```

Find `#threejs-mount { position: absolute; inset: 0; }` and replace:

```css
#threejs-mount {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  -webkit-mask-image: radial-gradient(circle, black 58%, transparent 100%);
  mask-image: radial-gradient(circle, black 58%, transparent 100%);
  overflow: hidden;
}
#threejs-mount canvas { display: block; width: 100% !important; height: 100% !important; }
```

- [ ] **Step 2: Add outer POI indicator styles**

Add these styles to the `<style>` block in `index.html` (after `.poi-popup` block):

```css
/* Outer POI indicators */
.outer-poi-indicator {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  cursor: pointer;
  z-index: 10;
  transition: transform 0.15s ease;
}
.outer-poi-indicator:hover { transform: translate(-50%, -50%) scale(1.1) !important; }
.outer-poi-indicator.active .outer-poi-pill { box-shadow: 0 0 0 2px #fff; }

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
.outer-poi-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 5px;
  flex-shrink: 0;
}
.outer-poi-header {
  display: flex;
  align-items: center;
  width: 100%;
}
.outer-poi-name {
  color: #f0f0f0;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 110px;
}
.outer-poi-meta {
  color: #9ca3af;
  font-size: 10px;
  white-space: nowrap;
  padding-left: 13px;
}

/* Info card for outer POI hover */
.outer-poi-info-card {
  position: absolute;
  background: rgba(15, 20, 35, 0.95);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 10px;
  padding: 10px 14px;
  min-width: 160px;
  color: #f0f0f0;
  font-size: 12px;
  pointer-events: none;
  z-index: 20;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
  display: none;
}
.outer-poi-info-card.visible { display: block; }
.outer-poi-info-card .opc-name { font-weight: bold; margin-bottom: 3px; font-size: 13px; }
.outer-poi-info-card .opc-meta { color: #9ca3af; font-size: 11px; line-height: 1.6; }
```

- [ ] **Step 3: Add info card container to HTML**

Inside `<div id="canvas-container">`, after `<div id="threejs-mount"></div>`, add:

```html
<div id="outer-poi-info-card" class="outer-poi-info-card">
  <div class="opc-name" id="opc-name"></div>
  <div class="opc-meta" id="opc-meta"></div>
</div>
```

- [ ] **Step 4: Verify visually in browser**

Open http://localhost:5173, search Pezinok. The 3D scene should now appear as a circle on a dark background. Inner scene looks the same, edge fades to transparent revealing dark `#111827` background. No outer POI indicators yet (those come in Task 4).

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add circular vignette and dark infographic frame to canvas"
```

---

## Task 4: Frontend — `frame.js` (outer POI indicators)

**Files:**
- Create: `frontend/src/frame.js`
- Create: `frontend/src/frame.test.js`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/frame.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { _formatDistance, _bearingToCardinal, _resolveCollisions } from './frame.js';

describe('_formatDistance', () => {
  it('returns meters for < 1000', () => {
    expect(_formatDistance(850)).toBe('850 m');
  });
  it('rounds meters', () => {
    expect(_formatDistance(423)).toBe('423 m');
  });
  it('returns km with 1 decimal for >= 1000', () => {
    expect(_formatDistance(2100)).toBe('2.1 km');
  });
  it('returns km for exactly 1000', () => {
    expect(_formatDistance(1000)).toBe('1.0 km');
  });
});

describe('_bearingToCardinal', () => {
  it('0° is S (Sever = North)', () => {
    expect(_bearingToCardinal(0)).toBe('S');
  });
  it('90° is V (Východ = East)', () => {
    expect(_bearingToCardinal(90)).toBe('V');
  });
  it('180° is J (Juh = South)', () => {
    expect(_bearingToCardinal(180)).toBe('J');
  });
  it('270° is Z (Západ = West)', () => {
    expect(_bearingToCardinal(270)).toBe('Z');
  });
  it('315° is SZ (Severozápad = NW)', () => {
    expect(_bearingToCardinal(315)).toBe('SZ');
  });
  it('360° wraps to S', () => {
    expect(_bearingToCardinal(360)).toBe('S');
  });
});

describe('_resolveCollisions', () => {
  it('leaves non-colliding POIs unchanged', () => {
    const pois = [
      { bearing_deg: 10 },
      { bearing_deg: 90 },
      { bearing_deg: 200 },
    ];
    const result = _resolveCollisions(pois);
    expect(result[0].bearing_deg).toBe(10);
    expect(result[1].bearing_deg).toBe(90);
    expect(result[2].bearing_deg).toBe(200);
  });

  it('separates two POIs closer than 15°', () => {
    const pois = [
      { bearing_deg: 45 },
      { bearing_deg: 50 },
    ];
    const result = _resolveCollisions(pois);
    const diff = Math.abs(result[1].bearing_deg - result[0].bearing_deg);
    expect(diff).toBeGreaterThanOrEqual(15);
  });

  it('does not mutate input objects', () => {
    const pois = [{ bearing_deg: 45 }, { bearing_deg: 50 }];
    _resolveCollisions(pois);
    expect(pois[0].bearing_deg).toBe(45);
    expect(pois[1].bearing_deg).toBe(50);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/mato/Dev/tf/genmap/frontend
npm test
```

Expected: `FAILED` — cannot import from `./frame.js` (file does not exist).

- [ ] **Step 3: Create `frontend/src/frame.js`**

```js
import { POI_COLORS } from './colors.js';

const PRIORITY = ['hospital', 'school', 'pharmacy', 'grocery', 'public_office', 'restaurant', 'pub', 'bar'];
const MAX_OUTER = 8;

/**
 * Renders outer POI indicators around the infographic frame.
 * Returns { highlight(poi), clear() }.
 */
export function initFrame(container, outerPois, centerLat, centerLon, onHover, onLeave) {
  const sorted = [...outerPois]
    .sort((a, b) => {
      const pa = PRIORITY.indexOf(a.category);
      const pb = PRIORITY.indexOf(b.category);
      return (pa === -1 ? 99 : pa) - (pb === -1 ? 99 : pb);
    })
    .slice(0, MAX_OUTER);

  const resolved = _resolveCollisions(sorted);

  const entries = resolved.map(poi => {
    const el = _createIndicator(poi);
    container.appendChild(el);
    _positionIndicator(el, poi.bearing_deg, container);
    el.addEventListener('mouseenter', () => onHover(poi, el));
    el.addEventListener('mouseleave', () => onLeave(poi, el));
    return { el, poi };
  });

  // Reposition on resize
  const observer = new ResizeObserver(() => {
    entries.forEach(({ el, poi }) => _positionIndicator(el, poi.bearing_deg, container));
  });
  observer.observe(container);

  return {
    highlight(activePoi) {
      entries.forEach(({ el, poi }) => el.classList.toggle('active', poi === activePoi));
    },
    clear() {
      observer.disconnect();
      entries.forEach(({ el }) => el.remove());
    },
  };
}

export function _resolveCollisions(pois) {
  const result = pois.map(p => ({ ...p }));
  const MIN_DIFF = 15;
  for (let i = 1; i < result.length; i++) {
    for (let j = 0; j < i; j++) {
      let diff = result[i].bearing_deg - result[j].bearing_deg;
      if (diff > 180) diff -= 360;
      if (diff < -180) diff += 360;
      if (Math.abs(diff) < MIN_DIFF) {
        result[i].bearing_deg += Math.sign(diff || 1) * (MIN_DIFF - Math.abs(diff) + 2);
      }
    }
  }
  return result;
}

export function _formatDistance(meters) {
  if (meters < 1000) return `${Math.round(meters)} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}

export function _bearingToCardinal(deg) {
  const dirs = ['S', 'SV', 'V', 'JV', 'J', 'JZ', 'Z', 'SZ'];
  return dirs[Math.round(((deg % 360) + 360) % 360 / 45) % 8];
}

function _createIndicator(poi) {
  const color = POI_COLORS[poi.category] || '#888888';
  const el = document.createElement('div');
  el.className = 'outer-poi-indicator';
  el.dataset.category = poi.category;
  el.innerHTML = `
    <div class="outer-poi-pill">
      <div class="outer-poi-header">
        <span class="outer-poi-dot" style="background:${color}"></span>
        <span class="outer-poi-name">${poi.name.slice(0, 22)}</span>
      </div>
      <span class="outer-poi-meta">${_formatDistance(poi.distance_m)} · ${_bearingToCardinal(poi.bearing_deg)}</span>
    </div>
  `;
  return el;
}

function _positionIndicator(el, bearingDeg, container) {
  const W = container.clientWidth;
  const H = container.clientHeight;
  if (!W || !H) return;
  const rad = (bearingDeg * Math.PI) / 180;
  // Elliptical placement at 90% of each half-axis so indicators stay inside container
  const rx = W / 2 * 0.90;
  const ry = H / 2 * 0.90;
  const x = W / 2 + rx * Math.sin(rad);
  const y = H / 2 - ry * Math.cos(rad);
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
  el.style.transform = 'translate(-50%, -50%)';
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/mato/Dev/tf/genmap/frontend
npm test
```

Expected: all frame tests `PASSED`. Existing tests also `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/frame.js frontend/src/frame.test.js
git commit -m "feat: add frame.js outer POI indicator rendering"
```

---

## Task 5: Frontend — `scene.js` camera + outer POI needles

**Files:**
- Modify: `frontend/src/scene.js`

- [ ] **Step 1: Raise default camera angle**

In `scene.js`, find:
```js
camera.position.set(0, 450, 550);
```
Replace with:
```js
camera.position.set(0, 380, 560);
```

This raises the polar angle from ~51° to ~56° for a better overview of the circular scene.

- [ ] **Step 2: Add `_addOuterNeedles` function and call it**

Add this function at the bottom of `scene.js` (before the export):

```js
export function addOuterNeedles(scene, outerPois, displayRadiusM) {
  const needles = [];
  const needleR = displayRadiusM * 0.93;

  outerPois.forEach(poi => {
    const color = new THREE.Color(BUILDING_COLORS[poi.category] || '#888888');
    // Use POI_COLORS if available; fall back gracefully
    const rad = (poi.bearing_deg * Math.PI) / 180;
    const x = Math.sin(rad) * needleR;
    const z = -Math.cos(rad) * needleR;

    const geo = new THREE.ConeGeometry(3, 15, 6);
    const mat = new THREE.MeshLambertMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.25,
    });
    const needle = new THREE.Mesh(geo, mat);
    needle.position.set(x, 8, z);
    needle.castShadow = false;
    scene.add(needle);
    needle.userData.poiCategory = poi.category;
    needles.push({ mesh: needle, mat, poi });
  });

  return {
    highlight(activePoi) {
      needles.forEach(({ mat, poi }) => {
        mat.emissiveIntensity = poi === activePoi ? 1.0 : 0.25;
      });
    },
  };
}
```

At the top of `scene.js`, the import line is:
```js
import { BUILDING_COLORS, BUILDING_COLOR_DEFAULT, GEO_LAYER_COLORS, ROAD_COLORS, ROAD_COLOR_DEFAULT } from './colors.js';
```

Add `POI_COLORS` to that import:
```js
import { BUILDING_COLORS, BUILDING_COLOR_DEFAULT, GEO_LAYER_COLORS, ROAD_COLORS, ROAD_COLOR_DEFAULT, POI_COLORS } from './colors.js';
```

Then update `addOuterNeedles` to use `POI_COLORS`:
```js
const colorHex = POI_COLORS[poi.category] || '#888888';
const color = new THREE.Color(colorHex);
```

Update `createScene` to accept and return the Three.js `scene` object, and call `addOuterNeedles`:

```js
// In createScene, after addPOIs block (around line 104), add:
let needleController = null;
if (sceneData.outer_pois && sceneData.outer_pois.length > 0) {
  const { addOuterNeedles: _add } = await import('./scene.js').catch(() => ({ addOuterNeedles }));
  needleController = addOuterNeedles(scene, sceneData.outer_pois, sceneData.display_radius_m || 450);
}
```

Wait — the function is in the same file. Just call it directly:

```js
// After the addPOIs block, add:
let needleController = null;
if (sceneData.outer_pois && sceneData.outer_pois.length > 0) {
  needleController = addOuterNeedles(scene, sceneData.outer_pois, sceneData.display_radius_m || 450);
}
```

Update the `return` at the bottom of `createScene`:
```js
// OLD:
_activeScene = { dispose };
return { dispose };
// NEW:
_activeScene = { dispose };
return { dispose, scene, needleController };
```

- [ ] **Step 3: Verify in browser**

Open http://localhost:5173, search Pezinok. If Overpass returns POIs beyond 450 m, small coloured cone pins should appear at the circle boundary. Camera should be slightly higher than before.

If Overpass is still down (no POIs), test by temporarily hardcoding an outer POI in `main.js` for visual check, then remove it.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/scene.js
git commit -m "feat: raise camera angle and add outer POI needle pins to scene"
```

---

## Task 6: Frontend — `route.js` (route hint tube)

**Files:**
- Create: `frontend/src/route.js`

- [ ] **Step 1: Create `frontend/src/route.js`**

```js
import * as THREE from 'three';

let _activeTube = null;
let _activeFallback = null;

/**
 * Fetches a route from /api/route and renders the first ~450 m as a 3D tube.
 * Falls back to a dashed straight line if the API fails.
 */
export async function showRouteHint(scene, fromLat, fromLon, toLat, toLon, color) {
  hideRouteHint(scene);

  try {
    const resp = await fetch(
      `/api/route?from_lat=${fromLat}&from_lon=${fromLon}&to_lat=${toLat}&to_lon=${toLon}`
    );
    if (!resp.ok) throw new Error(`route ${resp.status}`);
    const data = await resp.json();
    const coords = data.routes?.[0]?.geometry?.coordinates;
    if (!coords || coords.length < 2) throw new Error('no geometry');

    const truncated = _truncateRoute(coords, 450);
    if (truncated.length < 2) throw new Error('too short');

    const pts = truncated.map(([lon, lat]) => {
      const { x, y } = _latLonToLocal(lat, lon, fromLat, fromLon);
      return new THREE.Vector3(x, 1.5, -y);
    });

    const curve = new THREE.CatmullRomCurve3(pts);
    const geo = new THREE.TubeGeometry(curve, Math.max(4, truncated.length * 2), 1.5, 6, false);
    const mat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(color),
      transparent: true,
      opacity: 0.85,
    });
    _activeTube = new THREE.Mesh(geo, mat);
    scene.add(_activeTube);
  } catch {
    _showFallback(scene, fromLat, fromLon, toLat, toLon, color);
  }
}

export function hideRouteHint(scene) {
  if (_activeTube) {
    _activeTube.geometry.dispose();
    _activeTube.material.dispose();
    scene.remove(_activeTube);
    _activeTube = null;
  }
  if (_activeFallback) {
    _activeFallback.geometry.dispose();
    scene.remove(_activeFallback);
    _activeFallback = null;
  }
}

export function _latLonToLocal(lat, lon, centerLat, centerLon) {
  const metersPerDegLat = 111320;
  const metersPerDegLon = 111320 * Math.cos(centerLat * Math.PI / 180);
  return {
    x: (lon - centerLon) * metersPerDegLon,
    y: (lat - centerLat) * metersPerDegLat,
  };
}

function _showFallback(scene, fromLat, fromLon, toLat, toLon, color) {
  const bearing = _bearing(fromLat, fromLon, toLat, toLon);
  const rad = (bearing * Math.PI) / 180;
  const len = 430;
  const pts = [
    new THREE.Vector3(0, 1.0, 0),
    new THREE.Vector3(Math.sin(rad) * len, 1.0, -Math.cos(rad) * len),
  ];
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineDashedMaterial({
    color: new THREE.Color(color),
    dashSize: 10,
    gapSize: 6,
    transparent: true,
    opacity: 0.7,
  });
  _activeFallback = new THREE.Line(geo, mat);
  _activeFallback.computeLineDistances();
  scene.add(_activeFallback);
}

function _truncateRoute(coords, maxMeters) {
  let dist = 0;
  const result = [coords[0]];
  for (let i = 1; i < coords.length; i++) {
    const [lon0, lat0] = coords[i - 1];
    const [lon1, lat1] = coords[i];
    dist += _haversineM(lat0, lon0, lat1, lon1);
    result.push(coords[i]);
    if (dist >= maxMeters) break;
  }
  return result;
}

function _haversineM(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const r = Math.PI / 180;
  const phi1 = lat1 * r, phi2 = lat2 * r;
  const a = Math.sin((lat2 - lat1) * r / 2) ** 2
    + Math.cos(phi1) * Math.cos(phi2) * Math.sin((lon2 - lon1) * r / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function _bearing(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180;
  const phi1 = lat1 * r, phi2 = lat2 * r;
  const dlam = (lon2 - lon1) * r;
  const x = Math.sin(dlam) * Math.cos(phi2);
  const y = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dlam);
  return ((Math.atan2(x, y) / r) + 360) % 360;
}
```

- [ ] **Step 2: Verify module loads without error**

```bash
cd /home/mato/Dev/tf/genmap/frontend
npm run build 2>&1 | tail -10
```

Expected: build succeeds with no errors referencing `route.js`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/route.js
git commit -m "feat: add route.js OSRM route hint renderer with fallback dashed line"
```

---

## Task 7: Frontend — `main.js` wiring

**Files:**
- Modify: `frontend/src/main.js`

- [ ] **Step 1: Wire frame and route hint into the demo flow**

The current `init()` function calls `createScene(container, sceneData, 'demo')`. Replace that section with:

```js
// At the top of main.js, add imports:
import { initFrame } from './frame.js';
import { showRouteHint, hideRouteHint } from './route.js';
import { POI_COLORS } from './colors.js';
```

In the `initDemoUI` callback, replace:
```js
// OLD:
const sceneData = await fetchScene(lat, lon);
const container = document.getElementById('threejs-mount');
createScene(container, sceneData, 'demo');
```

With:
```js
const sceneData = await fetchScene(lat, lon);
const container = document.getElementById('threejs-mount');
const frameContainer = document.getElementById('canvas-container');
const { scene, needleController } = createScene(container, sceneData, 'demo');

// Clear any previous frame indicators
document.querySelectorAll('.outer-poi-indicator').forEach(el => el.remove());

// Render outer POI indicators
if (sceneData.outer_pois && sceneData.outer_pois.length > 0) {
  const center = sceneData.center;
  initFrame(
    frameContainer,
    sceneData.outer_pois,
    center.lat,
    center.lon,
    // onHover
    (poi, el) => {
      const color = POI_COLORS[poi.category] || '#888888';
      if (needleController) needleController.highlight(poi);
      // Show info card
      const card = document.getElementById('outer-poi-info-card');
      const rect = el.getBoundingClientRect();
      const containerRect = frameContainer.getBoundingClientRect();
      card.style.left = `${rect.left - containerRect.left + rect.width / 2}px`;
      card.style.top = `${rect.top - containerRect.top - 10}px`;
      card.style.transform = 'translate(-50%, -100%)';
      document.getElementById('opc-name').textContent = poi.name;
      document.getElementById('opc-meta').textContent =
        `${poi.category} · ${poi.distance_m >= 1000 ? (poi.distance_m / 1000).toFixed(1) + ' km' : poi.distance_m + ' m'}`;
      card.classList.add('visible');
      showRouteHint(scene, center.lat, center.lon, poi.lat, poi.lon, color);
    },
    // onLeave
    (poi, el) => {
      if (needleController) needleController.highlight(null);
      document.getElementById('outer-poi-info-card').classList.remove('visible');
      hideRouteHint(scene);
    },
  );
}
```

- [ ] **Step 2: Handle embed/view mode**

In the embed/view branch of `init()`, after `createScene(container, sceneData, mode)`, add:

```js
const { scene: embedScene, needleController: embedNeedles } = createScene(container, sceneData, mode);
if (sceneData.outer_pois && sceneData.outer_pois.length > 0) {
  const center = sceneData.center;
  const frameContainer = document.getElementById('canvas-container');
  initFrame(
    frameContainer,
    sceneData.outer_pois,
    center.lat,
    center.lon,
    (poi) => {
      const color = POI_COLORS[poi.category] || '#888888';
      if (embedNeedles) embedNeedles.highlight(poi);
      showRouteHint(embedScene, center.lat, center.lon, poi.lat, poi.lon, color);
    },
    (poi) => {
      if (embedNeedles) embedNeedles.highlight(null);
      hideRouteHint(embedScene);
    },
  );
}
```

- [ ] **Step 3: Verify end-to-end in browser**

1. Open http://localhost:5173
2. Search "Pezinok Slovensko"
3. Confirm: inner 3D scene appears as circle on dark background
4. If any POIs are returned and some are > 450 m away: confirm outer indicators appear as pills around the perimeter
5. Hover an outer indicator: confirm info card appears, route hint tube draws along road (or dashed fallback if OSRM unreachable)
6. Move mouse away: confirm tube disappears

To force outer POIs for testing when Overpass is down, temporarily add to the `fetchScene` result in `main.js`:

```js
// TEMP: inject a fake outer POI for visual testing — remove after confirming
if (!sceneData.outer_pois || sceneData.outer_pois.length === 0) {
  sceneData.outer_pois = [
    { name: 'Nemocnica Pezinok', category: 'hospital', distance_m: 2100, bearing_deg: 335, lat: 48.307, lon: 17.266 },
    { name: 'Gymnázium', category: 'school', distance_m: 1500, bearing_deg: 45, lat: 48.299, lon: 17.285 },
  ];
}
```

Remove this after visual verification.

- [ ] **Step 4: Run full test suite**

```bash
# Backend
cd /home/mato/Dev/tf/genmap
python -m pytest tests/ -v

# Frontend
cd /home/mato/Dev/tf/genmap/frontend
npm test
```

Expected: all tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/main.js
git commit -m "feat: wire outer POI frame, needles and route hint into demo and embed modes"
```

---

## Self-Review

**Spec coverage check:**

| Spec Section | Task |
|---|---|
| Layout & visual structure (HTML frame + 3D canvas) | Task 3, 7 |
| Circular clip + fade vignette | Task 3 |
| POI threshold + `display_radius_m` | Task 1 |
| `outer_pois` in scene JSON | Task 1 |
| `/api/route` endpoint | Task 2 |
| Outer POI frame indicators (pills, positioning, collision) | Task 4 |
| 3D needles at scene boundary | Task 5 |
| Hover: info card | Task 7 |
| Hover: route tube | Task 6, 7 |
| Fallback dashed line | Task 6 |
| Priority ordering + max 8 | Task 4 |
| Camera angle raised | Task 5 |

All spec requirements covered. ✓

**Placeholder scan:** No TBDs or incomplete steps. ✓

**Type consistency:**
- `outer_pois` shape: `{ name, category, distance_m, bearing_deg, lat, lon }` — consistent across Task 1 (backend), Task 4 (`initFrame` input), Task 5 (`addOuterNeedles` input), Task 7 (wiring).
- `createScene` return: `{ dispose, scene, needleController }` — consistent across Task 5 (change) and Task 7 (consume).
- `needleController.highlight(poi | null)` — defined in Task 5, called in Task 7. ✓
- `showRouteHint(scene, fromLat, fromLon, toLat, toLon, color)` — defined in Task 6, called in Task 7. ✓
- `hideRouteHint(scene)` — defined in Task 6, called in Task 7. ✓
- `initFrame(container, outerPois, centerLat, centerLon, onHover, onLeave)` — defined in Task 4, called in Task 7. ✓
