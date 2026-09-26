# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

**HoodieMap** — generates playful neighbourhood infographics for real estate listings. A FastAPI backend turns OpenStreetMap data into a compact scene JSON; a Three.js frontend renders it as a pastel isometric widget showing only ±140 m around the property. Nearby POIs are marked on the map, farther ones are hinted as badges on the widget edge in their direction ("Nemocnica · 3,6 km →").

Design: `docs/superpowers/specs/2026-09-26-playful-iso-map-design.md`. Default center: Pezinok, Slovakia (`config.yaml`).

## Running the App

```bash
.venv/bin/pip install -r requirements.txt
cd frontend && npm install

# Backend (terminal 1)
.venv/bin/python src/api.py        # FastAPI on http://localhost:8000

# Frontend (terminal 2)
cd frontend && npm run dev         # Vite on http://localhost:5173 (proxies /api)
```

Open `http://localhost:5173/?lat=…&lon=…`, or `?fixture=true` for offline dev with `fixtures/pezinok-centrum.json` (regenerate with `.venv/bin/python scripts/capture_fixture.py` after changing the scene format).

Tests: `.venv/bin/python -m pytest` (backend, no network) and `cd frontend && npm test` (vitest, pure helpers).

## Configuration (`config.yaml`, validated by `src/config.py`)

```yaml
location: {lat: 48.28646434486518, lon: 17.27221245956356}
radii:
  display_meters: 140      # half-size of the visible square
poi:
  show: {hospital: true, supermarket: true, school: true, kindergarten: true,
         pharmacy: true, bus_stop: true, train: true, park: true, playground: true,
         food: true, post: true, bank: true, doctors: true, city: true}
cache: {enabled: true, dir: .cache}
api: {host: "0.0.0.0", port: 8000}
```

## Architecture

```
src/
  api.py            GET /api/scene (+ Nominatim address), /api/geocode, /health; serves frontend/dist in prod
  scene_builder.py  build_scene(): rules (building kind/height, road kind, area layer), clipping, property, POI split
  osm.py            Overpass queries, 3-endpoint fallback, User-Agent, JSON cache (.cache/osm, 30 days)
  geo.py            haversine, bearing, equirectangular local projection (metres, x east, y north)
  config.py         Pydantic config
frontend/src/
  main.js           URL params, fetch, loading/error states
  map/stage.js      renderer, ortho iso camera, lights, render loop (pauses off-screen, respects reduced motion)
  map/ground.js, buildings.js, trees.js, cars.js, people.js, property.js   Three.js layers (people = pedestrians, cyclists, chat groups)
  map/decor.js, pigeons.js, clouds.js, textures.js               street furniture + café terraces (instanced), pigeon flock, cloud-shadow shader patch
  map/geom.js, lines.js, roofs.js, placement.js                  pure geometry (unit-tested)
  overlay/labels.js, edge.js                                     HTML labels + edge badge placement
  overlay/tooltip.js, describe.js, map/hover.js                 hover/tap/focus info bubbles (walk/drive time, opening hours), building glow via raycast
  palette.js, icons.js, format.js, random.js, url.js
```

### Pipeline

`GET /api/scene?lat&lon` → `build_scene()` runs two Overpass queries in parallel: the area (buildings, roads, parks, water, forest, trees in the square + 20 m) and the POIs (bbox per category radius). Geometry is projected to local metres and clipped to the square. Buildings less than 40 % inside are dropped. Each building is classified house/apartment/commercial/civic/other. The property is the building containing the center, or the nearest one within 15 m. Only the nearest POI per category is kept (cities: two nearest): it goes to `near_pois` when inside the square (10 m inset), otherwise to `far_pois` with `bearing_deg`. If the POI query fails, the scene is still returned with `warnings: ["poi_fetch_failed"]`. If the area query fails, the API returns 502.

Pedestrian zones: `highway=pedestrian` lines are road kind `pedestrian` (10 m paved ribbon); `highway=pedestrian`+`area=yes` and `place=square` become `areas.plaza`. Benches/lamps/planters line both edges, pigeons and chatting groups gather there (fallback: largest park). Cloud shadows are injected into every material via the material cache's `onCreate` hook.

Backend (x, y) maps to Three (x, 0, −y). Houses with a near-rectangular footprint get gable roofs, other houses get hip roofs, and larger buildings get flat roofs with a colored cap.

### POI categories (`osm.py`)

| Category     | OSM tag | Search radius |
|--------------|---------|---------------|
| hospital     | `amenity=hospital` | 30 km |
| supermarket  | `shop=supermarket` | 5 km |
| school       | `amenity=school` | 5 km |
| kindergarten | `amenity=kindergarten` | 5 km |
| pharmacy     | `amenity=pharmacy` | 5 km |
| bus_stop     | `highway=bus_stop` | 3 km |
| train        | `railway=station|halt` | 30 km |
| park         | `leisure=park` (named or ≥ 0.5 ha) | 3 km |
| playground   | `leisure=playground` | 300 m, map only |
| food         | `amenity=cafe|restaurant` | 300 m, map only (icon marker) |
| post         | `amenity=post_office` | 300 m, map only |
| bank         | `amenity=bank` | 300 m, map only |
| doctors      | `amenity=doctors|clinic|dentist` | 300 m, map only |
| city         | `place=city` | 70 km, 2 nearest ≥ 5 km away, edge badges only |

The POI query uses `out bb tags` (bbox centre = position, bbox size = area check). Specialized hospitals (psychiatric, oncology, rehab…) are skipped. A near POI gets `building_index` (the building it sits in, ≤ 6 m) and that building's roof takes the category colour.

### Known risks

- Public Overpass servers are often overloaded (504 / timeouts). Cold requests can take 10–60 s; cached ones are instant. Failures are not cached.
- OSM data quality: missing names fall back to the category label.

### Planned Stages

- Travel time in minutes next to km
- Public data overlays (prices)
- Static image / PDF export

## Data Sources

- Street network & POIs: OpenStreetMap via Overpass API (no key required)
- Future: public price registries, real estate APIs
