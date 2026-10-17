"""/api/presentations: create, view and edit a property presentation, its photos and buyer leads."""
import asyncio
import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import ai
from config import get_config
from db import connect_pool, migrate
from osm import AREA_FAILED_DETAIL, OverpassError
from presentations import (
    MAX_PHOTO_BYTES, MAX_PHOTOS, LeadIn, Location, Photo, PhotoError, PresentationData, PresentationStore,
    Record, new_photo_id, process_photo,
)
from scene_builder import build_scene

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "pezinok-centrum.json"
NOT_FOUND = "Presentation not found."
GONE = "This presentation has expired."
BAD_TOKEN = "The edit link is not valid."
PHOTO_SIZES = {"large", "thumb"}

router = APIRouter(prefix="/api/presentations")
_store: PresentationStore | None = None


def get_store() -> PresentationStore:
    global _store
    if _store is None:
        cfg = get_config()
        pool = connect_pool(cfg.database.resolved_url())
        migrate(pool)
        _store = PresentationStore(pool, cfg.storage.dir)
    return _store


Store = Annotated[PresentationStore, Depends(get_store)]
Token = Annotated[str | None, Header(alias="X-Edit-Token")]


class CreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: PresentationData
    demo_for: Annotated[str, Field(max_length=200)] | None = None
    expires_in_days: Annotated[int, Field(ge=1, le=365)] | None = None
    fixture: bool = False


def _location_key(loc: dict) -> tuple:
    return (loc["lat"], loc["lon"], loc.get("tier"), loc.get("name"))


async def _scene_for(loc: Location, fixture: bool) -> dict:
    if fixture:
        scene = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    else:
        try:
            scene = await asyncio.to_thread(build_scene, loc.lat, loc.lon, get_config(), loc.tier, loc.name)
        except OverpassError as exc:
            raise HTTPException(status_code=502, detail=AREA_FAILED_DETAIL) from exc
    if loc.label:
        scene["address"] = loc.label
    return scene


def _iso(dt) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def _public(rec: Record) -> dict:
    return {"id": rec.id, "data": rec.data, "scene": rec.scene, "demo_for": rec.demo_for,
            "expires_at": _iso(rec.expires_at), "updated_at": _iso(rec.updated_at)}


def _load(store: PresentationStore, pid: str, *, allow_expired: bool = False) -> Record:
    rec = store.get(pid)
    if rec is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    if rec.expired() and not allow_expired:
        raise HTTPException(status_code=410, detail=GONE)
    return rec


def _editable(store: PresentationStore, pid: str, token: str | None) -> Record:
    # The owner can still open an expired demo (e.g. to copy it); only the public view goes away.
    rec = _load(store, pid, allow_expired=True)
    if not rec.token_ok(token):
        raise HTTPException(status_code=403, detail=BAD_TOKEN)
    return rec


def _validated(data: dict) -> dict:
    try:
        return PresentationData.model_validate(data).model_dump(mode="json")
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json(include_url=False))) from exc


@router.post("", status_code=201)
async def create(body: CreateIn, store: Store):
    if body.data.photos:
        raise HTTPException(status_code=422, detail="Upload photos after creating the presentation.")
    scene = await _scene_for(body.data.location, body.fixture)
    rec = store.create(body.data.model_dump(mode="json"), scene, body.demo_for, body.expires_in_days)
    return {"id": rec.id, "edit_token": rec.edit_token}


@router.get("/{pid}")
async def view(pid: str, store: Store):
    return _public(_load(store, pid))


@router.get("/{pid}/edit")
async def edit_view(pid: str, store: Store, token: Token = None):
    rec = _editable(store, pid, token)
    return {**_public(rec), "expired": rec.expired(), "source_url": rec.source_url, "leads": store.leads(pid),
            "ai": ai_features()}


@router.patch("/{pid}")
async def update(pid: str, patch: dict, store: Store, token: Token = None, fixture: bool = False):
    rec = _editable(store, pid, token)
    unknown = set(patch) - set(PresentationData.model_fields)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown fields: {', '.join(sorted(unknown))}")
    # A new location needs a new map. Build it before taking the row lock: it can take seconds.
    new_scene = None
    if "location" in patch:
        loc = Location.model_validate(_validated({**rec.data, "location": patch["location"]})["location"])
        if _location_key(loc.model_dump()) != _location_key(rec.data["location"]):
            new_scene = await _scene_for(loc, fixture)

    def change(current: Record) -> tuple[dict, dict | None]:
        merged = dict(patch)
        if "photos" in merged:
            merged["photos"] = _reordered_photos(current.data["photos"], merged["photos"])
        data = _validated({**current.data, **merged})
        scene = new_scene
        if scene is None and data["location"].get("label") != current.data["location"].get("label"):
            scene = {**current.scene, "address": data["location"].get("label") or current.scene.get("address")}
        return data, scene

    return _public(await asyncio.to_thread(store.mutate, pid, change))


def _reordered_photos(current: list[dict], wanted) -> list[dict]:
    """The editor may reorder photos and change captions, but not invent or drop them here."""
    if not isinstance(wanted, list):
        raise HTTPException(status_code=422, detail="photos must be a list")
    by_id = {p["id"]: p for p in current}
    ids = [p.get("id") if isinstance(p, dict) else None for p in wanted]
    if sorted(map(str, ids)) != sorted(by_id):
        raise HTTPException(status_code=422, detail="photos must list exactly the uploaded photos")
    return [{**by_id[p["id"]], "caption": p.get("caption")} for p in wanted]


@router.post("/{pid}/photos", status_code=201)
async def upload_photo(pid: str, store: Store, file: Annotated[UploadFile, File()], token: Token = None):
    rec = _editable(store, pid, token)
    if len(rec.data["photos"]) >= MAX_PHOTOS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_PHOTOS} photos.")
    raw = await file.read(MAX_PHOTO_BYTES + 1)
    try:
        large, thumb, w, h = await asyncio.to_thread(process_photo, raw)
    except PhotoError as exc:
        raise HTTPException(status_code=422, detail=f"Not a usable photo: {exc}") from exc
    photo_id = new_photo_id()
    folder = store.photo_dir(pid)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{photo_id}_large.jpg").write_bytes(large)
    (folder / f"{photo_id}_thumb.jpg").write_bytes(thumb)
    photo = Photo(id=photo_id, w=w, h=h).model_dump(mode="json")
    if not store.append_photo(pid, photo):
        for size in PHOTO_SIZES:
            (folder / f"{photo_id}_{size}.jpg").unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"At most {MAX_PHOTOS} photos.")
    return photo


@router.delete("/{pid}/photos/{photo_id}", status_code=204)
async def delete_photo(pid: str, photo_id: str, store: Store, token: Token = None):
    _editable(store, pid, token)
    if not store.remove_photo(pid, photo_id):
        raise HTTPException(status_code=404, detail="Photo not found.")
    for size in PHOTO_SIZES:
        (store.photo_dir(pid) / f"{photo_id}_{size}.jpg").unlink(missing_ok=True)
    return Response(status_code=204)


@router.get("/{pid}/photos/{photo_id}/{size}")
async def photo(pid: str, photo_id: str, size: str, store: Store):
    rec = _load(store, pid)
    if size not in PHOTO_SIZES or photo_id not in {p["id"] for p in rec.data["photos"]}:
        raise HTTPException(status_code=404, detail="Photo not found.")
    path = store.photo_dir(pid) / f"{photo_id}_{size}.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo not found.")
    # Photo ids are never reused, so the bytes behind a URL never change.
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})


class DraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transcript: Annotated[str, Field(max_length=ai.MAX_TRANSCRIPT_CHARS)] | None = None
    data: dict = {}  # the editor's current, possibly unsaved, form values


AI_OFF = "AI is not configured on this server."
AI_FAILED = "The AI provider did not answer usefully. Try again in a minute."


def ai_features() -> dict:
    cfg = get_config().ai
    return {"voice": bool(cfg.stt.base_url), "text": bool(cfg.llm.base_url and cfg.llm.model)}


@router.post("/{pid}/ai/transcribe")
async def transcribe(pid: str, store: Store, file: Annotated[UploadFile, File()], token: Token = None):
    _editable(store, pid, token)
    audio = await file.read(ai.MAX_AUDIO_BYTES + 1)
    if len(audio) > ai.MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="The recording is longer than the server accepts (25 MB).")
    if not audio:
        raise HTTPException(status_code=422, detail="The recording is empty.")
    try:
        text = await asyncio.to_thread(ai.transcribe, get_config().ai.stt, audio, file.filename or "audio.webm",
                                       file.content_type or "application/octet-stream")
    except ai.AiUnavailable as exc:
        raise HTTPException(status_code=503, detail=AI_OFF) from exc
    except ai.AiFailed as exc:
        raise HTTPException(status_code=502, detail=AI_FAILED) from exc
    return {"text": text}


@router.post("/{pid}/ai/draft")
async def draft(pid: str, body: DraftIn, store: Store, token: Token = None):
    rec = _editable(store, pid, token)
    if not body.transcript and not body.data.get("description") and not body.data.get("params"):
        raise HTTPException(status_code=422, detail="Nothing to write from: record notes or fill in some fields.")
    context = ai.sanitize_draft(body.data)  # the same field checks as the model's answer
    try:
        return await asyncio.to_thread(
            ai.draft_listing, get_config().ai.llm, transcript=body.transcript, data=context,
            address=rec.data["location"].get("label"), scene=rec.scene,
        )
    except ai.AiUnavailable as exc:
        raise HTTPException(status_code=503, detail=AI_OFF) from exc
    except ai.AiFailed as exc:
        raise HTTPException(status_code=502, detail=AI_FAILED) from exc


@router.post("/{pid}/leads", status_code=201)
async def add_lead(pid: str, lead: LeadIn, store: Store):
    _load(store, pid)
    if lead.website:  # honeypot filled: look successful, keep nothing
        return {"ok": True}
    store.add_lead(pid, lead)
    return {"ok": True}
