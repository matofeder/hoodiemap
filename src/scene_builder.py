"""Turn raw Overpass JSON into the compact scene consumed by the frontend."""
import logging

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import polygonize

from config import Config
from geo import compute_bearing, haversine_m, to_local
from osm import OverpassError, categorize_poi, fetch_area, fetch_pois

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

ROAD_KINDS: dict[str, str] = {
    **dict.fromkeys(["primary", "secondary", "tertiary", "primary_link", "secondary_link", "tertiary_link"], "main"),
    **dict.fromkeys(["residential", "unclassified", "living_street", "service", "road"], "street"),
    **dict.fromkeys(["footway", "path", "cycleway", "pedestrian", "steps", "track"], "path"),
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
    if height is not None and height > 0:
        return max(2.0, height)
    levels = _num(tags.get("building:levels"))
    if levels is not None and levels > 0:
        return levels * METERS_PER_LEVEL
    return DEFAULT_HEIGHT[kind]


def road_kind(highway) -> str | None:
    return ROAD_KINDS.get(str(highway))


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
    return None


def split_pois(lat: float, lon: float, radius_m: float, pois_raw: dict,
               categories: list[str]) -> tuple[list[dict], list[dict]]:
    wanted = set(categories)
    best: dict[str, tuple[float, dict, tuple[float, float]]] = {}
    for el in pois_raw.get("elements", []):
        tags = el.get("tags") or {}
        cat = categorize_poi(tags)
        pos = _element_latlon(el)
        if cat not in wanted or pos is None:
            continue
        d = haversine_m(lat, lon, *pos)
        if cat not in best or d < best[cat][0]:
            best[cat] = (d, tags, pos)

    near, far = [], []
    limit = radius_m - NEAR_INSET_M
    for cat, (d, tags, (plat, plon)) in sorted(best.items(), key=lambda kv: kv[1][0]):
        entry = {"category": cat, "name": tags.get("name", ""), "distance_m": round(d)}
        x, y = to_local(plat, plon, lat, lon)
        if abs(x) <= limit and abs(y) <= limit:
            near.append({**entry, "x": _r(x), "y": _r(y)})
        else:
            far.append({**entry, "bearing_deg": round(compute_bearing(lat, lon, plat, plon), 1)})
    return near, far


def assemble_scene(lat: float, lon: float, radius_m: float, area: dict, pois_raw: dict,
                   categories: list[str]) -> dict:
    square = box(-radius_m, -radius_m, radius_m, radius_m)
    buildings, roads, trees = [], [], []
    areas: dict[str, list] = {"park": [], "water": [], "forest": []}

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

    near, far = split_pois(lat, lon, radius_m, pois_raw, categories)
    return {
        "center": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "buildings": buildings,
        "property": {"building_index": find_property(buildings)},
        "roads": roads,
        "areas": areas,
        "trees": trees,
        "near_pois": near,
        "far_pois": far,
    }


def build_scene(lat: float, lon: float, cfg: Config) -> dict:
    cache_dir = cfg.cache.dir if cfg.cache.enabled else None
    radius = cfg.radii.display_meters
    categories = cfg.poi.enabled()
    area = fetch_area(lat, lon, radius, cache_dir)
    warnings = []
    try:
        pois_raw = fetch_pois(lat, lon, categories, cache_dir)
    except OverpassError as exc:
        logger.warning("POI fetch failed: %s", exc)
        pois_raw = {"elements": []}
        warnings.append("poi_fetch_failed")
    scene = assemble_scene(lat, lon, radius, area, pois_raw, categories)
    scene["warnings"] = warnings
    return scene
