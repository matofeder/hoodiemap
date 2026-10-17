"""/api/import: turn one public nehnutelnosti.sk listing into a demo presentation (admin only)."""
import asyncio
import logging
import os
import secrets
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import listing_import
from geocode import GeocodeUnavailable, get_geocoder
from presentation_api import Store, _scene_for
from presentations import Location, PhotoError, Photo, PresentationData, new_photo_id, process_photo

logger = logging.getLogger(__name__)

ADMIN_TOKEN_ENV = "HOODIEMAP_ADMIN_TOKEN"
router = APIRouter(prefix="/api/import")


class ImportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: Annotated[str, Field(max_length=500)]
    demo_for: Annotated[str, Field(max_length=200)] | None = None  # default: the listing's agency
    expires_in_days: Annotated[int, Field(ge=1, le=365)] = 30
    fixture: bool = False  # offline: the fixture map instead of Overpass, no geocoding


def _check_admin(token: str | None) -> None:
    expected = os.environ.get(ADMIN_TOKEN_ENV)
    if not expected:
        raise HTTPException(status_code=503, detail=f"Import is off: set {ADMIN_TOKEN_ENV} on the server.")
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Wrong admin token.")


def _locate(listing: listing_import.ImportedListing, fixture: bool) -> tuple[dict, list[str]]:
    """Exact coordinates from the geocoder when the listing has a house number, else the portal's point."""
    loc, notes = dict(listing.data["location"]), []
    if listing.address_query and not fixture:
        try:
            hit = get_geocoder().search(listing.address_query)
        except GeocodeUnavailable:
            hit = None
        if hit and hit.get("tier") == "address":
            return {**loc, "lat": hit["lat"], "lon": hit["lon"]}, notes
        notes.append("Adresu sa nepodarilo presne nájsť, mapa je podľa polohy z portálu (± 200 m).")
    if listing.point is None:
        raise HTTPException(status_code=422, detail="The listing has no usable location.")
    return {**loc, "lat": listing.point[0], "lon": listing.point[1]}, notes


def _import_photos(store, pid: str, urls: list[str]) -> tuple[int, int]:
    saved = failed = 0
    folder = store.photo_dir(pid)
    folder.mkdir(parents=True, exist_ok=True)
    for url in urls:
        try:
            large, thumb, w, h = process_photo(listing_import.fetch_photo(url))
        except (PhotoError, Exception) as exc:  # one broken photo must not stop the import
            logger.warning("Photo import failed for %s: %s", url, exc)
            failed += 1
            continue
        photo_id = new_photo_id()
        (folder / f"{photo_id}_large.jpg").write_bytes(large)
        (folder / f"{photo_id}_thumb.jpg").write_bytes(thumb)
        if store.append_photo(pid, Photo(id=photo_id, w=w, h=h).model_dump(mode="json")):
            saved += 1
        else:
            failed += 1
    return saved, failed


@router.post("", status_code=201)
async def import_listing(body: ImportIn, store: Store, admin: Annotated[str | None, Header(alias="X-Admin-Token")] = None):
    _check_admin(admin)
    try:
        url = listing_import.check_url(body.url)
        html = await asyncio.to_thread(listing_import.fetch, url)
        listing = listing_import.parse(html, url)
    except listing_import.ImportError_ as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    location, notes = await asyncio.to_thread(_locate, listing, body.fixture)
    try:
        data = PresentationData.model_validate({**listing.data, "location": location}).model_dump(mode="json")
    except ValidationError as exc:
        logger.warning("Imported listing failed validation: %s", exc)
        raise HTTPException(status_code=422, detail="The listing data could not be read cleanly.") from exc
    scene = await _scene_for(Location.model_validate(location), body.fixture)
    rec = store.create(data, scene, body.demo_for or listing.agency, body.expires_in_days, source_url=url)
    saved, failed = await asyncio.to_thread(_import_photos, store, rec.id, listing.photo_urls)
    warnings = listing.warnings + notes
    if failed:
        warnings.append(f"{failed} fotiek sa nepodarilo prevziať.")
    return {"id": rec.id, "edit_token": rec.edit_token, "title": data["title"], "label": location.get("label"),
            "demo_for": rec.demo_for, "photos": saved, "warnings": warnings}
