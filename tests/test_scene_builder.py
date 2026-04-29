import pytest
from unittest.mock import patch, MagicMock
import networkx as nx
import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon, Point
from pyproj import CRS
from geo import POI


def _make_mock_graph(cx_utm, cy_utm):
    """Minimal osmnx-style projected graph with two nodes and one edge."""
    G = nx.MultiDiGraph()
    G.graph["crs"] = CRS.from_epsg(32633)
    G.add_node(1, x=cx_utm + 50, y=cy_utm + 10)
    G.add_node(2, x=cx_utm + 150, y=cy_utm + 10)
    G.add_edge(1, 2, 0, highway="residential")
    return G


def _make_mock_building_gdf(cx_utm, cy_utm):
    poly = Polygon([
        (cx_utm + 20, cy_utm + 20),
        (cx_utm + 40, cy_utm + 20),
        (cx_utm + 40, cy_utm + 40),
        (cx_utm + 20, cy_utm + 40),
    ])
    gdf = gpd.GeoDataFrame(
        [{"building": "residential", "height": "8", "geometry": poly}],
        crs=CRS.from_epsg(32633),
    )
    return gdf


def _get_utm_center(lat, lon):
    from pyproj import CRS
    utm_crs = CRS.from_epsg(32633)
    center_gdf = gpd.GeoDataFrame(
        geometry=[Point(lon, lat)], crs="EPSG:4326"
    ).to_crs(utm_crs)
    return float(center_gdf.geometry.x.iloc[0]), float(center_gdf.geometry.y.iloc[0])


def test_build_scene_returns_required_keys(default_config):
    from scene_builder import build_scene
    lat, lon = 48.28646, 17.27221
    cx, cy = _get_utm_center(lat, lon)

    with patch("scene_builder.fetch_street_network") as mock_net, \
         patch("scene_builder.fetch_geo_layers") as mock_geo, \
         patch("scene_builder.fetch_trees") as mock_trees, \
         patch("scene_builder.fetch_pois") as mock_pois, \
         patch("scene_builder.ox.project_graph") as mock_proj:

        mock_net.return_value = MagicMock()
        mock_proj.return_value = _make_mock_graph(cx, cy)
        mock_geo.return_value = {
            "building": _make_mock_building_gdf(cx, cy),
            "water": None, "forest": None, "park": None, "railway": None,
            "residential": None,
        }
        mock_trees.return_value = [
            {"lat": lat + 0.001, "lon": lon + 0.001, "crown_d": 6.0, "height_m": 10.0}
        ]
        mock_pois.return_value = []
        result = build_scene(lat, lon, default_config)

    assert set(result.keys()) == {"center", "bbox_m", "display_radius_m", "roads", "buildings", "pois", "outer_pois", "trees", "geo_layers"}
    assert result["display_radius_m"] == 600
    assert isinstance(result["outer_pois"], list)
    assert result["center"] == {"lat": lat, "lon": lon}
    assert result["bbox_m"] == 600


def test_roads_have_points_and_type(default_config):
    from scene_builder import build_scene
    lat, lon = 48.28646, 17.27221
    cx, cy = _get_utm_center(lat, lon)

    with patch("scene_builder.fetch_street_network") as mock_net, \
         patch("scene_builder.fetch_geo_layers") as mock_geo, \
         patch("scene_builder.fetch_trees") as mock_trees, \
         patch("scene_builder.fetch_pois") as mock_pois, \
         patch("scene_builder.ox.project_graph") as mock_proj:

        mock_net.return_value = MagicMock()
        mock_proj.return_value = _make_mock_graph(cx, cy)
        mock_geo.return_value = {k: None for k in ["building", "water", "forest", "park", "railway", "residential"]}
        mock_trees.return_value = []
        mock_pois.return_value = []
        result = build_scene(lat, lon, default_config)

    assert len(result["roads"]) >= 1
    road = result["roads"][0]
    assert "points" in road and "type" in road
    assert isinstance(road["points"], list)
    assert all(len(p) == 2 for p in road["points"])


def test_buildings_projected_near_center(default_config):
    from scene_builder import build_scene
    lat, lon = 48.28646, 17.27221
    cx, cy = _get_utm_center(lat, lon)

    with patch("scene_builder.fetch_street_network") as mock_net, \
         patch("scene_builder.fetch_geo_layers") as mock_geo, \
         patch("scene_builder.fetch_trees") as mock_trees, \
         patch("scene_builder.fetch_pois") as mock_pois, \
         patch("scene_builder.ox.project_graph") as mock_proj:

        mock_net.return_value = MagicMock()
        mock_proj.return_value = _make_mock_graph(cx, cy)
        mock_geo.return_value = {
            "building": _make_mock_building_gdf(cx, cy),
            "water": None, "forest": None, "park": None, "railway": None,
            "residential": None,
        }
        mock_trees.return_value = []
        mock_pois.return_value = []
        result = build_scene(lat, lon, default_config)

    assert len(result["buildings"]) == 1
    b = result["buildings"][0]
    assert b["height"] == 8.0
    assert b["type"] == "residential"
    for x, y in b["footprint"]:
        assert abs(x) < 700 and abs(y) < 700


def test_trees_projected(default_config):
    from scene_builder import build_scene
    lat, lon = 48.28646, 17.27221
    cx, cy = _get_utm_center(lat, lon)

    with patch("scene_builder.fetch_street_network") as mock_net, \
         patch("scene_builder.fetch_geo_layers") as mock_geo, \
         patch("scene_builder.fetch_trees") as mock_trees, \
         patch("scene_builder.fetch_pois") as mock_pois, \
         patch("scene_builder.ox.project_graph") as mock_proj:

        mock_net.return_value = MagicMock()
        mock_proj.return_value = _make_mock_graph(cx, cy)
        mock_geo.return_value = {k: None for k in ["building", "water", "forest", "park", "railway", "residential"]}
        mock_trees.return_value = [
            {"lat": lat + 0.001, "lon": lon + 0.001, "crown_d": 6.0, "height_m": 10.0}
        ]
        mock_pois.return_value = []
        result = build_scene(lat, lon, default_config)

    assert len(result["trees"]) == 1
    t = result["trees"][0]
    assert "x" in t and "y" in t and "radius" in t and "height" in t
    assert t["radius"] == 3.0
    assert t["height"] == 10.0


def test_building_height_from_levels():
    from scene_builder import _building_height
    row = {"building": "residential", "building:levels": "4", "height": None}
    assert _building_height(row) == 12.0  # 4 * 3.0


def test_building_height_from_type_default():
    from scene_builder import _building_height
    row = {"building": "commercial", "building:levels": None, "height": None}
    # BUILDING_TYPE_HEIGHTS["commercial"] from styles.py
    from styles import BUILDING_TYPE_HEIGHTS
    expected = BUILDING_TYPE_HEIGHTS.get("commercial", 8.0)
    assert _building_height(row) == expected


def _make_poi(lat, lon, name, category, distance_m):
    return POI(name=name, lat=lat, lon=lon, category=category, distance_m=distance_m, bearing_deg=0.0)


def _make_mock_geo_layer_gdf(cx_utm, cy_utm, offset=100):
    """A simple square polygon GDF in UTM CRS, offset from center."""
    poly = Polygon([
        (cx_utm + offset,      cy_utm + offset),
        (cx_utm + offset + 50, cy_utm + offset),
        (cx_utm + offset + 50, cy_utm + offset + 50),
        (cx_utm + offset,      cy_utm + offset + 50),
    ])
    return gpd.GeoDataFrame([{"geometry": poly}], crs=CRS.from_epsg(32633))


def test_geo_layers_in_scene_output(default_config):
    from scene_builder import build_scene
    lat, lon = 48.28646, 17.27221
    cx, cy = _get_utm_center(lat, lon)

    with patch("scene_builder.fetch_street_network") as mock_net, \
         patch("scene_builder.fetch_geo_layers") as mock_geo, \
         patch("scene_builder.fetch_trees") as mock_trees, \
         patch("scene_builder.fetch_pois") as mock_pois, \
         patch("scene_builder.ox.project_graph") as mock_proj:

        mock_net.return_value = MagicMock()
        mock_proj.return_value = _make_mock_graph(cx, cy)
        mock_geo.return_value = {
            "building": None,
            "water":  _make_mock_geo_layer_gdf(cx, cy, offset=100),
            "forest": _make_mock_geo_layer_gdf(cx, cy, offset=200),
            "park":   None,
            "railway": None,
            "residential": None,
        }
        mock_trees.return_value = []
        mock_pois.return_value = []
        result = build_scene(lat, lon, default_config)

    gl = result["geo_layers"]
    assert set(gl.keys()) == {"water", "forest", "park", "residential"}

    # water has one polygon ring
    assert len(gl["water"]) == 1
    ring = gl["water"][0]
    assert len(ring) >= 4  # 4 corners + closing coord
    for coord in ring:
        assert len(coord) == 2
        assert abs(coord[0]) < 1000 and abs(coord[1]) < 1000

    # forest also has one ring
    assert len(gl["forest"]) == 1

    # park was None → empty list
    assert gl["park"] == []


def test_geo_layers_multipolygon(default_config):
    """MultiPolygon geometries are split into individual rings."""
    from scene_builder import build_scene
    lat, lon = 48.28646, 17.27221
    cx, cy = _get_utm_center(lat, lon)

    poly1 = Polygon([(cx+10, cy+10), (cx+30, cy+10), (cx+30, cy+30), (cx+10, cy+30)])
    poly2 = Polygon([(cx+50, cy+50), (cx+80, cy+50), (cx+80, cy+80), (cx+50, cy+80)])
    multi = MultiPolygon([poly1, poly2])
    gdf = gpd.GeoDataFrame([{"geometry": multi}], crs=CRS.from_epsg(32633))

    with patch("scene_builder.fetch_street_network") as mock_net, \
         patch("scene_builder.fetch_geo_layers") as mock_geo, \
         patch("scene_builder.fetch_trees") as mock_trees, \
         patch("scene_builder.fetch_pois") as mock_pois, \
         patch("scene_builder.ox.project_graph") as mock_proj:

        mock_net.return_value = MagicMock()
        mock_proj.return_value = _make_mock_graph(cx, cy)
        mock_geo.return_value = {
            "building": None,
            "water": gdf,
            "forest": None,
            "park": None,
            "railway": None,
            "residential": None,
        }
        mock_trees.return_value = []
        mock_pois.return_value = []
        result = build_scene(lat, lon, default_config)

    # One MultiPolygon with two parts → two rings in output
    assert len(result["geo_layers"]["water"]) == 2


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
    assert result["display_radius_m"] == 600


def test_outer_pois_classified_and_have_bearing(default_config):
    from scene_builder import build_scene
    lat, lon = 48.28646, 17.27221
    cx, cy = _get_utm_center(lat, lon)
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
    assert bearing < 1.0 or bearing > 359.0
