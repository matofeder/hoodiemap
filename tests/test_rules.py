import pytest

from scene_builder import area_layer, building_height, classify_building, road_kind


@pytest.mark.parametrize("tags,area,kind", [
    ({"building": "school"}, 800, "civic"),
    ({"building": "church"}, 300, "civic"),
    ({"building": "retail"}, 500, "commercial"),
    ({"building": "industrial"}, 900, "commercial"),
    ({"building": "garage"}, 20, "other"),
    ({"building": "shed"}, 8, "other"),
    ({"building": "house"}, 400, "house"),
    ({"building": "detached"}, 120, "house"),
    ({"building": "yes"}, 120, "house"),
    ({"building": "residential", "building:levels": "2"}, 180, "house"),
    ({"building": "yes", "building:levels": "3"}, 120, "apartment"),
    ({"building": "yes"}, 260, "apartment"),
    ({"building": "apartments"}, 100, "apartment"),
    ({"building": "YES"}, 100, "house"),
])
def test_classify_building(tags, area, kind):
    assert classify_building(tags, area) == kind


@pytest.mark.parametrize("tags,kind,height", [
    ({"height": "12 m"}, "apartment", 12.0),
    ({"height": "1"}, "other", 2.0),
    ({"building:levels": "4"}, "apartment", 12.0),
    ({"height": "abc", "building:levels": "2"}, "house", 6.0),
    ({}, "house", 6.0),
    ({}, "apartment", 12.0),
    ({}, "commercial", 8.0),
    ({}, "civic", 10.0),
    ({}, "other", 3.0),
])
def test_building_height(tags, kind, height):
    assert building_height(tags, kind) == height


@pytest.mark.parametrize("highway,kind", [
    ("primary", "main"), ("tertiary_link", "main"), ("residential", "street"),
    ("service", "street"), ("footway", "path"), ("steps", "path"),
    ("construction", None), ("proposed", None),
])
def test_road_kind(highway, kind):
    assert road_kind(highway) == kind


@pytest.mark.parametrize("tags,layer", [
    ({"leisure": "park"}, "park"), ({"leisure": "playground"}, "park"), ({"landuse": "grass"}, "park"),
    ({"natural": "water"}, "water"), ({"waterway": "riverbank"}, "water"),
    ({"landuse": "forest"}, "forest"), ({"natural": "wood"}, "forest"),
    ({"landuse": "residential"}, None),
])
def test_area_layer(tags, layer):
    assert area_layer(tags) == layer
