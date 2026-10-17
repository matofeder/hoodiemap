"""Property presentations: validated listing data, a SQLite store, photo re-encoding."""
import io
import json
import secrets
import sqlite3
import threading
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

from PIL import Image, ImageOps
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
    created_at: str
    updated_at: str
    expires_at: str | None
    demo_for: str | None
    data: dict
    scene: dict

    def expired(self, now: datetime | None = None) -> bool:
        if not self.expires_at:
            return False
        return (now or datetime.now(timezone.utc)) >= datetime.fromisoformat(self.expires_at)

    def token_ok(self, token: str | None) -> bool:
        return bool(token) and secrets.compare_digest(token, self.edit_token)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS presentations (
  id TEXT PRIMARY KEY, edit_token TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  expires_at TEXT, demo_for TEXT, data TEXT NOT NULL, scene TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT, presentation_id TEXT NOT NULL REFERENCES presentations(id),
  created_at TEXT NOT NULL, name TEXT NOT NULL, email TEXT, phone TEXT, message TEXT
);
CREATE INDEX IF NOT EXISTS leads_by_presentation ON leads(presentation_id);
"""


class PresentationStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._db = self.root / "hoodiemap.db"
        self._lock = threading.Lock()
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db)
        con.row_factory = sqlite3.Row
        return con

    def photo_dir(self, pid: str) -> Path:
        return self.root / "photos" / pid

    def create(self, data: dict, scene: dict, demo_for: str | None = None,
               expires_in_days: int | None = None) -> Record:
        now = _now()
        expires = None
        if expires_in_days:
            expires = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat(timespec="seconds")
        rec = Record(secrets.token_urlsafe(9), secrets.token_urlsafe(24), now, now, expires, demo_for, data, scene)
        with self._lock, self._connect() as con:
            con.execute(
                "INSERT INTO presentations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (rec.id, rec.edit_token, rec.created_at, rec.updated_at, rec.expires_at, rec.demo_for,
                 json.dumps(data, ensure_ascii=False), json.dumps(scene, ensure_ascii=False)),
            )
        return rec

    def get(self, pid: str) -> Record | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM presentations WHERE id = ?", (pid,)).fetchone()
        if row is None:
            return None
        return Record(row["id"], row["edit_token"], row["created_at"], row["updated_at"], row["expires_at"],
                      row["demo_for"], json.loads(row["data"]), json.loads(row["scene"]))

    def update(self, pid: str, data: dict, scene: dict | None = None) -> None:
        with self._lock, self._connect() as con:
            if scene is None:
                con.execute("UPDATE presentations SET data = ?, updated_at = ? WHERE id = ?",
                            (json.dumps(data, ensure_ascii=False), _now(), pid))
            else:
                con.execute("UPDATE presentations SET data = ?, scene = ?, updated_at = ? WHERE id = ?",
                            (json.dumps(data, ensure_ascii=False), json.dumps(scene, ensure_ascii=False), _now(), pid))

    def add_lead(self, pid: str, lead: LeadIn) -> None:
        with self._lock, self._connect() as con:
            con.execute(
                "INSERT INTO leads (presentation_id, created_at, name, email, phone, message) VALUES (?, ?, ?, ?, ?, ?)",
                (pid, _now(), lead.name, lead.email, lead.phone, lead.message),
            )

    def leads(self, pid: str) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT created_at, name, email, phone, message FROM leads WHERE presentation_id = ? ORDER BY id DESC",
                (pid,),
            ).fetchall()
        return [dict(r) for r in rows]


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
