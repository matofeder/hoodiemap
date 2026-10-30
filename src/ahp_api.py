"""/api/ahp: the expert panel questionnaire behind the score weights (see src/ahp.py, methodology/weights.json).

Experts answer at /ahp with a panel code; every answer is checked for consistency on the spot. The admin
sees the group weights per set and downloads them as methodology/weights.json, which is committed: the
weights a score uses are always a versioned file, never live database state.
"""
import os
import secrets
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import ahp
import score_method as M
from admin import check_admin
from landing_api import Pool

router = APIRouter(prefix="/api/ahp")
PANEL_CODE_ENV = "HOODIEMAP_AHP_CODE"


def _set(set_id: str) -> dict:
    if set_id not in M.AHP_SETS:
        raise HTTPException(status_code=404, detail=f"Unknown criteria set {set_id}.")
    return M.AHP_SETS[set_id]


class CheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    set_id: str
    judgments: dict[str, float]


class Expert(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Annotated[str, Field(min_length=2, max_length=120)]
    role: Annotated[str, Field(min_length=2, max_length=120)]


class ResponseIn(CheckIn):
    code: str
    expert: Expert


def _weigh(body: CheckIn) -> ahp.Result:
    criteria = list(_set(body.set_id)["criteria"])
    try:
        return ahp.weigh(criteria, body.judgments)
    except ahp.AHPError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _result(r: ahp.Result) -> dict:
    return {"weights": {k: round(v, 4) for k, v in r.weights.items()}, "lambda_max": round(r.lambda_max, 4),
            "ci": round(r.ci, 4), "cr": round(r.cr, 4), "consistent": r.consistent}


@router.get("/sets")
async def sets():
    return {"sets": {sid: {"title": s["title"], "criteria": s["criteria"], "pairs": ahp.pairs(list(s["criteria"]))}
                     for sid, s in M.AHP_SETS.items()},
            "scale_labels": ahp.SCALE_LABELS, "cr_limit": ahp.CR_LIMIT}


@router.post("/check")
async def check(body: CheckIn):
    return _result(_weigh(body))


@router.post("/responses", status_code=201)
async def respond(body: ResponseIn, pool: Pool):
    expected = os.environ.get(PANEL_CODE_ENV)
    if not expected:
        raise HTTPException(status_code=503, detail=f"The panel is closed: set {PANEL_CODE_ENV} on the server.")
    if not secrets.compare_digest(body.code, expected):
        raise HTTPException(status_code=403, detail="Wrong panel code.")
    r = _weigh(body)
    from psycopg.types.json import Jsonb
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO ahp_responses (set_id, expert_name, expert_role, judgments, cr, consistent) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (body.set_id, body.expert.name, body.expert.role, Jsonb(body.judgments), r.cr, r.consistent),
        )
    return _result(r)


@router.get("/results")
async def results(pool: Pool, admin: Annotated[str | None, Header(alias="X-Admin-Token")] = None):
    """Per set: every expert's latest answer, the group weights from the consistent ones, and weights.json."""
    check_admin(admin)
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ON (set_id, lower(expert_name)) set_id, expert_name, expert_role, judgments, created_at "
            "FROM ahp_responses ORDER BY set_id, lower(expert_name), id DESC").fetchall()
    out, file_sets = {}, {}
    for set_id, spec in M.AHP_SETS.items():
        criteria = list(spec["criteria"])
        answers = [r for r in rows if r["set_id"] == set_id]
        g = ahp.group(criteria, [a["judgments"] for a in answers]) if answers else None
        experts = [{"name": a["expert_name"], "role": a["expert_role"], "date": a["created_at"].date().isoformat(),
                    **_result(g.individual[i])} for i, a in enumerate(answers)] if g else []
        group = _result(g.result) if g and g.result else None
        out[set_id] = {"title": spec["title"], "criteria": spec["criteria"], "experts": experts,
                       "used": len(g.used) if g else 0, "group": group}
        if group:
            file_sets[set_id] = {"weights": group["weights"], "method": "ahp", "panel": {
                "experts": len(g.used), "excluded_inconsistent": len(answers) - len(g.used), "cr": group["cr"],
                "roles": sorted({experts[i]["role"] for i in g.used}), "date": date.today().isoformat(),
                "aggregation": "geometric mean of judgments (AIJ), principal eigenvector, Saaty RI"}}
    return {"sets": out, "weights_json": {"version": M.VERSION, "sets": file_sets}}
