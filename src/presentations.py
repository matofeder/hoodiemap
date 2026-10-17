"""Property presentations: validated listing data, the Postgres store, photo re-encoding."""
import io
import secrets
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

from PIL import Image, ImageOps
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_PHOTOS = 40
MAX_PHOTO_BYTES = 15 * 1024 * 1024
LARGE_PX = 2000
THUMB_PX = 600
_FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = 60_000_000  # a phone photo is ~12–50 Mpx; above this is a decompression bomb

Short = Annotated[str, Field(max_length=200)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Location(_Model):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tier: Literal["address", "street", "city"] = "address"
    name: Short | None = None
    label: Short | None = None


class Params(_Model):
    property_type: Literal["flat", "house", "land", "other"] | None = None
    rooms: int | None = Field(default=None, ge=0, le=50)
    area_m2: float | None = Field(default=None, gt=0, le=100_000)
    land_m2: float | None = Field(default=None, gt=0, le=10_000_000)
    floor: int | None = Field(default=None, ge=-5, le=200)
    floors_total: int | None = Field(default=None, ge=1, le=200)
    condition: Literal["new", "renovated", "partly_renovated", "original", "under_construction"] | None = None
    energy_class: Literal["A0", "A1", "A", "B", "C", "D", "E", "F", "G"] | None = None
    year_built: int | None = Field(default=None, ge=1000, le=2100)
    features: list[Literal["balcony", "loggia", "terrace", "elevator", "cellar", "parking", "garage", "garden"]] = []


class Agent(_Model):
    name: Short | None = None
    phone: Annotated[str, Field(max_length=40)] | None = None
    email: Short | None = None
    agency: Short | None = None


class Photo(_Model):
    id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{8,32}$")]
    w: int
    h: int
    caption: Short | None = None


class PresentationData(_Model):
    location: Location
    title: Short | None = None
    offer: Literal["sale", "rent"] = "sale"
    price_eur: float | None = Field(default=None, ge=0, le=1_000_000_000)
    price_note: Short | None = None
    params: Params = Field(default_factory=Params)
    description: Annotated[str, Field(max_length=10_000)] | None = None
    tour_url: Annotated[str, Field(max_length=500, pattern=r"^https://\S+$")] | None = None  # 3D tour (Matterport…)
    agent: Agent = Field(default_factory=Agent)
    photos: list[Photo] = Field(default=[], max_length=MAX_PHOTOS)


class LeadIn(_Model):
    name: Annotated[str, Field(min_length=1, max_length=100)]
    email: Annotated[str, Field(max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")] | None = None
    phone: Annotated[str, Field(max_length=40, pattern=r"^[0-9+()\s/-]{6,40}$")] | None = None
    message: Annotated[str, Field(max_length=2000)] | None = None
    consent: bool
    website: str | None = None  # honeypot: people never see it, bots fill it

    @field_validator("email", "phone", "message", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v

    @model_validator(mode="after")
    def _reachable(self):
        if not self.consent:
            raise ValueError("consent is required")
        if not self.email and not self.phone:
            raise ValueError("an e-mail or a phone is required")
        return self


@dataclass
class Record:
    id: str
    edit_token: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    demo_for: str | None
    source_url: str | None
    data: dict
    scene: dict

    def expired(self, now: datetime | None = None) -> bool:
        return self.expires_at is not None and (now or datetime.now(timezone.utc)) >= self.expires_at

    def token_ok(self, token: str | None) -> bool:
        return bool(token) and secrets.compare_digest(token, self.edit_token)


_COLUMNS = "id, edit_token, created_at, updated_at, expires_at, demo_for, source_url, data, scene"


class PresentationStore:
    """Presentations and leads in Postgres (see migrations/); photo files under `photo_root`."""

    def __init__(self, pool: ConnectionPool, photo_root: str | Path):
        self.pool = pool
        self.photo_root = Path(photo_root)

    def photo_dir(self, pid: str) -> Path:
        return self.photo_root / "photos" / pid

    def create(self, data: dict, scene: dict, demo_for: str | None = None,
               expires_in_days: int | None = None, source_url: str | None = None) -> Record:
        expires = datetime.now(timezone.utc) + timedelta(days=expires_in_days) if expires_in_days else None
        with self.pool.connection() as conn:
            row = conn.execute(
                f"INSERT INTO presentations (id, edit_token, expires_at, demo_for, source_url, data, scene) "
                f"VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING {_COLUMNS}",
                (secrets.token_urlsafe(9), secrets.token_urlsafe(24), expires, demo_for, source_url,
                 Jsonb(data), Jsonb(scene)),
            ).fetchone()
        return Record(**row)

    def get(self, pid: str) -> Record | None:
        with self.pool.connection() as conn:
            row = conn.execute(f"SELECT {_COLUMNS} FROM presentations WHERE id = %s", (pid,)).fetchone()
        return Record(**row) if row else None

    def mutate(self, pid: str, change: Callable[[Record], tuple[dict, dict | None]]) -> Record | None:
        """Read-modify-write under a row lock: `change` gets the current record, returns (data, scene or None)."""
        with self.pool.connection() as conn, conn.transaction():
            row = conn.execute(f"SELECT {_COLUMNS} FROM presentations WHERE id = %s FOR UPDATE", (pid,)).fetchone()
            if row is None:
                return None
            data, scene = change(Record(**row))
            row = conn.execute(
                f"UPDATE presentations SET data = %s, scene = COALESCE(%s, scene), updated_at = now() "
                f"WHERE id = %s RETURNING {_COLUMNS}",
                (Jsonb(data), Jsonb(scene) if scene is not None else None, pid),
            ).fetchone()
        return Record(**row)

    def append_photo(self, pid: str, photo: dict, max_photos: int = MAX_PHOTOS) -> bool:
        """Atomic append; False when the presentation is gone or already has `max_photos`."""
        with self.pool.connection() as conn:
            row = conn.execute(
                "UPDATE presentations SET data = jsonb_set(data, '{photos}', data->'photos' || %s), updated_at = now() "
                "WHERE id = %s AND jsonb_array_length(data->'photos') < %s RETURNING id",
                (Jsonb([photo]), pid, max_photos),
            ).fetchone()
        return row is not None

    def remove_photo(self, pid: str, photo_id: str) -> bool:
        with self.pool.connection() as conn:
            row = conn.execute(
                "UPDATE presentations SET data = jsonb_set(data, '{photos}', COALESCE("
                "  (SELECT jsonb_agg(p ORDER BY n) FROM jsonb_array_elements(data->'photos') WITH ORDINALITY AS t(p, n)"
                "   WHERE p->>'id' <> %s), '[]'::jsonb)), updated_at = now() "
                "WHERE id = %s AND data->'photos' @> %s RETURNING id",
                (photo_id, pid, Jsonb([{"id": photo_id}])),
            ).fetchone()
        return row is not None

    def add_lead(self, pid: str, lead: LeadIn) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                "INSERT INTO leads (presentation_id, name, email, phone, message) VALUES (%s, %s, %s, %s, %s)",
                (pid, lead.name, lead.email, lead.phone, lead.message),
            )

    def leads(self, pid: str) -> list[dict]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT created_at, name, email, phone, message FROM leads WHERE presentation_id = %s ORDER BY id DESC",
                (pid,),
            ).fetchall()
        return [{**r, "created_at": r["created_at"].isoformat(timespec="seconds")} for r in rows]


class PhotoError(ValueError):
    """The upload is not a usable JPEG, PNG or WebP photo."""


def _jpeg(img: Image.Image, px: int) -> bytes:
    copy = img.copy()
    copy.thumbnail((px, px), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    copy.save(out, "JPEG", quality=84, optimize=True, progressive=True)
    return out.getvalue()


def process_photo(raw: bytes) -> tuple[bytes, bytes, int, int]:
    """Re-encode an upload: EXIF orientation applied, metadata dropped. Returns (large, thumb, w, h)."""
    if len(raw) > MAX_PHOTO_BYTES:
        raise PhotoError("too large")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(raw))
            if img.format not in _FORMATS:
                raise PhotoError(f"unsupported format {img.format}")
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
    except PhotoError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise PhotoError("image too large") from exc
    except Exception as exc:  # Pillow raises many types for broken input
        raise PhotoError("not an image") from exc
    large = _jpeg(img, LARGE_PX)
    w, h = Image.open(io.BytesIO(large)).size
    return large, _jpeg(img, THUMB_PX), w, h


def new_photo_id() -> str:
    return secrets.token_urlsafe(9)
