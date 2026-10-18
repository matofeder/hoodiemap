import pytest

from tests.test_presentations import client, store  # noqa: F401

J = {"kindergarten|primary_school": 1, "kindergarten|playground": 3, "kindergarten|doctors": 5,
     "kindergarten|grocery": 3, "kindergarten|green": 3, "primary_school|playground": 3, "primary_school|doctors": 5,
     "primary_school|grocery": 3, "primary_school|green": 3, "playground|doctors": 2, "playground|grocery": 1,
     "playground|green": 1, "doctors|grocery": 1 / 2, "doctors|green": 1 / 2, "grocery|green": 1}


@pytest.fixture
def panel(monkeypatch):
    monkeypatch.setenv("HOODIEMAP_AHP_CODE", "panel-2026")
    monkeypatch.setenv("HOODIEMAP_ADMIN_TOKEN", "letmein")


async def test_sets_list_every_pair(client):
    body = (await client.get("/api/ahp/sets")).json()
    assert len(body["sets"]["rodina"]["pairs"]) == 15 and len(body["sets"]["zelen"]["pairs"]) == 3
    assert body["cr_limit"] == 0.1


async def test_check_returns_weights_and_cr_without_storing(client):
    r = await client.post("/api/ahp/check", json={"set_id": "rodina", "judgments": J})
    body = r.json()
    assert r.status_code == 200 and body["consistent"] and body["cr"] < 0.1
    assert body["weights"]["kindergarten"] > body["weights"]["doctors"]
    bad = await client.post("/api/ahp/check", json={"set_id": "rodina", "judgments": {**J, "doctors|green": 11}})
    assert bad.status_code == 422
    assert (await client.post("/api/ahp/check", json={"set_id": "nope", "judgments": {}})).status_code == 404


async def test_responses_need_the_panel_code(client, monkeypatch):
    payload = {"set_id": "rodina", "judgments": J, "code": "x", "expert": {"name": "Eva", "role": "urbanistka"}}
    monkeypatch.delenv("HOODIEMAP_AHP_CODE", raising=False)
    assert (await client.post("/api/ahp/responses", json=payload)).status_code == 503
    monkeypatch.setenv("HOODIEMAP_AHP_CODE", "panel-2026")
    assert (await client.post("/api/ahp/responses", json=payload)).status_code == 403


async def test_results_combine_the_latest_consistent_answers(client, panel):
    def answer(name, role, judgments):
        return client.post("/api/ahp/responses", json={"set_id": "rodina", "judgments": judgments, "code": "panel-2026",
                                                       "expert": {"name": name, "role": role}})
    assert (await answer("Eva", "urbanistka", {**J, "kindergarten|primary_school": 3})).status_code == 201
    await answer("Eva", "urbanistka", J)  # a second answer replaces the first
    await answer("Peter", "realitný znalec", {**J, "kindergarten|primary_school": 2})
    circular = {**J, "kindergarten|playground": 1 / 9, "playground|doctors": 9, "kindergarten|doctors": 9,
                "doctors|green": 9, "kindergarten|green": 1 / 9}
    r = await answer("Jano", "rodič", circular)
    assert r.json()["consistent"] is False

    assert (await client.get("/api/ahp/results")).status_code == 403
    body = (await client.get("/api/ahp/results", headers={"X-Admin-Token": "letmein"})).json()
    rodina = body["sets"]["rodina"]
    assert [e["name"] for e in rodina["experts"]] == ["Eva", "Jano", "Peter"] and rodina["used"] == 2
    assert rodina["group"]["consistent"]
    file = body["weights_json"]["sets"]["rodina"]
    assert file["panel"]["experts"] == 2 and file["panel"]["excluded_inconsistent"] == 1
    assert sum(file["weights"].values()) == pytest.approx(1.0, abs=1e-3)
    assert "zelen" not in body["weights_json"]["sets"]  # nobody answered it: stays on equal weights
