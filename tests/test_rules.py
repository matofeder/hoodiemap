import pytest

from scene_builder import area_layer, building_facts, building_height, classify_building, road_kind


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


@pytest.mark.parametrize("tags", [{"height": "inf"}, {"height": "500"}, {"building:levels": "200"}])
def test_building_height_is_clamped(tags):
    assert building_height(tags, "apartment") == 150.0


def test_building_facts_keeps_only_what_osm_actually_says():
    assert building_facts({"building": "yes"}) == {}


def test_building_facts_full():
    tags = {"building": "church", "name": "Dóm sv. Alžbety", "addr:street": "Hlavná",
            "addr:housenumber": "1640/32", "building:levels": "3", "start_date": "1508",
            "heritage": "2", "amenity": "place_of_worship"}
    assert building_facts(tags) == {"name": "Dóm sv. Alžbety", "type": "place_of_worship",
                                    "address": "Hlavná 1640/32", "levels": 3, "year": "1508",
                                    "heritage": True}


@pytest.mark.parametrize("tags,expected", [
    ({"building": "apartments"}, "apartments"),
    ({"building": "yes", "shop": "supermarket"}, "supermarket"),
    ({"building": "yes", "tourism": "hotel"}, "hotel"),
    ({"building": "yes", "amenity": "school"}, "school"),
    ({"building": "garage"}, "garage"),
    ({"building": "yes"}, None),
])
def test_building_facts_type_prefers_what_is_inside(tags, expected):
    assert building_facts(tags).get("type") == expected


@pytest.mark.parametrize("tags,expected", [
    ({"addr:street": "Hlavná", "addr:housenumber": "32"}, "Hlavná 32"),
    ({"addr:place": "Viničné", "addr:housenumber": "12"}, "Viničné 12"),
    ({"addr:housenumber": "12"}, None),
    ({"addr:street": "Hlavná"}, None),
])
def test_building_facts_address(tags, expected):
    assert building_facts({"building": "yes", **tags}).get("address") == expected


@pytest.mark.parametrize("raw,expected", [
    ("1913", "1913"), ("2019-06-27", "2019"), ("mid C17", "17. stor."), ("C19", "19. stor."), ("~1900s", "1900"),
    ("unknown", None),
])
def test_building_facts_year(raw, expected):
    assert building_facts({"building": "yes", "start_date": raw}).get("year") == expected


@pytest.mark.parametrize("raw,expected", [("4", 4), ("4.5", None), ("0", None), ("abc", None), ("200", None)])
def test_building_facts_levels_only_plausible_integers(raw, expected):
    assert building_facts({"building": "yes", "building:levels": raw}).get("levels") == expected


def test_building_facts_historic_building_counts_as_heritage():
    assert building_facts({"building": "yes", "historic": "building"})["heritage"] is True
