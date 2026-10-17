from unittest.mock import patch

import pytest

from config import LandingConfig
from tests.test_presentations import client, store  # noqa: F401

OPEN = LandingConfig(operator="Matej Feder, Pezinok", contact_email="ahoj@example.sk", price_variants=["9", "19"])
SIGNUP = {"email": "Jana@Example.sk", "timeframe": "3m", "listing_url": "https://www.nehnutelnosti.sk/detail/x",
          "consent": True, "variant": "9", "source": "fb", "campaign": "test1"}


@pytest.fixture
def open_landing():
    with patch("landing_api._landing", return_value=OPEN):
        yield


async def test_info_says_closed_without_an_operator(client):
    r = await client.get("/api/landing")
    assert r.json()["open"] is False and r.json()["variants"] == ["9", "19"]
    assert (await client.post("/api/landing/signup", json=SIGNUP)).status_code == 503


async def test_events_validate_kind_variant_and_tags(client, open_landing):
    ok = {"kind": "view", "variant": "9", "source": "fb", "campaign": "jesen-2026"}
    assert (await client.post("/api/landing/event", json=ok)).status_code == 204
    assert (await client.post("/api/landing/event", json={**ok, "kind": "buy"})).status_code == 422
    assert (await client.post("/api/landing/event", json={**ok, "variant": "99"})).status_code == 422
    assert (await client.post("/api/landing/event", json={**ok, "source": "<script>"})).status_code == 422


async def test_signup_needs_consent_and_a_real_email(client, open_landing):
    assert (await client.post("/api/landing/signup", json={**SIGNUP, "consent": False})).status_code == 422
    assert (await client.post("/api/landing/signup", json={**SIGNUP, "email": "nope"})).status_code == 422
    assert (await client.post("/api/landing/signup", json={**SIGNUP, "listing_url": "javascript:x"})).status_code == 422
    r = await client.post("/api/landing/signup", json={**SIGNUP, "listing_url": "", "timeframe": ""})
    assert r.status_code == 201


async def test_stats_and_export_count_the_funnel(client, open_landing, monkeypatch):
    monkeypatch.setenv("HOODIEMAP_ADMIN_TOKEN", "letmein")
    admin = {"X-Admin-Token": "letmein"}
    for kind, variant, source in [("view", "9", "fb"), ("view", "9", "fb"), ("cta", "9", "fb"),
                                  ("view", "19", None), ("cta", "19", None)]:
        await client.post("/api/landing/event", json={"kind": kind, "variant": variant, "source": source})
    await client.post("/api/landing/signup", json=SIGNUP)
    await client.post("/api/landing/signup", json={**SIGNUP, "email": "jana@example.SK"})  # same person again
    await client.post("/api/landing/signup", json={**SIGNUP, "email": "bot@x.sk", "website": "spam"})
    await client.post("/api/landing/signup", json={**SIGNUP, "email": "peter@x.sk", "variant": "19",
                                                   "source": None, "timeframe": "browsing", "listing_url": None})

    assert (await client.get("/api/landing/stats")).status_code == 403
    stats = (await client.get("/api/landing/stats", headers=admin)).json()
    assert stats["totals"] == {"views": 3, "cta": 2, "signups": 2, "soon": 1, "with_listing": 1}
    fb = next(r for r in stats["rows"] if r["variant"] == "9")
    assert fb == {"variant": "9", "source": "fb", "views": 2, "cta": 1, "signups": 1, "soon": 1, "with_listing": 1}

    r = await client.get("/api/landing/export.csv", headers=admin)
    lines = r.text.strip().splitlines()
    assert r.headers["content-type"].startswith("text/csv") and len(lines) == 3
    assert "jana@example.sk" in lines[1] and "bot@x.sk" not in r.text


async def test_landing_api_is_noindex_but_the_page_route_is_public(client):
    r = await client.get("/api/landing")
    assert r.headers["x-robots-tag"] == "noindex, nofollow"
