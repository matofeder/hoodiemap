import pytest
from unittest.mock import patch, MagicMock
import networkx as nx
import geopandas as gpd
from shapely.geometry import Polygon, Point
from pyproj import CRS


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
        }
        mock_trees.return_value = [
            {"lat": lat + 0.001, "lon": lon + 0.001, "crown_d": 6.0, "height_m": 10.0}
        ]
        mock_pois.return_value = []
        result = build_scene(lat, lon, default_config)

    assert set(result.keys()) == {"center", "bbox_m", "roads", "buildings", "pois", "trees"}
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
        mock_geo.return_value = {k: None for k in ["building", "water", "forest", "park", "railway"]}
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
        mock_geo.return_value = {k: None for k in ["building", "water", "forest", "park", "railway"]}
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
