"""Constant-time token and replay-window HMAC authentication helpers."""

import hashlib
import hmac
import time

from fastapi import HTTPException, Request

from syncmesh.core.settings import Settings


def require_admin(request: Request) -> None:
    """Require a configured bearer token outside the trusted development mode."""
    settings: Settings = request.app.state.settings
    if settings.admin_token is None:
        if settings.environment == "dev":
            return
        raise HTTPException(status_code=503, detail="admin authentication is not configured")
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    expected = settings.admin_token.get_secret_value()
    if scheme.lower() != "bearer" or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="invalid admin credentials")


async def require_peer(request: Request) -> None:
    """Verify the timestamped HMAC of the exact request body from a peer."""
    settings: Settings = request.app.state.settings
    if settings.peer_secret is None:
        if settings.environment == "dev":
            return
        raise HTTPException(status_code=503, detail="peer authentication is not configured")

    timestamp = request.headers.get("x-syncmesh-timestamp", "")
    signature = request.headers.get("x-syncmesh-signature", "")
    try:
        sent_at = int(timestamp)
    except ValueError as error:
        raise HTTPException(status_code=401, detail="invalid peer timestamp") from error
    if abs(int(time.time()) - sent_at) > settings.peer_auth_window_seconds:
        raise HTTPException(
            status_code=401, detail="peer request timestamp is outside the allowed window"
        )
    body = await request.body()
    message = timestamp.encode("ascii") + b"." + body
    expected = hmac.new(
        settings.peer_secret.get_secret_value().encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="invalid peer signature")
