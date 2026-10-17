"""/api/landing: the "Prever si byt pred kúpou" demand test behind /prever.

Counts page views and clicks on the call to action (no cookies, nothing personal) and collects
e-mails from people who want the report. Stats and the CSV export need the admin token.
"""
import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from admin import check_admin
from config import get_config
from presentation_api import Store

router = APIRouter(prefix="/api/landing")
Tag = Annotated[str, Field(max_length=60, pattern=r"^[\w.\-]*$")]
CLOSED = "Sign-ups are not open: set landing.operator and landing.contact_email in config.yaml."


def get_pool(store: Store) -> ConnectionPool:
    return store.pool  # one pool for the app; going through the store keeps test overrides working


Pool = Annotated[ConnectionPool, Depends(get_pool)]
Admin = Annotated[str | None, Header(alias="X-Admin-Token")]


def _landing():
    return get_config().landing


def _is_open() -> bool:
    cfg = _landing()
    return bool(cfg.operator and cfg.contact_email)


class Tags(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    variant: Annotated[str, Field(max_length=10)]
    source: Tag | None = None
    campaign: Tag | None = None

    @field_validator("variant")
    @classmethod
    def _known_variant(cls, v):
        if v not in _landing().price_variants:
            raise ValueError("unknown variant")
        return v

    @field_validator("source", "campaign", mode="before")
    @classmethod
    def _blank(cls, v):
        return None if isinstance(v, str) and not v.strip() else v


class EventIn(Tags):
    kind: Literal["view", "cta"]


class SignupIn(Tags):
    email: Annotated[str, Field(max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    timeframe: Literal["3m", "12m", "browsing"] | None = None
    listing_url: Annotated[str, Field(max_length=500, pattern=r"^https?://\S+$")] | None = None
    consent: bool
    website: str | None = None  # honeypot

    @field_validator("listing_url", "timeframe", mode="before")
    @classmethod
    def _blank_optional(cls, v):
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("consent")
    @classmethod
    def _consented(cls, v):
        if not v:
            raise ValueError("consent is required")
        return v


@router.get("")
async def info():
    cfg = _landing()
    return {"open": _is_open(), "operator": cfg.operator, "contact_email": cfg.contact_email,
            "variants": cfg.price_variants}


@router.post("/event", status_code=204)
async def event(body: EventIn, pool: Pool):
    with pool.connection() as conn:
        conn.execute("INSERT INTO landing_events (kind, variant, source, campaign) VALUES (%s, %s, %s, %s)",
                     (body.kind, body.variant, body.source, body.campaign))
    return Response(status_code=204)


@router.post("/signup", status_code=201)
async def signup(body: SignupIn, pool: Pool):
    if not _is_open():
        raise HTTPException(status_code=503, detail=CLOSED)
    if body.website:  # bots fill the hidden field: look fine, keep nothing
        return {"ok": True}
    with pool.connection() as conn:
        # The same answer for a repeated address, so the form doesn't reveal who already signed up.
        conn.execute(
            "INSERT INTO waitlist (email, timeframe, listing_url, variant, source, campaign) "
            "VALUES (lower(%s), %s, %s, %s, %s, %s) ON CONFLICT (email) DO NOTHING",
            (body.email, body.timeframe, body.listing_url, body.variant, body.source, body.campaign),
        )
    return {"ok": True}


@router.get("/stats")
async def stats(pool: Pool, admin: Admin = None):
    check_admin(admin)
    with pool.connection() as conn:
        events = conn.execute(
            "SELECT variant, coalesce(source, '') AS source, kind, count(*) AS n FROM landing_events "
            "GROUP BY 1, 2, 3").fetchall()
        signups = conn.execute(
            "SELECT variant, coalesce(source, '') AS source, count(*) AS n, "
            "count(*) FILTER (WHERE timeframe = '3m') AS soon, count(listing_url) AS with_listing "
            "FROM waitlist GROUP BY 1, 2").fetchall()
    rows: dict[tuple[str, str], dict] = {}

    def row(variant, source):
        return rows.setdefault((variant, source), {"variant": variant, "source": source or None, "views": 0,
                                                   "cta": 0, "signups": 0, "soon": 0, "with_listing": 0})
    for e in events:
        row(e["variant"], e["source"])["views" if e["kind"] == "view" else "cta"] = e["n"]
    for s in signups:
        r = row(s["variant"], s["source"])
        r.update(signups=s["n"], soon=s["soon"], with_listing=s["with_listing"])
    out = sorted(rows.values(), key=lambda r: (r["variant"], r["source"] or ""))
    totals = {k: sum(r[k] for r in out) for k in ("views", "cta", "signups", "soon", "with_listing")}
    return {"rows": out, "totals": totals}


@router.get("/export.csv")
async def export(pool: Pool, admin: Admin = None):
    check_admin(admin)
    with pool.connection() as conn:
        rows = conn.execute("SELECT created_at, email, timeframe, listing_url, variant, source, campaign "
                            "FROM waitlist ORDER BY id").fetchall()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["created_at", "email", "timeframe", "listing_url", "variant", "source", "campaign"])
    for r in rows:
        writer.writerow([r["created_at"].isoformat(timespec="seconds"), r["email"], r["timeframe"] or "",
                         r["listing_url"] or "", r["variant"], r["source"] or "", r["campaign"] or ""])
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="prever-waitlist.csv"'})
