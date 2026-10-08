"""Sign-in through Market Hub.

With HUB_URL and HUB_SESSION_SECRET set, the service only answers people signed in to Market Hub.
It reads the hub's session cookie (``mh_session``, shared on the parent domain) and checks its
signature with the hub's secret. It never sets or changes that cookie and keeps nothing about the
user. Without the two settings the service is public, as before.
"""

from __future__ import annotations

import json
import os
from base64 import b64decode
from urllib.parse import quote, urlsplit

import itsdangerous
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

COOKIE = "mh_session"
MAX_AGE = 30 * 86400  # the hub's session length
# Served without a session: the health check and the site's static assets (no data in them).
OPEN = ("/api/health", "/_astro/", "/favicon.svg", "/robots.txt")


def settings() -> tuple[str, str] | None:
    hub = os.environ.get("HUB_URL", "").strip().rstrip("/")
    secret = os.environ.get("HUB_SESSION_SECRET", "").strip()
    return (hub, secret) if hub and secret else None


def read_user(cookie: str | None, secret: str, max_age: int = MAX_AGE) -> dict | None:
    """The user in a hub session cookie, or None if it is missing, forged or expired."""
    if not cookie:
        return None
    try:
        data = itsdangerous.TimestampSigner(secret).unsign(cookie.encode(), max_age=max_age)
        user = json.loads(b64decode(data)).get("user")
    except (itsdangerous.BadSignature, ValueError, TypeError, AttributeError):
        return None
    return user if isinstance(user, dict) and user.get("id") else None


class HubGate:
    """ASGI middleware: lets signed-in requests through with ``request.state.user``; sends the
    others to the hub's sign-in page (pages) or answers 401 (API)."""

    def __init__(self, app, hub_url: str, secret: str):
        self.app, self.hub, self.secret = app, hub_url.rstrip("/"), secret

    def signin_url(self, request: Request) -> str:
        """The hub's sign-in, coming back here afterwards. For an API call "here" is the page that
        made it (its Referer, when it is this same site), or the tool's home."""
        scheme = "https" if self.hub.startswith("https:") else request.url.scheme
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        if request.url.path.startswith("/api/"):
            referer = request.headers.get("referer", "")
            here = referer if urlsplit(referer).netloc == host else f"{scheme}://{host}/"
        else:
            here = f"{scheme}://{host}{request.url.path}" + (f"?{request.url.query}" if request.url.query else "")
        return f"{self.hub}/signin/?next={quote(here, safe='')}"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].startswith(OPEN):
            return await self.app(scope, receive, send)
        request = Request(scope)
        user = read_user(request.cookies.get(COOKIE), self.secret)
        if user:
            scope.setdefault("state", {})["user"] = user
            return await self.app(scope, receive, send)
        if scope["path"].startswith("/api/"):
            response = JSONResponse({"detail": "Sign in to Market Hub to use this tool.", "signin": self.signin_url(request)},
                                    status_code=401)
        else:
            response = RedirectResponse(self.signin_url(request), status_code=302)
        response.headers["Cache-Control"] = "no-store"
        return await response(scope, receive, send)
