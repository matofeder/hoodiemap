"""The admin token: imports always need it; creating presentations needs it once it is set (public servers)."""
import os
import secrets

from fastapi import HTTPException

ADMIN_TOKEN_ENV = "HOODIEMAP_ADMIN_TOKEN"


def admin_token() -> str | None:
    return os.environ.get(ADMIN_TOKEN_ENV) or None


def check_admin(token: str | None, *, required: bool = True) -> None:
    """`required=False`: without a configured token (local development) everyone passes."""
    expected = admin_token()
    if not expected:
        if required:
            raise HTTPException(status_code=503, detail=f"Import is off: set {ADMIN_TOKEN_ENV} on the server.")
        return
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Wrong admin token.")
