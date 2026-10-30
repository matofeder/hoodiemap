import pytest

from tests.test_presentations import client, store  # noqa: F401

AREAS = ["walk", "family", "transport", "green", "quiet", "income", "jobs", "housing", "safety"]
# judgments that are exact ratios of these weights: perfectly consistent (CR = 0)
TRUE = {"walk": 3, "family": 4, "transport": 1, "green": 3, "quiet": 2, "income": 2, "jobs": 2, "housing": 2, "safety": 4}
SAATY = [1, 2, 3, 4, 5, 6, 7, 8, 9]


def _on_scale(x):
    v = min(SAATY, key=lambda k: abs(k - (x if x >= 1 else 1 / x)))
    return v if x >= 1 else 1 / v


J = {f"{a}|{b}": _on_scale(TRUE[a] / TRUE[b]) for i, a in enumerate(AREAS) for b in AREAS[i + 1:]}


@pytest.fixture
def panel(monkeypatch):
    monkeypatch.setenv("HOODIEMAP_AHP_CODE", "panel-2026")
    monkeypatch.setenv("HOODIEMAP_ADMIN_TOKEN", "letmein")


async def test_sets_list_every_pair(client):
    body = (await client.get("/api/ahp/sets")).json()
    assert set(body["sets"]) == {"rodina", "senior", "bez_auta"}
    assert len(body["sets"]["rodina"]["pairs"]) == 36  # 9 index areas: 9·8/2 comparisons
    assert body["sets"]["rodina"]["criteria"]["safety"] == "Bezpečnosť"
    assert body["cr_limit"] == 0.1


async def test_check_returns_weights_and_cr_without_storing(client):
    r = await client.post("/api/ahp/check", json={"set_id": "rodina", "judgments": J})
    body = r.json()
    assert r.status_code == 200 and body["consistent"] and body["cr"] < 0.1
    assert body["weights"]["family"] > body["weights"]["transport"]
    bad = await client.post("/api/ahp/check", json={"set_id": "rodina", "judgments": {**J, "green|quiet": 11}})
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
    assert (await answer("Eva", "urbanistka", {**J, "housing|safety": 3})).status_code == 201
    await answer("Eva", "urbanistka", J)  # a second answer replaces the first
    await answer("Peter", "realitný znalec", {**J, "transport|safety": 1 / 5})
    circular = {**J, "walk|family": 1 / 9, "family|transport": 1 / 9, "walk|transport": 9,
                "green|quiet": 9, "quiet|income": 9, "green|income": 1 / 9}
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
    assert "senior" not in body["weights_json"]["sets"]  # nobody answered it: stays on equal weights
