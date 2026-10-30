import pytest

import regions


@pytest.mark.parametrize("lat,lon,zuj,okres,kraj", [
    (48.28646, 17.27221, "508179", "SK0107", "SK010"),   # Pezinok, Záhradná
    (48.27150, 17.30173, "508306", "SK0107", "SK010"),   # Viničné
    (48.14507, 17.11214, "528595", "SK0101", "SK010"),   # Bratislava-Staré Mesto, Nám. SNP
    (48.71640, 21.26110, None, None, "SK042"),           # Košice: the city has boroughs (checked below)
])
def test_locate_finds_the_official_codes(lat, lon, zuj, okres, kraj):
    loc = regions.locate(lat, lon)
    assert loc["kraj"]["code"] == kraj
    if okres:
        assert loc["okres"]["code"] == okres and loc["zuj"]["code"] == zuj


def test_kosice_centre_is_a_borough_with_its_census_code():
    loc = regions.locate(48.71640, 21.26110)
    assert loc["okres"]["code"].startswith("SK042") and loc["zuj"]["code"].isdigit()


def test_outside_slovakia_has_no_region():
    assert regions.locate(48.2082, 16.3738) == {"kraj": None, "okres": None, "zuj": None}  # Vienna


def test_percentile_rank():
    vals = [10, 20, 30, 40, 50]
    assert regions.percentile(50, vals, "higher") == 100 and regions.percentile(10, vals, "higher") == 0
    assert regions.percentile(30, vals, "higher") == 50
    assert regions.percentile(10, vals, "lower") == 100
    assert regions.percentile(20, [10, 20, 20, 30], "higher") == pytest.approx(100 * 1.5 / 3)  # ties share the middle


def test_indicators_carry_value_rank_and_source():
    loc = regions.locate(48.28646, 17.27221)
    wage = regions.indicator("wage", loc)
    assert wage["region"] == "okres Pezinok" and wage["unit"] == "€" and wage["n_regions"] == 79
    assert 0 <= wage["sub_score"] <= 100 and "np3110rr" in wage["source"]
    crime = regions.indicator("crime", loc)
    assert crime["level"] == "kraj" and crime["n_regions"] == 8 and crime["formula"]
    ppd = regions.indicator("persons_per_dwelling", loc)
    assert ppd["region"] == "Pezinok" and ppd["period"] == "2021"


def test_statistics_cover_every_region_of_their_level():
    st = regions.stats()["indicators"]
    assert len(st["wage"]["values"]) == 79 and len(st["unemployment"]["values"]) == 79
    assert len(st["crime"]["values"]) == 8 and len(st["persons_per_dwelling"]["values"]) > 2900
