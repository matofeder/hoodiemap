import json
from unittest.mock import patch

import httpx
import pytest

import ai
from config import LlmConfig, SttConfig

LLM = LlmConfig(base_url="https://llm.example/v1", model="cheap-model", api_key_env="TEST_LLM_KEY")
STT = SttConfig(base_url="http://localhost:8001/v1", model="whisper-sk", language="sk")

SCENE = {
    "near_pois": [{"category": "supermarket", "name": "Billa", "distance_m": 69},
                  {"category": "playground", "name": None, "distance_m": 51}],
    "far_pois": [{"category": "city", "name": "Bratislava", "distance_m": 20006},
                 {"category": "school", "name": "Gymnazium", "distance_m": 151}],
}
GOOD = {
    "title": "3-izbový byt s balkónom", "offer": "sale", "price_eur": 189000, "price_note": None,
    "params": {"property_type": "flat", "rooms": 3, "area_m2": 72.5, "floor": 4, "floors_total": 7,
               "condition": "renovated", "energy_class": None, "year_built": 1987,
               "features": ["balcony", "elevator"]},
    "description": "Svetlý byt po rekonštrukcii.\n\nSupermarket je 70 m od domu.",
    "missing": ["energetická trieda"],
}


def _chat(content: str):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def test_travel_time_matches_the_map_tooltips():
    assert ai.travel_time(69) == "cca 2 min pešo"  # describe.js: ceil(69 * 1.3 / 80)
    assert ai.travel_time(20006) == "cca 30 min autom"


def test_locality_facts_are_sorted_and_named():
    assert ai.locality_facts(SCENE) == [
        "Detské ihrisko: 50 m, cca 1 min pešo",
        "Supermarket Billa: 70 m, cca 2 min pešo",
        "Škola Gymnazium: 150 m, cca 3 min pešo",
        "Mesto Bratislava: 20 km, cca 30 min autom",
    ]


def test_sanitize_keeps_good_fields_and_drops_bad_ones_individually():
    raw = {**GOOD, "price_eur": "veľa", "offer": "swap", "title": "x" * 300,
           "params": {**GOOD["params"], "rooms": -2, "energy_class": "Z", "features": ["balcony", "pool", "balcony"]},
           "missing": ["cena", "", 5], "agent": {"name": "should vanish"}}
    out = ai.sanitize_draft(raw)
    assert out["price_eur"] is None and out["offer"] is None and out["title"] is None
    assert out["params"]["rooms"] is None and out["params"]["energy_class"] is None
    assert out["params"]["area_m2"] == 72.5 and out["params"]["features"] == ["balcony"]
    assert out["missing"] == ["cena", "5"]
    assert "agent" not in out


def test_json_object_survives_fences_and_reasoning():
    content = "<think>hmm {not json}</think>\n```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```"
    assert ai._json_object(content)["title"] == GOOD["title"]
    with pytest.raises(ValueError):
        ai._json_object("Prepáčte, neviem.")


def test_draft_sends_facts_not_contacts_and_returns_sanitized(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret")
    seen = {}

    def handler(request: httpx.Request):
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_chat(json.dumps(GOOD, ensure_ascii=False)))

    data = {"title": "Byt", "params": {"rooms": 3}, "agent": {"phone": "0900 111 222"}, "photos": [{"id": "x"}]}
    out = ai.draft_listing(LLM, transcript="tri izby, štvrté poschodie", data=data, address="Záhradná 12, Pezinok",
                           scene=SCENE, transport=httpx.MockTransport(handler))
    assert out["params"]["rooms"] == 3 and out["missing"] == ["energetická trieda"]
    assert seen["auth"] == "Bearer secret"
    assert seen["body"]["model"] == "cheap-model"
    prompt = seen["body"]["messages"][1]["content"]
    assert "Supermarket Billa: 70 m" in prompt and "tri izby" in prompt and "Záhradná 12" in prompt
    assert "0900" not in prompt and "photos" not in prompt


def test_draft_retries_without_json_mode_when_unsupported():
    calls = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        calls.append("response_format" in body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": "unknown field response_format"})
        return httpx.Response(200, json=_chat(json.dumps(GOOD)))

    out = ai.draft_listing(LLM, transcript="x", data={}, address=None, scene={}, transport=httpx.MockTransport(handler))
    assert calls == [True, False] and out["title"] == GOOD["title"]


def test_draft_failures_and_missing_config():
    with pytest.raises(ai.AiUnavailable):
        ai.draft_listing(LlmConfig(), transcript="x", data={}, address=None, scene={})
    bad = httpx.MockTransport(lambda r: httpx.Response(200, json=_chat("nie je to JSON")))
    with pytest.raises(ai.AiFailed):
        ai.draft_listing(LLM, transcript="x", data={}, address=None, scene={}, transport=bad)
    down = httpx.MockTransport(lambda r: httpx.Response(503))
    with pytest.raises(ai.AiFailed):
        ai.draft_listing(LLM, transcript="x", data={}, address=None, scene={}, transport=down)


def test_transcribe_posts_audio_with_slovak_language():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["body"] = request.content
        return httpx.Response(200, json={"text": "  Trojizbový byt,\n štvrté poschodie. "})

    text = ai.transcribe(STT, b"OggS-fake-audio", "notes.webm", "audio/webm", transport=httpx.MockTransport(handler))
    assert text == "Trojizbový byt, štvrté poschodie."
    assert seen["url"] == "http://localhost:8001/v1/audio/transcriptions"
    assert b'name="language"\r\n\r\nsk' in seen["body"] and b'name="model"\r\n\r\nwhisper-sk' in seen["body"]
    assert b"OggS-fake-audio" in seen["body"]


def test_transcribe_unconfigured_or_down():
    with pytest.raises(ai.AiUnavailable):
        ai.transcribe(SttConfig(), b"x", "a.webm", "audio/webm")
    with pytest.raises(ai.AiFailed):
        ai.transcribe(STT, b"x", "a.webm", "audio/webm", transport=httpx.MockTransport(lambda r: httpx.Response(500)))


# --- API ------------------------------------------------------------------------------------

from tests.test_presentations import DATA, SCENE as PRES_SCENE, client, store  # noqa: E402,F401


async def _created(client):
    with patch("presentation_api.build_scene", return_value=dict(PRES_SCENE)):
        r = await client.post("/api/presentations", json={"data": DATA})
    return r.json()["id"], {"X-Edit-Token": r.json()["edit_token"]}


async def test_edit_view_reports_which_ai_features_are_on(client):
    pid, h = await _created(client)
    r = await client.get(f"/api/presentations/{pid}/edit", headers=h)
    assert r.json()["ai"] == {"voice": False, "text": False}  # config.yaml ships with AI off


async def test_ai_endpoints_need_the_token_and_report_off(client):
    pid, h = await _created(client)
    files = {"file": ("a.webm", b"audio", "audio/webm")}
    assert (await client.post(f"/api/presentations/{pid}/ai/transcribe", files=files)).status_code == 403
    assert (await client.post(f"/api/presentations/{pid}/ai/transcribe", files=files, headers=h)).status_code == 503
    r = await client.post(f"/api/presentations/{pid}/ai/draft", json={"transcript": "tri izby"}, headers=h)
    assert r.status_code == 503


async def test_draft_endpoint_passes_saved_location_and_scene(client):
    pid, h = await _created(client)
    with patch("presentation_api.ai.draft_listing", return_value=ai.sanitize_draft(GOOD)) as draft:
        r = await client.post(f"/api/presentations/{pid}/ai/draft", headers=h,
                              json={"transcript": "tri izby", "data": {"title": "Byt", "agent": {"phone": "1"}}})
    assert r.status_code == 200 and r.json()["params"]["rooms"] == 3
    kwargs = draft.call_args.kwargs
    assert kwargs["address"] == "Záhradná 12, Pezinok" and kwargs["scene"]["radius_m"] == 140
    assert kwargs["data"]["title"] == "Byt" and "agent" not in kwargs["data"]


async def test_draft_needs_something_to_write_from(client):
    pid, h = await _created(client)
    r = await client.post(f"/api/presentations/{pid}/ai/draft", json={}, headers=h)
    assert r.status_code == 422


async def test_transcribe_endpoint_maps_provider_failure_to_502(client):
    pid, h = await _created(client)
    files = {"file": ("a.webm", b"audio", "audio/webm")}
    with patch("presentation_api.ai.transcribe", side_effect=ai.AiFailed("down")):
        assert (await client.post(f"/api/presentations/{pid}/ai/transcribe", files=files, headers=h)).status_code == 502
    with patch("presentation_api.ai.transcribe", return_value="tri izby") as t:
        r = await client.post(f"/api/presentations/{pid}/ai/transcribe", files=files, headers=h)
    assert r.json() == {"text": "tri izby"} and t.call_args.args[1] == b"audio"
    empty = {"file": ("a.webm", b"", "audio/webm")}
    assert (await client.post(f"/api/presentations/{pid}/ai/transcribe", files=empty, headers=h)).status_code == 422


async def test_features_endpoint_is_public(client):
    r = await client.get("/api/features")
    assert r.status_code == 200 and r.json() == {"ai": {"voice": False, "text": False}}
