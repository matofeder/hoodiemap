import httpx
import pytest

from geocode import Geocoder, GeocodeUnavailable, short_label, tier_for_rank

HIT = {
    "lat": "48.2895813", "lon": "17.2696", "place_rank": 26, "name": "Záhradná",
    "display_name": "Záhradná, Cajla, Pezinok, okres Pezinok, Slovensko",
    "address": {"road": "Záhradná", "town": "Pezinok"},
}


def _transport(bodies, calls):
    def handler(request):
        calls.append(request)
        body = bodies[len(calls) - 1]
        if isinstance(body, Exception):
            raise body
        return httpx.Response(200, json=body)
    return httpx.MockTransport(handler)


class Clock:
    def __init__(self):
        self.t, self.slept = 100.0, []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 3))
        self.t += s


@pytest.mark.parametrize("rank,tier", [(30, "address"), (28, "address"), (27, "street"), (26, "street"),
                                       (25, "city"), (18, "city"), (16, "city")])
def test_tier_for_rank(rank, tier):
    assert tier_for_rank(rank) == tier


def test_short_labels():
    assert short_label(HIT) == "Záhradná, Pezinok"
    house = {**HIT, "place_rank": 30, "address": {"road": "Záhradná", "house_number": "12", "town": "Pezinok"}}
    assert short_label(house) == "Záhradná 12, Pezinok"
    borough = {"place_rank": 18, "name": "Staré Mesto", "address": {"city": "Bratislava"}}
    assert short_label(borough) == "Staré Mesto, Bratislava"
    town = {"place_rank": 16, "name": "Pezinok", "address": {"town": "Pezinok"}}
    assert short_label(town) == "Pezinok"


def test_short_label_survives_missing_fields():
    assert short_label({"place_rank": 26, "display_name": "Niečo, Niekde"}) == "Niečo, Niekde"
    assert short_label({"place_rank": 16, "name": "Modra"}) == "Modra"
    assert short_label({}) == ""


def test_search_returns_best_match_with_tier_and_sends_params(tmp_path):
    calls = []
    g = Geocoder("sk,cz", str(tmp_path), transport=_transport([[HIT]], calls))
    r = g.search("Záhradná Pezinok")
    assert r == {"lat": 48.2895813, "lon": 17.2696, "tier": "street", "name": "Záhradná",
                 "label": "Záhradná, Pezinok", "place_rank": 26}
    params = calls[0].url.params
    assert params["countrycodes"] == "sk,cz" and params["limit"] == "1" and params["format"] == "jsonv2"
    assert params["accept-language"] == "sk" and params["addressdetails"] == "1"


def test_street_name_prefers_road_over_display_name(tmp_path):
    house = {**HIT, "place_rank": 30, "name": "", "address": {"road": "Záhradná", "house_number": "12", "town": "Pezinok"}}
    g = Geocoder("sk", str(tmp_path), transport=_transport([[house]], []))
    assert g.search("Záhradná 12 Pezinok")["name"] == "Záhradná"


def test_search_cache_hit_skips_network_and_normalizes_query(tmp_path):
    calls = []
    g = Geocoder("sk", str(tmp_path), transport=_transport([[HIT]], calls))
    first = g.search("Záhradná  Pezinok")
    assert g.search("  záhradná pezinok ") == first
    assert len(calls) == 1


def test_not_found_returns_none_and_is_not_cached(tmp_path):
    calls, clock = [], Clock()
    g = Geocoder("sk", str(tmp_path), transport=_transport([[], [HIT]], calls), clock=clock.now, sleep=clock.sleep)
    assert g.search("xyz") is None
    assert g.search("xyz") is not None
    assert len(calls) == 2


def test_throttle_waits_one_second_between_requests(tmp_path):
    clock = Clock()
    g = Geocoder("sk", None, transport=_transport([[HIT], [HIT]], []), clock=clock.now, sleep=clock.sleep)
    g.search("a")
    clock.t += 0.25
    g.search("b")
    assert clock.slept == [0.75]


def test_network_error_raises_unavailable(tmp_path):
    g = Geocoder("sk", None, transport=_transport([httpx.ConnectError("offline")], []))
    with pytest.raises(GeocodeUnavailable):
        g.search("Pezinok")
