# HoodieMap — Location Search with Address / Street / City Tiers

**Date:** 2026-09-26
**Status:** Draft, awaiting review
**Builds on:** `2026-09-26-playful-iso-map-design.md` and the `feat/lively-map` branch (pedestrian zones, people, hover bubbles)

---

## Why

Today the widget only takes `?lat=&lon=` and always shows ±140 m around one building. Real estate agencies often publish only the street, not the house number, and visitors want to explore a whole town. We want one search box where a typed place decides the scale of the map, and the POIs shown make sense at that scale. For now the purpose is testing: how it looks and how fast each tier loads.

## Goal

- A search box above the map. Enter a query, press Enter: the best match loads immediately (no result list).
- The tier comes from what was typed:
  - street + house number → **address** tier (today's view, ±140 m),
  - street only → **street** tier (the whole street, with a "Na predaj" highlight on the street),
  - town / village / borough → **city** tier (its centre, ±450 m, with landmarks and key services).
- POIs per tier are chosen so they are meaningful at that scale.
- The load time is visible under the map ("Načítané za 12,4 s · nové dáta" / "0,1 s · z cache").

Success: the five test queries below load and look right; address and street tiers load in under ~10 s cold; the city tier's cold time is measured and reported (target under ~40 s); every tier is instant from cache.

## Non-goals

- The agent / configuration page (use case 2) and embed link generation.
- A list of alternative search results or autocomplete (forbidden by the Nominatim usage policy anyway).
- Real routing times (the existing rough walk/drive estimate stays).
- A stylized "diorama" city tier (approach B) — revisit only if the city tier proves too slow.

## Known risk

An earlier version of this project rendered 450 m around a point and one cold request took over 4 minutes, mostly because of overloaded Overpass servers and heavy POI queries. The city tier returns to that radius. Mitigations: a lighter area query at the city tier (no footways, no tree nodes), a longer Overpass timeout only there, merged building meshes on the frontend, and measuring the cold time as part of acceptance. If it is unacceptable, shrink `radii.city_meters` first.

---

## 1. Search and tier detection

### Geocoding (`GET /api/geocode?q=`)

- Calls Nominatim `search` with `format=jsonv2`, `limit=1`, `addressdetails=1`, `countrycodes` from config (default `sk,cz`), `accept-language=sk`.
- Returns one result or 404:

```json
{
  "lat": 48.2895, "lon": 17.2696,
  "tier": "street",
  "name": "Záhradná",
  "label": "Záhradná, Pezinok",
  "place_rank": 26
}
```

- Tier from `place_rank`:

| place_rank | Typical match | Tier |
|---|---|---|
| ≥ 28 | building, house number | `address` |
| 26–27 | road, pedestrian way | `street` |
| ≤ 25 | town, village, borough, suburb | `city` |

- If a house number is not in OSM, Nominatim returns the street (rank 26) — the street tier is then the correct fallback.
- `label` is short: road + house number (if any) + town, else the place name. It is shown in the address chip with the tier: "Záhradná, Pezinok · ulica".
- Throttle: at most 1 Nominatim request per second (process-wide lock). Results cached in `.cache/geocode/` for 30 days, keyed by normalized query. Timeout 5 s.
- The existing reverse geocode for `/api/scene` stays for plain `?lat=&lon=` links.

### Frontend flow

1. User types, presses Enter (or clicks the search button).
2. `GET /api/geocode?q=…` → on success the URL becomes `?lat=…&lon=…&tier=…&name=…&label=…` (shareable, reloadable) and the scene loads.
3. A newer search aborts any request still in flight (`AbortController`), so a stale scene never replaces a newer one.
4. Plain `?lat=&lon=` with no `tier` keeps working as the address tier.

## 2. Scene per tier (`GET /api/scene?lat&lon&tier=address|street|city[&name=]`)

The response keeps today's shape and adds:

```json
{
  "tier": "street",
  "radius_m": 240,
  "focus": {"kind": "street", "name": "Záhradná", "lines": [[[x, y], …], …]},
  "timing_ms": 8421,
  "cached": false
}
```

- `focus` is `{"kind": "building"}` for the address tier (property as today), `{"kind": "street", …}` for the street tier, `{"kind": "centre"}` for the city tier.
- `cached` is true when both Overpass queries came from the cache.

### Address tier

Unchanged: ±`radii.display_meters` (140 m) around the point; the property is the building at or nearest the point.

### Street tier

- Overpass: `way["highway"]["name"="<name>"](around:1500,lat,lon)` with geometry.
- Keep only ways connected (within 30 m, transitively) to the way nearest the geocoded point — avoids joining two different streets of the same name in neighbouring villages.
- Street length `L` = total length of the kept ways. Centre = the point halfway along the street (for branching streets: the centre of the kept ways' bounding box).
- `radius_m = clamp(L / 2 + 60, radii.street_min, radii.street_max)` (defaults 160 / 300).
- Long streets (`L / 2 + 60 > street_max`): centre on the geocoded point instead, radius `street_max`; the highlight is clipped to the square.
- If no way is found: centre on the geocoded point, radius `street_min`, no highlight, no warning to the user.
- No property building; the "Na predaj" tag sits on the street midpoint (or on the geocoded point for long streets).

### City tier

- Centre = the geocoded point (for towns Nominatim returns the place node, usually the historic centre). Radius `radii.city_meters` (default 450).
- Lighter area query: no footway / path / steps / track ways, no `natural=tree` nodes. Overpass timeout 60 s (25 s elsewhere); HTTP timeout 70 s.
- No property and no "Na predaj" tag.

## 3. POIs per tier

| Category | Address | Street | City |
|---|---|---|---|
| hospital, train, park, supermarket | ✓ | ✓ | ✓ |
| school, kindergarten, pharmacy, bus_stop | ✓ | ✓ | — |
| food, post, bank, doctors, playground (map-only icons) | ✓ | ✓ | — |
| bus_station (`amenity=bus_station`), mall (`shop=mall`) | — | — | ✓ |
| landmarks (see below) | — | — | ✓ (up to 3) |
| 2 nearest other cities | ✓ | ✓ | ✓ |

Map-only icons are already limited to the nearest one per category (5 at most), so no extra cap is needed.

- **Distances:** address tier — from the point; street tier — from the nearest point on the street lines (bearing still from the centre); city tier — from the centre.
- **Map vs edge:** unchanged rule — inside the square (10 m inset) the POI is on the map, otherwise an edge badge with bearing. Landmarks outside the square are dropped (they are about the centre, not directions).
- **Landmarks:** candidates within the square that carry `wikipedia` or `wikidata` and match one of, in priority order:
  1. `amenity=townhall`
  2. `place=square` or `highway=pedestrian` + `area=yes` with a name
  3. `historic=castle` / `historic=manor` / `castle_type=*`
  4. `building=church|cathedral` or `amenity=place_of_worship`
  5. `tourism=museum|attraction`
  Pick up to 3: best priority first, then distance from the centre; at most one per priority group. Category `landmark` with a `kind` for the label ("Radnica", "Námestie", "Hrad", "Kostol", "Múzeum"); the building gets the landmark colour like other POI buildings.
- **Cities:** unchanged (`place=city`, ≥ 5 km, 2 nearest) — for a city-tier search this naturally excludes the city itself.
- The POI query stays one Overpass request per scene; category radii as today, plus `bus_station` 30 km, `mall` 15 km, landmarks = the square.

## 4. Rendering and performance (frontend)

### Detail by tier

| Element | Address | Street | City |
|---|---|---|---|
| Buildings, roofs, POI roof colours | ✓ | ✓ | ✓ |
| Roads; lane markings | ✓ | ✓ | roads only |
| Footways | ✓ | ✓ | — (not fetched) |
| Pedestrian zone paving | ✓ | ✓ | ✓ |
| Benches, lamps, planters, café terraces | ✓ | — | — |
| Pedestrians / cyclists | full | half | — |
| Pigeons, chat groups | ✓ | — | — |
| Cars | ✓ | ✓ | ✓ (max 10) |
| Seeded park trees | ✓ | ✓ | OSM trees only (none fetched → none) |
| Cloud shadows | ✓ | ✓ | ✓ |
| Street highlight + "Na predaj" | — | ✓ | — |
| Property pin + ring | ✓ | — | — |

A single `detailFor(tier)` function returns these switches; layers read it.

### Street highlight

The street lines are drawn as a ribbon 14 m wide (about 4 m of band on each side of a street; tuned visually) in the property colour at ~35 % opacity under the road surface, plus a gentle pulse; the "Na predaj" tag is anchored at the street midpoint.

### Merged buildings

- All buildings of one material (walls per colour, roofs per colour) are merged into one `BufferGeometry` each (`BufferGeometryUtils.mergeGeometries`), with a per-vertex `buildingIndex` attribute.
- Hover: raycast the merged meshes, read `buildingIndex` of the hit face's vertex. The glow is a separate mesh built on demand from that building's extruded footprint (1 % larger, white, emissive, 25 % opacity), removed on leave.
- Applies to all tiers (simpler than two code paths).

### Shadows and camera

- Shadow map 1024 for the address tier, 2048 for street and city; the shadow camera fits `radius_m` as today.
- Camera framing, label sizes, widget size (874 px), palette and hover bubbles are unchanged.

### Search UI

- A rounded search field with a search button above the map (same width as the map), placeholder "Zadajte mesto, ulicu alebo adresu".
- Loading: the existing status panel with the breathing slab and text naming the tier: "Načítavam ulicu Záhradná, Pezinok…".
- Under the map, small grey text: "Načítané za 12,4 s · nové dáta" or "Načítané za 0,1 s · z cache" (from `timing_ms` and `cached`; the client adds its own fetch time for the geocode step).
- Address chip: `label · tier` ("Záhradná, Pezinok · ulica").

## 5. Configuration

```yaml
radii:
  display_meters: 140   # address tier
  street_min: 160
  street_max: 300
  city_meters: 450
geocode:
  countrycodes: "sk,cz"
```

## 6. Errors and edge cases

| Situation | Behaviour |
|---|---|
| Nominatim: no result, or result outside `countrycodes` | 404 → "Nenašli sme „…“. Skúste pridať mesto alebo PSČ." The current map stays. |
| Nominatim down / timeout (5 s) | 503 → "Vyhľadávanie je dočasne nedostupné, skúste o chvíľu." |
| Overpass area query fails | 502 → existing error panel with retry; at the city tier the hint "Mestská úroveň je náročnejšia – skúste konkrétnu ulicu." |
| Overpass POI query fails | scene without POIs, `warnings: ["poi_fetch_failed"]` (as today) |
| Street query fails | treat as "no way found" (see street tier) and add `warnings: ["street_fetch_failed"]` |
| Newer search while loading | older requests aborted |

## 7. Testing

**Backend (pytest, no network):**
- tier from `place_rank` (boundaries 25/26/27/28), label building, countrycodes passed through;
- geocode cache hit/miss and the 1 req/s throttle (injected clock);
- street assembly: connected-component filter, centre, radius clamp, long-street fallback, no-way fallback;
- street-tier distances from the street lines;
- city-tier POI set: excluded categories, landmark priority, one per group, max 3, Wikipedia/Wikidata filter, landmarks outside the square dropped;
- city-tier area query excludes footways and trees; timeout 60;
- `/api/scene` returns `tier`, `focus`, `timing_ms`, `cached`; `/api/geocode` 404 / 503.

**Frontend (vitest):**
- URL parsing of `tier`, `name`, `label` (and defaults for plain lat/lon);
- `detailFor(tier)`;
- building merge: vertex → building index mapping;
- load-time text formatting.

**Manual, in the browser, cold and cached, times recorded in the PR:**
"Záhradná 12, Pezinok", "Záhradná, Pezinok", "Pezinok", "Obchodná, Bratislava", "Staré Mesto, Bratislava".
