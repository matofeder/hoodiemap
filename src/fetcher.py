import hashlib
import os
import pickle
import time

import geopandas as gpd
import osmnx as ox
import overpy

from config import Config
from geo import BBox, POI, _diacritic_count, _strip_diacritics, compute_bearing, haversine_m

# ---------------------------------------------------------------------------
# POI category → OSM tag mapping
# ---------------------------------------------------------------------------

POI_TAGS: dict[str, str] = {
    "hospital":      "amenity=hospital",
    "grocery":       "shop=supermarket",
    "school":        "amenity=school",
    "pharmacy":      "amenity=pharmacy",
    "pub":           "amenity=pub",
    "bar":           "amenity=bar",
    "restaurant":    "amenity=restaurant",
    "public_office": "office=government",
}

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_path(key: str, cache_dir: str) -> str:
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    return os.path.join(cache_dir, f"{h}.pkl")


def _cache_load(key: str, cache_dir: str, use_cache: bool):
    if not use_cache:
        return None
    p = _cache_path(key, cache_dir)
    if os.path.exists(p):
        with open(p, "rb") as f:
            return pickle.load(f)
    return None


def _cache_save(key: str, obj, cache_dir: str, use_cache: bool) -> None:
    if not use_cache:
        return
    os.makedirs(cache_dir, exist_ok=True)
    with open(_cache_path(key, cache_dir), "wb") as f:
        pickle.dump(obj, f)


# ---------------------------------------------------------------------------
# Street network
# ---------------------------------------------------------------------------


def fetch_street_network(cfg: Config, center_lat: float, center_lon: float, radius_m: float):
    key = f"street_network:{center_lat}:{center_lon}:{radius_m}"
    cached = _cache_load(key, cfg.cache.dir, cfg.cache.enabled)
    if cached is not None:
        print("  (from cache)")
        return cached
    G = ox.graph_from_point(
        center_point=(center_lat, center_lon),
        dist=radius_m,
        network_type="drive",
        simplify=True,
    )
    _cache_save(key, G, cfg.cache.dir, cfg.cache.enabled)
    return G


# ---------------------------------------------------------------------------
# Geo layers
# ---------------------------------------------------------------------------

_GEO_LAYERS: dict[str, tuple[dict, list[str]]] = {
    "water":    ({"natural": ["water", "wetland"], "waterway": ["riverbank"]},
                 ["Polygon", "MultiPolygon"]),
    "forest":   ({"landuse": ["forest"], "natural": ["wood"]},
                 ["Polygon", "MultiPolygon"]),
    "park":        ({"leisure": ["park", "garden"], "landuse": ["grass", "meadow", "orchard"]},
                    ["Polygon", "MultiPolygon"]),
    "residential": ({"landuse": ["residential"]},
                    ["Polygon", "MultiPolygon"]),
    "building": ({"building": True},
                 ["Polygon", "MultiPolygon"]),
    "railway":  ({"railway": ["rail", "tram"]},
                 ["LineString", "MultiLineString"]),
}


def fetch_geo_layers(cfg: Config, bbox: BBox) -> dict[str, gpd.GeoDataFrame | None]:
    key = f"geo_layers:{bbox.north}:{bbox.south}:{bbox.east}:{bbox.west}"
    cached = _cache_load(key, cfg.cache.dir, cfg.cache.enabled)
    if cached is not None:
        print("  (from cache)")
        for name, gdf in cached.items():
            status = f"{len(gdf):,} features" if gdf is not None else "empty"
            print(f"  [{name:10s}] {status}")
        return cached

    osmnx_bbox = (bbox.north, bbox.south, bbox.east, bbox.west)
    result: dict[str, gpd.GeoDataFrame | None] = {}
    for name, (tags, geom_types) in _GEO_LAYERS.items():
        try:
            gdf = ox.features_from_bbox(bbox=osmnx_bbox, tags=tags)
            gdf = gdf[gdf.geometry.geom_type.isin(geom_types)]
            result[name] = gdf if not gdf.empty else None
        except Exception:
            result[name] = None
        status = f"{len(result[name]):,} features" if result[name] is not None else "empty"
        print(f"  [{name:10s}] {status}")

    _cache_save(key, result, cfg.cache.dir, cfg.cache.enabled)
    return result


# ---------------------------------------------------------------------------
# POIs
# ---------------------------------------------------------------------------

_OVERPASS_ENDPOINTS: list[str] = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def _build_overpass_query(bbox: BBox, osm_tag: str) -> str:
    key, value = osm_tag.split("=", 1)
    bb = f"{bbox.south},{bbox.west},{bbox.north},{bbox.east}"
    return (
        f'[out:json][timeout:30];\n'
        f'(\n'
        f'  node["{key}"="{value}"]({bb});\n'
        f'  way["{key}"="{value}"]({bb});\n'
        f'  relation["{key}"="{value}"]({bb});\n'
        f');\n'
        f'out center;\n'
    )


def _extract_raw_points(result: overpy.Result, category: str) -> list[tuple[float, float, str]]:
    fallback = category.replace("_", " ").title()
    raw: list[tuple[float, float, str]] = []
    for node in result.nodes:
        raw.append((float(node.lat), float(node.lon), node.tags.get("name", "").strip() or fallback))
    for way in result.ways:
        if way.center_lat is not None:
            raw.append((float(way.center_lat), float(way.center_lon), way.tags.get("name", "").strip() or fallback))
    for rel in result.relations:
        if rel.center_lat is not None:
            raw.append((float(rel.center_lat), float(rel.center_lon), rel.tags.get("name", "").strip() or fallback))
    return raw


def fetch_pois(
    cfg: Config,
    bbox: BBox,
    center_lat: float,
    center_lon: float,
    categories: list[str],
) -> list[POI]:
    max_per = cfg.poi.max_per_category
    key = f"pois:{bbox.north}:{bbox.south}:{bbox.east}:{bbox.west}:{','.join(sorted(categories))}:{max_per}"
    cached = _cache_load(key, cfg.cache.dir, cfg.cache.enabled)
    if cached is not None:
        print("  (from cache)")
        return cached

    pois: list[POI] = []
    for category in categories:
        query = _build_overpass_query(bbox, POI_TAGS[category])
        result = None
        for endpoint in _OVERPASS_ENDPOINTS:
            try:
                result = overpy.Overpass(url=endpoint).query(query)
                break
            except Exception as e:
                print(f"  [warn] {endpoint} failed ({e}), trying next …")
                time.sleep(1)
        if result is None:
            print(f"  [skip] '{category}' — all endpoints failed")
            continue

        ranked = sorted(
            _extract_raw_points(result, category),
            key=lambda p: haversine_m(center_lat, center_lon, p[0], p[1]),
        )
        best: dict[str, tuple[float, float, str]] = {}
        for lat, lon, name in ranked:
            nkey = _strip_diacritics(" ".join(name.split()))
            if nkey not in best:
                best[nkey] = (lat, lon, name)
            else:
                existing = best[nkey]
                if _diacritic_count(name) > _diacritic_count(existing[2]):
                    best[nkey] = (existing[0], existing[1], name)

        deduped = sorted(best.values(), key=lambda p: haversine_m(center_lat, center_lon, p[0], p[1]))
        for lat, lon, name in deduped[:max_per]:
            pois.append(POI(
                name=name, lat=lat, lon=lon, category=category,
                distance_m=round(haversine_m(center_lat, center_lon, lat, lon)),
                bearing_deg=round(compute_bearing(center_lat, center_lon, lat, lon), 1),
            ))

    _cache_save(key, pois, cfg.cache.dir, cfg.cache.enabled)
    return pois


# ---------------------------------------------------------------------------
# Trees
# ---------------------------------------------------------------------------


def _safe_float(val, default: float) -> float:
    try:
        if val is None:
            return default
        return max(1.0, float(str(val).replace("m", "").strip()))
    except (ValueError, TypeError):
        return default


def fetch_trees(cfg: Config, bbox: BBox) -> list[dict]:
    key = f"trees:{bbox.north:.5f}:{bbox.south:.5f}:{bbox.east:.5f}:{bbox.west:.5f}"
    cached = _cache_load(key, cfg.cache.dir, cfg.cache.enabled)
    if cached is not None:
        print(f"  (trees from cache: {len(cached)})")
        return cached

    bb = f"{bbox.south},{bbox.west},{bbox.north},{bbox.east}"
    query = (
        f'[out:json][timeout:30];\n'
        f'(\n'
        f'  node["natural"="tree"]({bb});\n'
        f'  way["natural"="tree_row"]({bb});\n'
        f');\n'
        f'out center;\n'
    )
    trees: list[dict] = []
    for endpoint in _OVERPASS_ENDPOINTS:
        try:
            result = overpy.Overpass(url=endpoint).query(query)
            for node in result.nodes:
                trees.append({
                    "lat":      float(node.lat),
                    "lon":      float(node.lon),
                    "crown_d":  _safe_float(node.tags.get("diameter_crown"), 6.0),
                    "height_m": _safe_float(node.tags.get("height"), 10.0),
                })
            for way in result.ways:
                if way.center_lat is not None:
                    trees.append({
                        "lat":      float(way.center_lat),
                        "lon":      float(way.center_lon),
                        "crown_d":  7.0,
                        "height_m": 12.0,
                    })
            break
        except Exception as e:
            print(f"  [warn] trees {endpoint}: {e}")
            time.sleep(1)

    _cache_save(key, trees, cfg.cache.dir, cfg.cache.enabled)
    print(f"  trees fetched: {len(trees)}")
    return trees
