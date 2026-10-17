import io
import json
from unittest.mock import patch

import pytest
from PIL import Image

import listing_import as li
from tests.test_presentations import SCENE, client, store  # noqa: F401

URL = "https://www.nehnutelnosti.sk/detail/AbC123xyz/2-izbovy-byt-vzorova-pezinok"
DESCRIPTION = "Slnečný byt v tichej lokalite.\r\nNové okná.\n\n\n\nBalkón na juh."


def _photo_url(i):
    return f"https://img.example.sk/foto/{i}.webp"


def listing_page(*, street_number="12", floor=3, floors=4, year=2009, photos=3, tour=True) -> str:
    """A page shaped like a nehnutelnosti.sk detail: JSON-LD plus Next.js flight rows (made-up data)."""
    ad = {
        "id": "AbC123xyz", "title": "2-izbový byt, Vzorová ul., Pezinok", "description": "$2e",
        "media": {"photos": [{"largeUrl": _photo_url(i), "origUrl": _photo_url(i)} for i in range(photos)],
                  "inspections3d": [{"type": "MATTERPORT", "url": "https://my.matterport.com/show/?m=abc"}] if tour else []},
        "location": {"name": "Vzorová 12, Pezinok, okres Pezinok", "city": "Pezinok", "street": "Vzorová",
                     "streetNumber": street_number, "point": {"latitude": 48.2967, "longitude": 17.2783, "radius": 200}},
        "parameters": {
            "hasElevator": False, "price": {"priceNum": 199900}, "transaction": "Predaj",
            "category": {"mainValue": "APARTMENTS", "subValue": "TWO_ROOM_APARTMENT"},
            "attributes": [{"label": "Plocha balkóna", "value": "3,8 m²"}, {"label": "Plocha pivnice", "value": "1,5 m²"},
                           {"label": "Počet izieb / miestností", "value": "2"}, {"label": "Vybavenie", "value": "Výťah"}],
            "floor": floor, "numberOfFloors": floors, "realEstateState": "Čiastočná rekonštrukcia",
            "area": "56", "yearOfConstruction": year, "energyRatingCertificate": "B",
        },
        "advertiser": {"name": "Ing. Jana Vzorová", "mainPhone": "0903 ...", "agency": {"name": "Vzor Reality s.r.o."}},
    }
    desc_bytes = DESCRIPTION.encode("utf-8")
    flight = ('27:["$","$L2d",null,' + json.dumps({"advertisement": ad}, ensure_ascii=False)[:-1] + "}]\n"
              + f"2e:T{len(desc_bytes):x}," + DESCRIPTION)
    half = len(flight) // 2
    pushes = "".join(f'<script>self.__next_f.push([1,{json.dumps(part, ensure_ascii=False)}])</script>'
                     for part in (flight[:half], flight[half:]))
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "Product", "name": ad["title"], "description": "Slnečný byt v tichej lokalite. Nové okná.",
         "image": [{"@type": "ImageObject", "url": _photo_url(i)} for i in range(photos)]},
        {"@type": "Offer", "priceSpecification": {"price": 199900}, "businessFunction": {"@id": "http://purl.org/goodrelations/v1#Sell"}},
        {"@type": "RealEstateAgent", "name": "Vzor Reality s.r.o."},
    ]}
    return f'<html><head><script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script></head><body>{pushes}</body></html>'


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (1560, 1040), (180, 160, 140)).save(out, "WEBP")
    return out.getvalue()


# --- parsing --------------------------------------------------------------------------------

def test_check_url_accepts_only_listing_details():
    assert li.check_url(" https://nehnutelnosti.sk/detail/AbC/x?utm=1 ") == "https://www.nehnutelnosti.sk/detail/AbC/x"
    for bad in ["http://www.nehnutelnosti.sk/detail/a", "https://www.nehnutelnosti.sk/vysledky/pezinok",
                "https://evil.example/detail/a", "https://www.nehnutelnosti.sk.evil.example/detail/a"]:
        with pytest.raises(li.ImportError_):
            li.check_url(bad)


def test_parse_maps_the_listing():
    r = li.parse(listing_page(), URL)
    d = r.data
    assert d["title"] == "2-izbový byt, Vzorová ul., Pezinok"
    assert d["offer"] == "sale" and d["price_eur"] == 199900
    assert d["location"] == {"lat": 48.2967, "lon": 17.2783, "tier": "address", "name": None, "label": "Vzorová 12, Pezinok"}
    assert d["params"] == {
        "property_type": "flat", "rooms": 2, "area_m2": 56.0, "land_m2": None, "floor": 2, "floors_total": 3,
        "condition": "partly_renovated", "energy_class": "B", "year_built": 2009,
        "features": ["balcony", "cellar", "elevator"],
    }
    assert d["description"] == "Slnečný byt v tichej lokalite.\nNové okná.\n\nBalkón na juh."
    assert d["tour_url"] == "https://my.matterport.com/show/?m=abc"
    assert d["agent"] == {"name": "Ing. Jana Vzorová", "agency": "Vzor Reality s.r.o."}
    assert "phone" not in d["agent"]
    assert r.photo_urls == [_photo_url(i) for i in range(3)]
    assert r.address_query == "Vzorová 12, Pezinok" and r.agency == "Vzor Reality s.r.o."
    assert any("Poschodie" in w for w in r.warnings)


def test_parse_without_house_number_falls_back_to_the_street():
    r = li.parse(listing_page(street_number=None), URL)
    assert r.data["location"]["tier"] == "street" and r.data["location"]["name"] == "Vzorová"
    assert r.address_query is None
    assert any("číslo domu" in w for w in r.warnings)


def test_parse_drops_implausible_years():
    r = li.parse(listing_page(year=2089), URL)
    assert r.data["params"]["year_built"] is None
    assert any("2089" in w for w in r.warnings)


def test_parse_rejects_pages_without_listing_data():
    with pytest.raises(li.ImportError_):
        li.parse("<html><body>Inzerát už neexistuje</body></html>", URL)


# --- endpoint -------------------------------------------------------------------------------

@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setenv("HOODIEMAP_ADMIN_TOKEN", "letmein")
    return {"X-Admin-Token": "letmein"}


async def test_import_needs_the_admin_token(client, monkeypatch):
    monkeypatch.delenv("HOODIEMAP_ADMIN_TOKEN", raising=False)
    assert (await client.post("/api/import", json={"url": URL})).status_code == 503
    monkeypatch.setenv("HOODIEMAP_ADMIN_TOKEN", "letmein")
    r = await client.post("/api/import", json={"url": URL}, headers={"X-Admin-Token": "nope"})
    assert r.status_code == 403


async def test_import_creates_a_demo_with_photos(client, admin):
    geocoder = type("G", (), {"search": lambda self, q: {"lat": 48.29671, "lon": 17.27841, "tier": "address"}})()
    with patch("import_api.listing_import.fetch", return_value=listing_page()) as fetch, \
         patch("import_api.listing_import.fetch_photo", side_effect=[_jpeg(), b"broken", _jpeg()]), \
         patch("import_api.get_geocoder", return_value=geocoder), \
         patch("presentation_api.build_scene", return_value=dict(SCENE)) as build:
        r = await client.post("/api/import", json={"url": URL}, headers=admin)
    assert r.status_code == 201, r.text
    body = r.json()
    fetch.assert_called_once_with(URL)
    assert build.call_args.args[:2] == (48.29671, 17.27841)  # geocoded house, not the portal's ±200 m point
    assert body["photos"] == 2 and any("1 fotiek" in w for w in body["warnings"])
    assert body["demo_for"] == "Vzor Reality s.r.o."

    view = (await client.get(f"/api/presentations/{body['id']}/edit", headers={"X-Edit-Token": body["edit_token"]})).json()
    assert view["source_url"] == URL and view["expires_at"] is not None
    assert view["data"]["tour_url"].startswith("https://my.matterport.com/")
    assert len(view["data"]["photos"]) == 2
    assert (await client.get(f"/api/presentations/{body['id']}")).json()["demo_for"] == "Vzor Reality s.r.o."


async def test_import_uses_the_portal_point_when_geocoding_misses(client, admin):
    geocoder = type("G", (), {"search": lambda self, q: None})()
    with patch("import_api.listing_import.fetch", return_value=listing_page(photos=0)), \
         patch("import_api.get_geocoder", return_value=geocoder), \
         patch("presentation_api.build_scene", return_value=dict(SCENE)) as build:
        r = await client.post("/api/import", json={"url": URL, "demo_for": "Jana"}, headers=admin)
    assert r.status_code == 201
    assert build.call_args.args[:2] == (48.2967, 17.2783)
    assert r.json()["demo_for"] == "Jana" and any("± 200 m" in w for w in r.json()["warnings"])


async def test_import_reports_bad_urls_and_pages(client, admin):
    r = await client.post("/api/import", json={"url": "https://www.nehnutelnosti.sk/vysledky/pezinok"}, headers=admin)
    assert r.status_code == 422
    with patch("import_api.listing_import.fetch", return_value="<html></html>"):
        r = await client.post("/api/import", json={"url": URL}, headers=admin)
    assert r.status_code == 422
