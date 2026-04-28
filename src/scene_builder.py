import geopandas as gpd
import osmnx as ox
from pyproj import CRS
from shapely.geometry import Point

from config import Config
from fetcher import fetch_geo_layers, fetch_pois, fetch_street_network, fetch_trees
from geo import compute_bbox
from styles import BUILDING_TYPE_HEIGHTS, BUILDING_HEIGHTS_DEFAULT_M


def _utm_crs_for(lat: float, lon: float) -> CRS:
    zone = int((lon + 180) / 6) + 1
    return CRS.from_dict({"proj": "utm", "zone": zone, "south": lat < 0})


def _center_utm(lat: float, lon: float, crs: CRS) -> tuple[float, float]:
    gdf = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326").to_crs(crs)
    return float(gdf.geometry.x.iloc[0]), float(gdf.geometry.y.iloc[0])


def _latlon_to_local(lat: float, lon: float, cx: float, cy: float, crs: CRS) -> tuple[float, float]:
    gdf = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326").to_crs(crs)
    return round(float(gdf.geometry.x.iloc[0]) - cx, 2), round(float(gdf.geometry.y.iloc[0]) - cy, 2)


def _building_height(row) -> float:
    raw = row.get("height") if hasattr(row, "get") else getattr(row, "height", None)
    if raw is not None:
        try:
            return max(2.0, float(str(raw).replace("m", "").strip()))
        except (ValueError, TypeError):
            pass
    levels = row.get("building:levels") if hasattr(row, "get") else getattr(row, "building:levels", None)
    if levels is not None:
        try:
            return max(1, int(float(str(levels)))) * 3.0
        except (ValueError, TypeError):
            pass
    btype = str(row.get("building", "yes") if hasattr(row, "get") else getattr(row, "building", "yes")).lower()
    return BUILDING_TYPE_HEIGHTS.get(btype, BUILDING_HEIGHTS_DEFAULT_M)


def build_scene(lat: float, lon: float, cfg: Config) -> dict:
    utm_crs = _utm_crs_for(lat, lon)
    cx, cy = _center_utm(lat, lon, utm_crs)

    display_bbox = compute_bbox(lat, lon, cfg.radii.display_meters)

    G_raw = fetch_street_network(cfg, lat, lon, cfg.radii.fetch_meters)
    geo_layers = fetch_geo_layers(cfg, display_bbox)
    trees_raw = fetch_trees(cfg, display_bbox)

    show = cfg.poi.show
    active_cats = [cat for cat, flag in {
        "hospital": show.hospital, "grocery": show.grocery,
        "school": show.school, "pharmacy": show.pharmacy,
        "pub": show.pub, "bar": show.bar,
        "restaurant": show.restaurant, "public_office": show.public_office,
    }.items() if flag]
    pois_raw = fetch_pois(cfg, display_bbox, lat, lon, active_cats)

    G_proj = ox.project_graph(G_raw, to_crs=utm_crs)

    roads = []
    for u, v, data in G_proj.edges(data=True):
        highway = data.get("highway", "residential")
        if isinstance(highway, list):
            highway = highway[0]
        if "geometry" in data:
            points = [[round(x - cx, 2), round(y - cy, 2)] for x, y in data["geometry"].coords]
        else:
            u_n, v_n = G_proj.nodes[u], G_proj.nodes[v]
            points = [
                [round(u_n["x"] - cx, 2), round(u_n["y"] - cy, 2)],
                [round(v_n["x"] - cx, 2), round(v_n["y"] - cy, 2)],
            ]
        roads.append({"points": points, "type": str(highway)})

    buildings = []
    building_gdf = geo_layers.get("building")
    if building_gdf is not None:
        building_proj = building_gdf.to_crs(utm_crs)
        for _, row in building_proj.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            try:
                poly = geom if geom.geom_type == "Polygon" else geom.geoms[0]
                footprint = [[round(x - cx, 2), round(y - cy, 2)] for x, y in poly.exterior.coords]
                buildings.append({
                    "footprint": footprint,
                    "height": _building_height(row),
                    "type": str(row.get("building", "yes")).lower(),
                })
            except Exception:
                continue

    pois = []
    for poi in pois_raw:
        x, y = _latlon_to_local(poi.lat, poi.lon, cx, cy, utm_crs)
        pois.append({
            "x": x, "y": y,
            "lat": poi.lat, "lon": poi.lon,
            "category": poi.category,
            "name": poi.name,
            "distance_m": poi.distance_m,
        })

    trees = []
    for tree in trees_raw:
        x, y = _latlon_to_local(tree["lat"], tree["lon"], cx, cy, utm_crs)
        trees.append({
            "x": x, "y": y,
            "radius": round(tree["crown_d"] / 2, 2),
            "height": round(tree["height_m"], 2),
        })

    return {
        "center": {"lat": lat, "lon": lon},
        "bbox_m": cfg.radii.display_meters,
        "roads": roads,
        "buildings": buildings,
        "pois": pois,
        "trees": trees,
    }
