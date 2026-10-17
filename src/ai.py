"""Voice -> text and a drafted listing, through any OpenAI-compatible provider.

Speech goes to an /audio/transcriptions server (typically a local whisper with a Slovak model); the listing
draft comes from a /chat/completions model. Neither gets the agent's or buyers' contact details.
"""
import json
import logging
import math
import os
import re
from typing import Annotated

import httpx
from pydantic import TypeAdapter, ValidationError

from config import LlmConfig, SttConfig
from presentations import Params, PresentationData

logger = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_TRANSCRIPT_CHARS = 20_000


class AiUnavailable(RuntimeError):
    """The provider is not configured."""


class AiFailed(RuntimeError):
    """The provider could not be reached, refused, or answered with something unusable."""


def _headers(env_name: str) -> dict:
    key = os.environ.get(env_name)
    return {"Authorization": f"Bearer {key}"} if key else {}


# --- speech to text -------------------------------------------------------------------------

def transcribe(cfg: SttConfig, audio: bytes, filename: str, content_type: str,
               transport: httpx.BaseTransport | None = None) -> str:
    if not cfg.base_url:
        raise AiUnavailable("speech-to-text is not configured")
    url = cfg.base_url.rstrip("/") + "/audio/transcriptions"
    form = {"language": cfg.language, "response_format": "json"}
    if cfg.model:
        form["model"] = cfg.model
    try:
        with httpx.Client(timeout=cfg.timeout_s, transport=transport) as client:
            resp = client.post(url, data=form, files={"file": (filename, audio, content_type)},
                               headers=_headers(cfg.api_key_env))
            resp.raise_for_status()
            text = resp.json().get("text", "")
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Transcription failed: %s", exc)
        raise AiFailed("transcription failed") from exc
    return " ".join(str(text).split())


# --- neighbourhood facts for the prompt ------------------------------------------------------

CATEGORY_SK = {
    "hospital": "Nemocnica", "supermarket": "Supermarket", "school": "Škola", "kindergarten": "Materská škola",
    "pharmacy": "Lekáreň", "bus_stop": "Zastávka MHD", "train": "Železničná stanica", "park": "Park",
    "playground": "Detské ihrisko", "food": "Kaviareň / reštaurácia", "post": "Pošta", "bank": "Banka",
    "doctors": "Lekár", "city": "Mesto", "landmark": "Pamiatka", "bus_station": "Autobusová stanica",
    "mall": "Nákupné centrum",
}


def travel_time(meters: float) -> str:
    """Same rough estimate as the map's tooltips (frontend/src/overlay/describe.js)."""
    if meters <= 2500:
        return f"cca {max(1, math.ceil(meters * 1.3 / 80))} min pešo"
    return f"cca {max(1, round(meters * 1.25 / (50_000 / 60)))} min autom"


def _distance(meters: float) -> str:
    m = round(meters / 10) * 10
    if m < 1000:
        return f"{m} m"
    km = round(m / 100) / 10
    return f"{round(km)} km" if km >= 10 else f"{km:.1f} km".replace(".", ",")


def locality_facts(scene: dict) -> list[str]:
    pois = [p for p in (scene.get("near_pois") or []) + (scene.get("far_pois") or [])
            if isinstance(p.get("distance_m"), (int, float))]
    lines = []
    for p in sorted(pois, key=lambda p: p["distance_m"]):
        label = p.get("kind") or CATEGORY_SK.get(p.get("category"), p.get("category", ""))
        name = (p.get("name") or "").strip()
        what = f"{label} {name}".strip() if name and name != label else label
        lines.append(f"{what}: {_distance(p['distance_m'])}, {travel_time(p['distance_m'])}")
    return lines


# --- listing draft --------------------------------------------------------------------------

_SYSTEM = """Si asistent realitného makléra na Slovensku. Z poznámok makléra, už vyplnených údajov a zoznamu miest v okolí pripravíš návrh inzerátu.

Pravidlá:
- Používaj iba fakty z poznámok, vyplnených údajov a zoznamu okolia. Nič si nevymýšľaj: čo nevieš, nastav na null a uveď v "missing".
- Ak si poznámky a vyplnené údaje odporujú, platia poznámky.
- Nespomínaj mená, telefóny ani e-maily žiadnych osôb.
- Popis píš po slovensky, vecne a pútavo: 2 až 4 odseky oddelené prázdnym riadkom, bez nadpisov, odrážok a emoji, bez prázdnych superlatívov ("jedinečný", "luxusný" len ak to vyplýva z faktov).
- Okolie opíš konkrétne podľa zoznamu (napr. "supermarket je 70 m od domu"), nie frázou "kompletná občianska vybavenosť". Vzdialenosti nezvyšuj ani nezmenšuj.
- Cenu do popisu nepíš.
- "missing": krátke slovenské frázy o dôležitých údajoch, ktoré chýbajú (napr. "energetická trieda", "cena"), najviac 6.

Odpovedz iba jedným JSON objektom s týmito kľúčmi:
{"title": string|null (napr. "3-izbový byt s balkónom"), "offer": "sale"|"rent"|null, "price_eur": number|null, "price_note": string|null,
 "params": {"property_type": "flat"|"house"|"land"|"other"|null, "rooms": int|null, "area_m2": number|null, "land_m2": number|null,
   "floor": int|null (0 = prízemie), "floors_total": int|null, "condition": "new"|"renovated"|"partly_renovated"|"original"|"under_construction"|null,
   "energy_class": "A0"|"A1"|"A"|"B"|"C"|"D"|"E"|"F"|"G"|null, "year_built": int|null,
   "features": [ "balcony"|"loggia"|"terrace"|"elevator"|"cellar"|"parking"|"garage"|"garden" ]},
 "description": string, "missing": [string]}"""

_TOP_FIELDS = ("title", "offer", "price_eur", "price_note")
_CONTEXT_FIELDS = (*_TOP_FIELDS, "params", "description")  # never agent, photos or coordinates


def _field_value(model, name: str, value):
    """The value if it fits the field's type, else None: one bad field must not sink the whole draft."""
    if value is None:
        return None
    field = model.model_fields[name]
    try:
        kind = Annotated[field.annotation, *field.metadata] if field.metadata else field.annotation
        return TypeAdapter(kind).validate_python(value)
    except ValidationError:
        return None


def sanitize_draft(raw: dict) -> dict:
    params_in = raw.get("params") if isinstance(raw.get("params"), dict) else {}
    params = {name: _field_value(Params, name, params_in.get(name)) for name in Params.model_fields}
    features = params_in.get("features") if isinstance(params_in.get("features"), list) else []
    allowed = set(TypeAdapter(Params.model_fields["features"].annotation).json_schema()["items"]["enum"])
    params["features"] = [f for f in dict.fromkeys(features) if f in allowed]
    out = {name: _field_value(PresentationData, name, raw.get(name)) for name in _TOP_FIELDS}
    if isinstance(out["title"], str) and len(out["title"]) > 200:
        out["title"] = None
    description = raw.get("description")
    out["description"] = description.strip()[:10_000] if isinstance(description, str) and description.strip() else None
    out["params"] = params
    missing = raw.get("missing") if isinstance(raw.get("missing"), list) else []
    out["missing"] = [str(m).strip()[:120] for m in missing if str(m).strip()][:6]
    return out


def _json_object(content: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", content, flags=re.S)  # reasoning models (Qwen3, R1 distills)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the answer")
    value = json.loads(text[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("answer is not a JSON object")
    return value


def build_messages(transcript: str | None, data: dict, address: str | None, facts: list[str]) -> list[dict]:
    known = {k: data.get(k) for k in _CONTEXT_FIELDS if data.get(k) not in (None, "", [], {})}
    parts = [
        f"Adresa: {address or 'neuvedená'}",
        "Už vyplnené údaje (JSON):\n" + json.dumps(known, ensure_ascii=False),
        "Okolie (vzdušnou čiarou, čas je odhad):\n" + ("\n".join(f"- {f}" for f in facts) or "- žiadne údaje"),
        "Poznámky makléra (prepis hlasu, môže obsahovať chyby prepisu):\n" + (transcript.strip() if transcript else "(žiadne)"),
    ]
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": "\n\n".join(parts)}]


def draft_listing(cfg: LlmConfig, *, transcript: str | None, data: dict, address: str | None, scene: dict,
                  transport: httpx.BaseTransport | None = None) -> dict:
    if not cfg.base_url or not cfg.model:
        raise AiUnavailable("the language model is not configured")
    url = cfg.base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": cfg.model,
        "messages": build_messages(transcript, data, address, locality_facts(scene)),
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    try:
        with httpx.Client(timeout=cfg.timeout_s, transport=transport) as client:
            resp = client.post(url, json=body, headers=_headers(cfg.api_key_env))
            if resp.status_code == 400 and "response_format" in resp.text:
                # Not every OpenAI-compatible server knows JSON mode; the prompt asks for JSON anyway.
                body.pop("response_format")
                resp = client.post(url, json=body, headers=_headers(cfg.api_key_env))
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        return sanitize_draft(_json_object(content))
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning("Listing draft failed: %s", exc)
        raise AiFailed("the language model did not return a usable draft") from exc
