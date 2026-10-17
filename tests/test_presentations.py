import io
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from osm import OverpassError

SCENE = {
    "center": {"lat": 48.28, "lon": 17.27}, "radius_m": 140, "tier": "address", "buildings": [],
    "property": {"building_index": None}, "roads": [],
    "areas": {"park": [], "water": [], "forest": [], "plaza": []}, "trees": [],
    "near_pois": [], "far_pois": [], "warnings": [],
}
DATA = {
    "location": {"lat": 48.2864, "lon": 17.2722, "tier": "address", "label": "Záhradná 12, Pezinok"},
    "title": "3-izbový byt s balkónom",
    "price_eur": 189000,
    "params": {"property_type": "flat", "rooms": 3, "area_m2": 72, "features": ["balcony", "elevator"]},
    "agent": {"name": "Jana Nová", "phone": "+421 900 123 456"},
}


@pytest.fixture
def store(tmp_path):
    from presentation_api import get_store
    from presentations import PresentationStore
    from api import app
    s = PresentationStore(tmp_path / "data")
    app.dependency_overrides[get_store] = lambda: s
    yield s
    app.dependency_overrides.clear()


@pytest.fixture
async def client(store):
    from api import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _create(client, **extra):
    with patch("presentation_api.build_scene", return_value=dict(SCENE)) as build:
        r = await client.post("/api/presentations", json={"data": DATA, **extra})
    assert r.status_code == 201, r.text
    return r.json(), build


def _jpeg(w=3000, h=2000, color=(200, 120, 90)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), color).save(out, "JPEG")
    return out.getvalue()


async def test_create_builds_scene_and_view_hides_token(client):
    created, build = await _create(client)
    build.assert_called_once()
    assert build.call_args.args[:2] == (48.2864, 17.2722)
    r = await client.get(f"/api/presentations/{created['id']}")
    assert r.status_code == 200
    body = r.json()
    assert "edit_token" not in body and "leads" not in body
    assert body["data"]["title"] == "3-izbový byt s balkónom"
    assert body["scene"]["address"] == "Záhradná 12, Pezinok"
    assert r.headers["x-robots-tag"] == "noindex, nofollow"


async def test_create_502_when_overpass_down_saves_nothing(client, store):
    with patch("presentation_api.build_scene", side_effect=OverpassError("down")):
        r = await client.post("/api/presentations", json={"data": DATA})
    assert r.status_code == 502
    with store._connect() as con:
        assert con.execute("SELECT COUNT(*) FROM presentations").fetchone()[0] == 0


async def test_create_rejects_unknown_fields_and_bad_values(client):
    bad = {**DATA, "params": {"rooms": -1}}
    r = await client.post("/api/presentations", json={"data": bad})
    assert r.status_code == 422
    r = await client.post("/api/presentations", json={"data": {**DATA, "owner_phone": "x"}})
    assert r.status_code == 422


async def test_unknown_presentation_is_404(client):
    assert (await client.get("/api/presentations/nope")).status_code == 404


async def test_edit_requires_token(client):
    created, _ = await _create(client)
    pid = created["id"]
    assert (await client.get(f"/api/presentations/{pid}/edit")).status_code == 403
    r = await client.get(f"/api/presentations/{pid}/edit", headers={"X-Edit-Token": "wrong"})
    assert r.status_code == 403
    r = await client.patch(f"/api/presentations/{pid}", json={"title": "x"})
    assert r.status_code == 403
    r = await client.get(f"/api/presentations/{pid}/edit", headers={"X-Edit-Token": created["edit_token"]})
    assert r.status_code == 200 and r.json()["leads"] == []


async def test_patch_merges_and_rebuilds_scene_only_when_location_moves(client):
    created, _ = await _create(client)
    pid, h = created["id"], {"X-Edit-Token": created["edit_token"]}
    with patch("presentation_api.build_scene", return_value=dict(SCENE)) as build:
        r = await client.patch(f"/api/presentations/{pid}", json={"price_eur": 179000}, headers=h)
        assert r.status_code == 200
        assert build.call_count == 0
        body = r.json()["data"]
        assert body["price_eur"] == 179000 and body["title"] == DATA["title"]

        moved = {**DATA["location"], "lat": 48.30, "label": "Holubyho 5, Pezinok"}
        r = await client.patch(f"/api/presentations/{pid}", json={"location": moved}, headers=h)
        assert r.status_code == 200
        assert build.call_count == 1
        assert r.json()["scene"]["address"] == "Holubyho 5, Pezinok"


async def test_patch_rejects_unknown_keys(client):
    created, _ = await _create(client)
    r = await client.patch(f"/api/presentations/{created['id']}", json={"edit_token": "x"},
                           headers={"X-Edit-Token": created["edit_token"]})
    assert r.status_code == 422


async def test_expired_presentation_is_410_but_owner_can_still_edit(client, store):
    created, _ = await _create(client, demo_for="Reality Pezinok", expires_in_days=30)
    pid = created["id"]
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
    with store._connect() as con:
        con.execute("UPDATE presentations SET expires_at = ? WHERE id = ?", (past, pid))
    assert (await client.get(f"/api/presentations/{pid}")).status_code == 410
    r = await client.get(f"/api/presentations/{pid}/edit", headers={"X-Edit-Token": created["edit_token"]})
    assert r.status_code == 200
    assert r.json()["expired"] is True and r.json()["demo_for"] == "Reality Pezinok"


async def test_photo_upload_reencodes_reorders_and_deletes(client, store):
    created, _ = await _create(client)
    pid, h = created["id"], {"X-Edit-Token": created["edit_token"]}
    ids = []
    for color in [(255, 0, 0), (0, 0, 255)]:
        r = await client.post(f"/api/presentations/{pid}/photos", headers=h,
                              files={"file": ("p.jpg", _jpeg(color=color), "image/jpeg")})
        assert r.status_code == 201, r.text
        assert (r.json()["w"], r.json()["h"]) == (2000, 1333)
        ids.append(r.json()["id"])

    r = await client.get(f"/api/presentations/{pid}/photos/{ids[0]}/thumb")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert max(Image.open(io.BytesIO(r.content)).size) == 600
    assert "immutable" in r.headers["cache-control"]

    order = [{"id": ids[1], "caption": "Kuchyňa"}, {"id": ids[0]}]
    r = await client.patch(f"/api/presentations/{pid}", json={"photos": order}, headers=h)
    assert r.status_code == 200
    photos = r.json()["data"]["photos"]
    assert [p["id"] for p in photos] == [ids[1], ids[0]]
    assert photos[0]["caption"] == "Kuchyňa" and photos[0]["w"] == 2000

    # reordering may not smuggle in or drop photos
    r = await client.patch(f"/api/presentations/{pid}", json={"photos": [{"id": ids[0]}]}, headers=h)
    assert r.status_code == 422

    r = await client.delete(f"/api/presentations/{pid}/photos/{ids[0]}", headers=h)
    assert r.status_code == 204
    assert (await client.get(f"/api/presentations/{pid}/photos/{ids[0]}/large")).status_code == 404
    assert not (store.photo_dir(pid) / f"{ids[0]}_large.jpg").exists()


async def test_photo_upload_strips_exif(client):
    created, _ = await _create(client)
    pid, h = created["id"], {"X-Edit-Token": created["edit_token"]}
    img = Image.new("RGB", (800, 600))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # Make
    exif[0x0112] = 6  # Orientation: rotate 90° CW to display
    out = io.BytesIO()
    img.save(out, "JPEG", exif=exif.tobytes())
    r = await client.post(f"/api/presentations/{pid}/photos", headers=h,
                          files={"file": ("p.jpg", out.getvalue(), "image/jpeg")})
    assert (r.json()["w"], r.json()["h"]) == (600, 800)  # orientation applied
    r = await client.get(f"/api/presentations/{pid}/photos/{(r.json()['id'])}/large")
    assert not Image.open(io.BytesIO(r.content)).getexif()


async def test_photo_upload_rejects_non_images_and_needs_token(client):
    created, _ = await _create(client)
    pid = created["id"]
    files = {"file": ("p.jpg", _jpeg(), "image/jpeg")}
    assert (await client.post(f"/api/presentations/{pid}/photos", files=files)).status_code == 403
    r = await client.post(f"/api/presentations/{pid}/photos", headers={"X-Edit-Token": created["edit_token"]},
                          files={"file": ("p.jpg", b"%PDF-1.4 not a photo", "image/jpeg")})
    assert r.status_code == 422


async def test_photo_path_cannot_escape(client):
    created, _ = await _create(client)
    r = await client.get(f"/api/presentations/{created['id']}/photos/..%2F..%2Fhoodiemap.db/large")
    assert r.status_code == 404


async def test_leads_are_validated_and_listed_for_the_owner(client):
    created, _ = await _create(client)
    pid, h = created["id"], {"X-Edit-Token": created["edit_token"]}
    url = f"/api/presentations/{pid}/leads"
    assert (await client.post(url, json={"name": "Peter", "consent": True})).status_code == 422  # no contact
    assert (await client.post(url, json={"name": "Peter", "email": "p@x.sk", "consent": False})).status_code == 422
    assert (await client.post(url, json={"name": "Peter", "email": "nope", "consent": True})).status_code == 422
    r = await client.post(url, json={"name": "Peter", "email": "", "phone": "0900 111 222",
                                     "message": "Kedy obhliadka?", "consent": True})
    assert r.status_code == 201
    r = await client.post(url, json={"name": "Bot", "email": "b@x.sk", "consent": True, "website": "http://spam"})
    assert r.status_code == 201  # honeypot: looks fine, stored nowhere

    leads = (await client.get(f"/api/presentations/{pid}/edit", headers=h)).json()["leads"]
    assert len(leads) == 1
    assert leads[0]["name"] == "Peter" and leads[0]["phone"] == "0900 111 222" and leads[0]["email"] is None


async def test_create_with_fixture_uses_the_fixture_scene(client):
    with patch("presentation_api.build_scene") as build:
        r = await client.post("/api/presentations", json={"data": DATA, "fixture": True})
    assert r.status_code == 201
    build.assert_not_called()
    body = (await client.get(f"/api/presentations/{r.json()['id']}")).json()
    assert body["scene"]["near_pois"]
