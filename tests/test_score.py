import json
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

import score
import score_method as M
from geo import from_local
from osm import OverpassError

LAT, LON = 48.28, 17.27
FIXTURES = Path(__file__).parent.parent / "fixtures"
_ids = iter(range(1, 10**6))


def node(x, y, **tags):
    lat, lon = from_local(x, y, LAT, LON)
    return {"type": "node", "id": next(_ids), "lat": lat, "lon": lon, "tags": tags}


def _pts(coords):
    return [dict(zip(("lat", "lon"), from_local(x, y, LAT, LON))) for x, y in coords]


def square(cx, cy, side, **tags):
    h = side / 2
    ring = [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h), (cx - h, cy - h)]
    return {"type": "way", "id": next(_ids), "tags": tags, "geometry": _pts(ring)}


def line(coords, **tags):
    return {"type": "way", "id": next(_ids), "tags": tags, "geometry": _pts(coords)}


def compute(*elements):
    return score.compute({"elements": list(elements)}, LAT, LON)["scores"]


def everything_at(d):
    """One of every walk category at distance d (east), as many as each category counts."""
    els = []
    for i in range(10):
        els.append(node(d, i, amenity="restaurant"))
    for i in range(5):
        els.append(node(d, 20 + i, shop="clothes"))
    els += [node(d, 30, shop="supermarket"), node(d, 31, amenity="cafe"), node(d, 32, amenity="cafe"),
            node(d, 33, amenity="bank"), node(d, 34, leisure="park", name="Park"), node(d, 35, amenity="school", name="ZŠ"),
            node(d, 36, amenity="pharmacy"), node(d, 37, amenity="library")]
    return els


def test_decay_follows_the_breakpoints():
    assert score.decay(0, M.WALK_DECAY) == 1.0
    assert score.decay(400, M.WALK_DECAY) == 1.0
    assert score.decay(600, M.WALK_DECAY) == pytest.approx(0.86)
    assert score.decay(2400, M.WALK_DECAY) == 0.0
    assert score.decay(5000, M.WALK_DECAY) == 0.0


def test_place_categories():
    assert score.place_categories({"shop": "supermarket"}) == ["grocery"]
    assert score.place_categories({"shop": "vacant"}) == []
    assert score.place_categories({"amenity": "cafe"}) == ["cafe"]
    assert score.place_categories({"amenity": "school", "name": "Základná škola Kupeckého"}) == ["school", "primary_school"]
    assert score.place_categories({"amenity": "school", "name": "ZŠ Fándlyho 11"}) == ["school", "primary_school"]
    assert score.place_categories({"amenity": "school", "name": "Základná umelecká škola"}) == ["school"]
    assert score.place_categories({"amenity": "school", "name": "Gymnázium"}) == ["school"]
    assert score.place_categories({"leisure": "park"}) == []  # an unnamed lawn tagged park
    assert score.place_categories({"leisure": "park", "name": "Predpark"}) == ["park"]
    assert score.place_categories({"highway": "bus_stop"}) == ["transit"]


def test_walk_full_near_nothing_far():
    assert compute(*everything_at(100))["walk"]["score"] == 100
    far = compute(*everything_at(1200))["walk"]
    assert far["score"] == 20  # 1 200 m straight = 1 560 m walking: between the 1 200 and 1 600 m breakpoints
    empty = compute()["walk"]
    assert empty["score"] == 0 and empty["band"] == "Takmer všetko autom"
    assert "Potraviny" in empty["missing"]


def test_walk_fact_reports_the_nearest_and_a_count():
    facts = compute(*everything_at(100))["walk"]["facts"]
    food = next(f for f in facts if f["label"] == "Reštaurácie")
    assert food["distance_m"] == 100 and food["minutes"] == 2 and food["count_1km"] == 10


def test_green_follows_who_and_3_30_300():
    near = compute(square(150, 0, 100, leisure="park", name="Park"))["green"]  # 1 ha, edge 100 m away
    assert near["facts"][0]["distance_m"] == 100 and near["facts"][0]["area_ha"] == 1.0
    small = compute(square(150, 0, 60, leisure="park"))["green"]               # 0.36 ha: below WHO size
    assert small["missing"] and small["score"] < near["score"]
    forest = compute(square(0, 0, 500, landuse="forest"))["green"]              # 25 ha around the point: ANGSt 20 ha
    assert forest["score"] == 100 and forest["band"] == "Zeleň za rohom"
    private = compute(square(150, 0, 100, leisure="park", access="private"))["green"]
    assert private["missing"]


def test_quiet_penalties_by_distance_and_nightlife():
    assert compute()["quiet"]["score"] == 100
    road = compute(line([(-500, 40), (500, 40)], highway="primary"))["quiet"]
    assert road["score"] == 70 and road["facts"][0]["distance_m"] == 40
    motorway = compute(line([(-500, 150), (500, 150)], highway="motorway"))["quiet"]
    assert motorway["score"] == 70
    yard = compute(line([(-500, 20), (500, 20)], railway="rail", service="yard"))["quiet"]
    assert yard["score"] == 100
    bars = compute(*[node(50, i, amenity="nightclub") for i in range(5)])["quiet"]
    assert bars["score"] == 100 - M.NIGHTLIFE_MAX


def test_bands():
    assert score.band("walk", 90) == "Všetko vybavíte pešo"
    assert score.band("walk", 89) == "Väčšinu vybavíte pešo"
    assert score.band("quiet", 0) == "Rušné"


def test_query_fetches_places_and_shapes():
    q = score.build_score_query(LAT, LON)
    assert q.count("out center tags;") == 1 and q.count("out geom;") == 1
    assert '["shop"]' in q and '"landuse"~"^(forest' in q and 'railway"~"^(rail|light_rail|tram)' in q


@pytest.mark.skipif(not (FIXTURES / "score-pezinok-centrum.json").exists(), reason="no fixture")
def test_pezinok_centre_from_real_osm():
    osm = json.loads((FIXTURES / "score-pezinok-centrum.json").read_text(encoding="utf-8"))
    s = score.compute(osm, osm["center"]["lat"], osm["center"]["lon"])["scores"]
    assert s["walk"]["score"] >= 90
    assert any(f["name"] == "Zámocký Park" for f in s["green"]["facts"])
    osm_r = score.compute(osm, osm["center"]["lat"], osm["center"]["lon"])
    fam = next(a for a in osm_r["index"]["areas"] if a["id"] == "family")
    zs = next(r for r in fam["breakdown"] if r["key"] == "primary_school")
    assert zs["sub_score"] < 100  # the nearest ZŠ (Fándlyho) is ~1.2 km on foot; the gymnázium does not count


@pytest.mark.skipif(not (FIXTURES / "score-vinicne.json").exists(), reason="no fixture")
def test_a_village_walks_worse_than_the_town_centre():
    def walk(name):
        osm = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        return score.compute(osm, osm["center"]["lat"], osm["center"]["lon"])["scores"]["walk"]["score"]
    assert walk("score-vinicne.json") < walk("score-pezinok-centrum.json")


async def _get(url):
    from api import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(url)


async def test_api_scores_the_nearest_fixture_offline():
    r = await _get(f"/api/score?lat={48.2865}&lon={17.2722}&fixture=true")
    assert r.status_code == 200
    body = r.json()
    assert set(body["scores"]) == {"walk", "green", "family", "quiet"}
    assert body["method_version"] == M.VERSION


async def test_api_method_lists_sources():
    body = (await _get("/api/score/method")).json()
    assert "WHO" in body["green"]["source"] and "Walk Score" in body["walk"]["source"] and "Brewster" in body["walk"]["source"]


async def test_api_502_when_overpass_is_down():
    with patch("score_api._fetch", side_effect=OverpassError("down")):
        r = await _get("/api/score?lat=48.28&lon=17.27")
    assert r.status_code == 502


def test_trams_and_tertiary_roads_lower_quiet():
    tram = compute(line([(-500, 20), (500, 20)], railway="tram"))["quiet"]
    assert tram["score"] == 85 and tram["facts"][0]["label"] == "Električka"
    tertiary = compute(line([(-500, 50), (500, 50)], highway="tertiary"))["quiet"]
    assert tertiary["score"] == 96


@pytest.mark.parametrize("kind", ["walk", "green"])
def test_breakdown_adds_up_to_the_score(kind):
    els = everything_at(300) + [node(200, 0, amenity="kindergarten"), node(200, 10, leisure="playground"),
                                node(200, 20, amenity="doctors"), square(150, 0, 100, leisure="park", name="Park")]
    s = compute(*els)[kind]
    assert sum(r["weight"] for r in s["breakdown"]) == pytest.approx(1.0, abs=1e-3)
    assert sum(r["points"] for r in s["breakdown"]) == pytest.approx(s["score"], abs=0.6)
    assert all(0 <= r["sub_score"] <= 100 and r["fact"] for r in s["breakdown"])


def test_quiet_breakdown_lists_the_deductions_and_is_marked_provisional():
    s = compute(line([(-500, 40), (500, 40)], highway="primary"))["quiet"]
    assert s["breakdown"] == [{"key": "primary", "label": "Cesta I. triedy", "fact": "40 m", "points": -30}]
    assert s["status"] == "orientačné"


@pytest.fixture
def outside_sk(monkeypatch):
    """An address outside Slovakia: no regional statistics, so the territory areas have no data."""
    monkeypatch.setattr(score.regions, "locate", lambda lat, lon: {"kraj": None, "okres": None, "zuj": None})


def area(r, aid):
    return next(a for a in r["index"]["areas"] if a["id"] == aid)


def test_areas_are_the_address_and_the_territory(outside_sk):
    r = score.compute({"elements": everything_at(100)}, LAT, LON)
    ids = [a["id"] for a in r["index"]["areas"]]
    assert ids == ["walk", "family", "transport", "green", "quiet", "air",
                   "income", "jobs", "housing", "safety", "health", "education", "civic"]
    assert {a["group"] for a in r["index"]["areas"]} == {"okolie", "uzemie"}
    # outside Slovakia the territory statistics are missing, so no index
    assert r["index"]["missing"] == ["Príjem", "Práca", "Bývanie", "Bezpečnosť"] and r["index"]["index"] is None
    assert area(r, "income")["status"] == "chýbajú dáta"


def test_planned_areas_are_listed_but_not_counted(outside_sk):
    r = score.compute({"elements": everything_at(100)}, LAT, LON)
    for aid in ("air", "health", "education", "civic"):
        a = area(r, aid)
        assert a["score"] is None and not a["in_index"] and a["status"] == "pripravujeme" and a["planned"]
    assert r["index"]["index_areas"] == 9 and M.INDEX_AREAS == [
        "walk", "family", "transport", "green", "quiet", "income", "jobs", "housing", "safety"]


def test_every_area_names_its_norm():
    assert all(spec["norm"] for spec in M.AREAS.values())
    assert "WHO" in M.AREAS["green"]["norm"] and "Walk Score" in M.AREAS["walk"]["norm"]
    assert all("OECD" in M.AREAS[a]["norm"] for a in ("income", "jobs", "housing", "safety"))


def test_area_is_the_mean_of_its_indicators():
    r = score.compute({"elements": [node(100, 0, amenity="doctors")]}, LAT, LON)
    fam = area(r, "family")
    assert fam["score"] == 20  # doctor near (100); kindergarten, school, playground, pharmacy not found (0)
    assert [row["weight"] for row in fam["breakdown"]] == [0.2] * 5


def test_walk_and_green_areas_are_their_scores():
    r = score.compute({"elements": everything_at(100)}, LAT, LON)
    assert area(r, "walk")["score"] == r["scores"]["walk"]["score"]
    assert area(r, "green")["score"] == r["scores"]["green"]["score"]
    assert area(r, "quiet")["status"] == "orientačné"


def test_primary_school_counts_but_a_gymnazium_does_not():
    def fam(*els):
        return {row["key"]: row["sub_score"] for row in area(score.compute({"elements": list(els)}, LAT, LON), "family")["breakdown"]}
    assert fam(node(300, 0, amenity="school", name="Gymnázium"))["primary_school"] == 0
    assert fam(node(300, 0, amenity="school", name="ZŠ Hroznová"))["primary_school"] == 100


def test_profile_waits_for_every_index_area(outside_sk):
    fam = compute(*everything_at(100))["family"]
    assert fam["score"] is None and fam["missing"] == ["Príjem", "Práca", "Bývanie", "Bezpečnosť"]


def test_profile_with_equal_weights_equals_the_index():
    r = score.compute({"elements": everything_at(100)}, 48.28646, 17.27221)  # Pezinok
    fam = r["scores"]["family"]
    assert fam["weights_method"] == "equal" and fam["score"] == r["index"]["index"]
    assert sum(row["weight"] for row in fam["breakdown"]) == pytest.approx(1.0, abs=1e-3)
    assert r["profiles"]["senior"]["score"] == fam["score"]


def test_panel_weights_from_the_file_shape_the_profile(tmp_path, monkeypatch):
    weights = {a: 0.05 for a in M.INDEX_AREAS}
    weights["family"] = 0.6
    f = tmp_path / "weights.json"
    f.write_text(json.dumps({"sets": {"rodina": {"weights": weights, "panel": {"experts": 7, "cr": 0.04,
                                                                              "date": "2026-11-20"}}}}), encoding="utf-8")
    monkeypatch.setattr(M, "WEIGHTS_FILE", f)
    r = score.compute({"elements": everything_at(100)}, 48.28646, 17.27221)
    fam = r["profiles"]["rodina"]
    row = next(x for x in fam["breakdown"] if x["key"] == "family")
    assert fam["weights_method"] == "ahp" and row["weight"] == 0.6
    assert fam["score"] == round(sum(x["sub_score"] * x["weight"] for x in fam["breakdown"]))
    assert "7 expertov" in M.weights("rodina")["source"] and M.weights("senior")["method"] == "equal"


def test_inside_slovakia_every_index_area_has_data_and_the_index_is_computed():
    r = score.compute({"elements": everything_at(100)}, 48.28646, 17.27221)  # Pezinok
    idx = r["index"]
    counted = [a for a in idx["areas"] if a["in_index"]]
    assert not idx["missing"] and idx["index"] == round(sum(a["score"] for a in counted) / 9)
    assert r["region"]["zuj"]["code"] == "508179" and r["region"]["okres"]["code"] == "SK0107"
    safety = area(r, "safety")
    assert safety["status"] == "len za kraj" and "Bratislavský kraj" in safety["breakdown"][0]["fact"]
    assert [row["key"] for row in area(r, "income")["breakdown"]] == ["wage"]
