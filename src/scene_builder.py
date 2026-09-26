"""Turn raw Overpass JSON into the compact scene consumed by the frontend."""
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from shapely.geometry import LineString, MultiLineString, Point, Polygon, box
from shapely.ops import polygonize

from config import Config
from geo import compute_bearing, from_local, haversine_m, to_local
from osm import OverpassError, categorize_poi, fetch_area, fetch_pois, fetch_street, landmark_kind
from street import street_anchor, street_frame, street_lines

logger = logging.getLogger(__name__)

CIVIC = frozenset({"school", "kindergarten", "church", "chapel", "hospital", "public", "civic",
                   "government", "train_station"})
COMMERCIAL = frozenset({"retail", "commercial", "office", "supermarket", "industrial", "warehouse", "hotel"})
OTHER = frozenset({"garage", "garages", "shed", "roof", "carport", "hut", "service"})
HOUSE = frozenset({"house", "detached", "semidetached_house", "terrace", "bungalow"})
HOUSE_MAX_AREA_M2 = 250
HOUSE_MAX_LEVELS = 2
DEFAULT_HEIGHT = {"house": 6.0, "apartment": 12.0, "commercial": 8.0, "civic": 10.0, "other": 3.0}
METERS_PER_LEVEL = 3.0
MIN_HEIGHT_M, MAX_HEIGHT_M = 2.0, 150.0  # guards against tag typos (height=500, inf)

ROAD_KINDS: dict[str, str] = {
    **dict.fromkeys(["primary", "secondary", "tertiary", "primary_link", "secondary_link", "tertiary_link"], "main"),
    **dict.fromkeys(["residential", "unclassified", "living_street", "service", "road"], "street"),
    **dict.fromkeys(["footway", "path", "cycleway", "steps", "track"], "path"),
    "pedestrian": "pedestrian",
}
PARK_LEISURE = frozenset({"park", "garden", "playground"})
PARK_LANDUSE = frozenset({"grass", "meadow", "recreation_ground", "village_green"})


def _num(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).lower().replace("m", "").replace(",", ".").strip())
    except ValueError:
        return None


def classify_building(tags: dict, area_m2: float) -> str:
    b = str(tags.get("building", "yes")).lower()
    if b in CIVIC:
        return "civic"
    if b in COMMERCIAL:
        return "commercial"
    if b in OTHER:
        return "other"
    if b in HOUSE:
        return "house"
    levels = _num(tags.get("building:levels"))
    small = area_m2 < HOUSE_MAX_AREA_M2 and (levels is None or levels <= HOUSE_MAX_LEVELS)
    if b in ("yes", "residential") and small:
        return "house"
    return "apartment"


def building_height(tags: dict, kind: str) -> float:
    height = _num(tags.get("height"))
    if height is None or not height > 0:
        levels = _num(tags.get("building:levels"))
        height = levels * METERS_PER_LEVEL if levels is not None and levels > 0 else DEFAULT_HEIGHT[kind]
    return min(MAX_HEIGHT_M, max(MIN_HEIGHT_M, height))


def road_kind(highway) -> str | None:
    return ROAD_KINDS.get(str(highway))


def _is_plaza(tags: dict) -> bool:
    """Pedestrian squares mapped as areas (not as lines)."""
    return (tags.get("highway") == "pedestrian" and tags.get("area") == "yes") or tags.get("place") == "square"


def area_layer(tags: dict) -> str | None:
    if tags.get("natural") == "water" or tags.get("waterway") == "riverbank":
        return "water"
    if tags.get("landuse") == "forest" or tags.get("natural") == "wood":
        return "forest"
    if tags.get("leisure") in PARK_LEISURE or tags.get("landuse") in PARK_LANDUSE:
        return "park"
    return None


MIN_KEEP_RATIO = 0.4
MIN_BUILDING_AREA_M2 = 4.0
PROPERTY_MAX_DIST_M = 15.0
NEAR_INSET_M = 10.0
POI_BUILDING_MAX_DIST_M = 6.0
CITY_COUNT = 2
CITY_MIN_DIST_M = 5_000  # skip the city the property is in
LOCAL_ONLY = frozenset({"food", "post", "bank", "doctors", "playground"})
PARK_MIN_AREA_M2 = 5_000  # unnamed lawns in courtyards are often tagged leisure=park
# Psychiatric, oncology, rehab… hospitals are not what "nearest hospital" means to a buyer.
SPECIALIZED_HOSPITAL_WORDS = ("psychiatr", "onkolog", "liečebn", "rehabilit", "geriatr", "hospic")

_BUYER = frozenset({"hospital", "supermarket", "school", "kindergarten", "pharmacy", "bus_stop", "train", "park",
                    "playground", "food", "post", "bank", "doctors", "city"})
TIER_CATEGORIES = {
    "address": _BUYER,
    "street": _BUYER,
    # A city has dozens of schools and pharmacies — "the one nearest the square" means nothing.
    "city": frozenset({"hospital", "train", "park", "supermarket", "bus_station", "mall", "landmark", "city"}),
}
MAX_LANDMARKS = 3
NO_BUILDING = frozenset({"park", "playground"})


def _r(v: float) -> float:
    return round(v, 1)


def _coords(geometry, lat0: float, lon0: float) -> list[tuple[float, float]]:
    return [to_local(p["lat"], p["lon"], lat0, lon0) for p in geometry or [] if p]


def _parts(geom, geom_type: str) -> list:
    if geom.is_empty:
        return []
    if geom.geom_type == geom_type:
        return [geom]
    return [p for sub in getattr(geom, "geoms", []) for p in _parts(sub, geom_type)]


def _polygons(el: dict, lat0: float, lon0: float) -> list[Polygon]:
    if el.get("type") == "way":
        pts = _coords(el.get("geometry"), lat0, lon0)
        if len(pts) < 4 or pts[0] != pts[-1]:
            return []
        raw = [Polygon(pts)]
    elif el.get("type") == "relation":
        lines = [LineString(_coords(m["geometry"], lat0, lon0)) for m in el.get("members", [])
                 if m.get("role") == "outer" and len(m.get("geometry") or []) >= 2]
        raw = list(polygonize(lines))
    else:
        return []
    out = []
    for poly in raw:
        fixed = poly if poly.is_valid else poly.buffer(0)
        out.extend(_parts(fixed, "Polygon"))
    return out


def _ring(poly: Polygon) -> list[list[float]]:
    return [[_r(x), _r(y)] for x, y in list(poly.exterior.coords)[:-1]]


def _building(poly: Polygon, tags: dict, square) -> dict | None:
    if poly.area < MIN_BUILDING_AREA_M2:
        return None
    clipped = _parts(poly.intersection(square), "Polygon")
    if not clipped:
        return None
    main = max(clipped, key=lambda p: p.area)
    if main.area < MIN_KEEP_RATIO * poly.area:
        return None
    kind = classify_building(tags, poly.area)
    return {"footprint": _ring(main), "kind": kind, "height": _r(building_height(tags, kind))}


def find_property(buildings: list[dict]) -> int | None:
    origin = Point(0, 0)
    best, best_d = None, PROPERTY_MAX_DIST_M
    for i, b in enumerate(buildings):
        poly = Polygon(b["footprint"])
        if poly.contains(origin):
            return i
        d = poly.distance(origin)
        if d <= best_d:
            best, best_d = i, d
    return best


def _element_latlon(el: dict) -> tuple[float, float] | None:
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    center = el.get("center")
    if center:
        return center["lat"], center["lon"]
    b = el.get("bounds")
    if b:
        return (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2
    return None


def _bounds_area_m2(el: dict) -> float:
    b = el.get("bounds")
    if not b:
        return 0.0
    mid_lat = (b["minlat"] + b["maxlat"]) / 2
    h = haversine_m(b["minlat"], b["minlon"], b["maxlat"], b["minlon"])
    w = haversine_m(mid_lat, b["minlon"], mid_lat, b["maxlon"])
    return h * w


def _is_real_park(el: dict, tags: dict) -> bool:
    return bool(tags.get("name")) or _bounds_area_m2(el) >= PARK_MIN_AREA_M2


def _is_general_hospital(tags: dict) -> bool:
    speciality = str(tags.get("healthcare:speciality", "")).lower()
    name = str(tags.get("name", "")).lower()
    return speciality in ("", "general", "emergency") and not any(w in name for w in SPECIALIZED_HOSPITAL_WORDS)


def split_pois(lat: float, lon: float, radius_m: float, pois_raw: dict,
               categories: list[str], street=None) -> tuple[list[dict], list[dict]]:
    wanted = set(categories) - {"landmark"}
    street_geom = MultiLineString(street) if street else None

    def distance(plat: float, plon: float) -> float:
        if street_geom is None:
            return haversine_m(lat, lon, plat, plon)
        return street_geom.distance(Point(*to_local(plat, plon, lat, lon)))

    best: dict[str, tuple[float, dict, tuple[float, float]]] = {}
    cities: dict[str, tuple[float, dict, tuple[float, float]]] = {}
    for el in pois_raw.get("elements", []):
        tags = el.get("tags") or {}
        cat = categorize_poi(tags)
        pos = _element_latlon(el)
        if cat not in wanted or pos is None:
            continue
        if cat == "hospital" and not _is_general_hospital(tags):
            continue
        if cat == "park" and not _is_real_park(el, tags):
            continue
        d = distance(*pos)
        if cat == "city":
            name = tags.get("name", "")
            if name and d >= CITY_MIN_DIST_M and (name not in cities or d < cities[name][0]):
                cities[name] = (d, tags, pos)
            continue
        if cat not in best or d < best[cat][0]:
            best[cat] = (d, tags, pos)

    nearest_cities = sorted(cities.values(), key=lambda v: v[0])[:CITY_COUNT]
    candidates = [(cat, v) for cat, v in best.items()] + [("city", v) for v in nearest_cities]

    near, far = [], []
    limit = radius_m - NEAR_INSET_M
    for cat, (d, tags, (plat, plon)) in sorted(candidates, key=lambda kv: kv[1][0]):
        entry = {"category": cat, "name": tags.get("name", ""), "distance_m": round(d)}
        if tags.get("opening_hours"):
            entry["opening_hours"] = tags["opening_hours"]
        x, y = to_local(plat, plon, lat, lon)
        if abs(x) <= limit and abs(y) <= limit and cat != "city":
            near.append({**entry, "x": _r(x), "y": _r(y)})
        elif cat not in LOCAL_ONLY:
            far.append({**entry, "bearing_deg": round(compute_bearing(lat, lon, plat, plon), 1)})
    return near, far


def select_landmarks(lat: float, lon: float, radius_m: float, pois_raw: dict) -> list[dict]:
    """Up to MAX_LANDMARKS notable places inside the square: best kind first, then nearest; one per kind."""
    limit = radius_m - NEAR_INSET_M
    found = []
    for el in pois_raw.get("elements", []):
        tags = el.get("tags") or {}
        kind = landmark_kind(tags)
        pos = _element_latlon(el)
        if kind is None or pos is None or not (tags.get("wikipedia") or tags.get("wikidata")):
            continue
        x, y = to_local(*pos, lat, lon)
        if abs(x) > limit or abs(y) > limit:
            continue  # landmarks describe the centre, not a direction
        found.append((kind[0], haversine_m(lat, lon, *pos), kind[1], tags, x, y))
    found.sort(key=lambda f: (f[0], f[1]))
    picked, seen = [], set()
    for prio, d, label, tags, x, y in found:
        if prio in seen:
            continue
        seen.add(prio)
        picked.append({"category": "landmark", "kind": label, "name": tags.get("name", ""),
                       "distance_m": round(d), "x": _r(x), "y": _r(y)})
        if len(picked) == MAX_LANDMARKS:
            break
    return picked


def poi_building(poi: dict, buildings: list[dict], exclude: int | None) -> int | None:
    """Index of the building the POI sits in (or right next to), so the map can highlight it."""
    pt = Point(poi["x"], poi["y"])
    best, best_d = None, POI_BUILDING_MAX_DIST_M
    for i, b in enumerate(buildings):
        if i == exclude or b["kind"] == "other":
            continue
        d = Polygon(b["footprint"]).distance(pt)
        if d == 0:
            return i
        if d <= best_d:
            best, best_d = i, d
    return best


def assemble_scene(lat: float, lon: float, radius_m: float, area: dict, pois_raw: dict,
                   categories: list[str], tier: str = "address", street=None) -> dict:
    square = box(-radius_m, -radius_m, radius_m, radius_m)
    buildings, roads, trees = [], [], []
    areas: dict[str, list] = {"park": [], "water": [], "forest": [], "plaza": []}

    for el in area.get("elements", []):
        tags = el.get("tags") or {}
        if el.get("type") == "node":
            if tags.get("natural") == "tree":
                x, y = to_local(el["lat"], el["lon"], lat, lon)
                if abs(x) <= radius_m and abs(y) <= radius_m:
                    trees.append({"x": _r(x), "y": _r(y)})
            continue
        if "building" in tags:
            for poly in _polygons(el, lat, lon):
                b = _building(poly, tags, square)
                if b:
                    buildings.append(b)
        elif _is_plaza(tags):
            for poly in _polygons(el, lat, lon):
                for part in _parts(poly.intersection(square), "Polygon"):
                    if part.area >= 1.0:
                        areas["plaza"].append(_ring(part))
        elif "highway" in tags:
            kind = road_kind(tags["highway"])
            pts = _coords(el.get("geometry"), lat, lon)
            if kind is None or el.get("type") != "way" or len(pts) < 2:
                continue
            for part in _parts(LineString(pts).intersection(square), "LineString"):
                roads.append({"points": [[_r(x), _r(y)] for x, y in part.coords], "kind": kind})
        else:
            layer = area_layer(tags)
            if layer is None:
                continue
            for poly in _polygons(el, lat, lon):
                for part in _parts(poly.intersection(square), "Polygon"):
                    if part.area >= 1.0:
                        areas[layer].append(_ring(part))

    near, far = split_pois(lat, lon, radius_m, pois_raw, categories, street=street if tier == "street" else None)
    if "landmark" in categories:
        near += select_landmarks(lat, lon, radius_m, pois_raw)
    property_index = find_property(buildings) if tier == "address" else None
    for poi in near:
        if poi["category"] not in NO_BUILDING and poi.get("kind") != "Námestie":
            poi["building_index"] = poi_building(poi, buildings, property_index)
    return {
        "center": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "tier": tier,
        "focus": _focus(tier, street, square),
        "buildings": buildings,
        "property": {"building_index": property_index},
        "roads": roads,
        "areas": areas,
        "trees": trees,
        "near_pois": near,
        "far_pois": far,
    }


def _focus(tier: str, street, square) -> dict:
    if tier == "address":
        return {"kind": "building"}
    if tier == "city":
        return {"kind": "centre"}
    lines = []
    for line in street or []:
        for part in _parts(LineString(line).intersection(square), "LineString"):
            lines.append([[_r(x), _r(y)] for x, y in part.coords])
    ax, ay = street_anchor(street or [])
    return {"kind": "street", "lines": lines, "anchor": [_r(ax), _r(ay)]}


def build_scene(lat: float, lon: float, cfg: Config, tier: str = "address", name: str | None = None) -> dict:
    t0 = time.perf_counter()
    cache_dir = cfg.cache.dir if cfg.cache.enabled else None
    stats: list[bool] = []  # one entry per Overpass query: True = served from cache
    warnings: list[str] = []
    lines = None
    radius = {"address": cfg.radii.display_meters, "city": cfg.radii.city_meters}.get(tier, cfg.radii.street_min)
    if tier == "street":
        lines = []
        if name:
            try:
                lines = street_lines(fetch_street(name, lat, lon, cache_dir, stats), lat, lon)
            except OverpassError as exc:
                logger.warning("Street fetch failed: %s", exc)
                warnings.append("street_fetch_failed")
        frame = street_frame(lines, cfg.radii.street_min, cfg.radii.street_max)
        radius = frame["radius_m"]
        lat, lon = from_local(frame["x"], frame["y"], lat, lon)
        # Shifting local metres is exact enough for a few hundred metres (equirectangular projection).
        lines = [[(x - frame["x"], y - frame["y"]) for x, y in line] for line in lines]
    categories = [c for c in cfg.poi.enabled() if c in TIER_CATEGORIES[tier]]
    with ThreadPoolExecutor(max_workers=2) as pool:
        area_job = pool.submit(fetch_area, lat, lon, radius, cache_dir, tier == "city", stats)
        poi_job = pool.submit(fetch_pois, lat, lon, categories, cache_dir, radius, stats)
        area = area_job.result()
    try:
        pois_raw = poi_job.result()
    except OverpassError as exc:
        logger.warning("POI fetch failed: %s", exc)
        pois_raw = {"elements": []}
        warnings.append("poi_fetch_failed")
    scene = assemble_scene(lat, lon, radius, area, pois_raw, categories, tier=tier, street=lines)
    if tier == "street":
        scene["focus"]["name"] = name or ""
    scene["warnings"] = warnings
    scene["timing_ms"] = round((time.perf_counter() - t0) * 1000)
    scene["cached"] = all(stats)
    return scene
