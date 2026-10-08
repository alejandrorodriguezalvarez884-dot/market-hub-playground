"""The service: the site and the API, from one origin.

    GET  /api/health
    GET  /api/me        who is signed in to Market Hub, and the hub's address
    GET  /api/catalog   the kinds of view, their ranges and the figures a table can show
    POST /api/chat      one turn: what the reader asks, the board as it stands -> the board after it
    POST /api/data      the figures a widget needs to be drawn

A board lives in the page that shows it: the service keeps nothing, about it or about its reader.
Everything else is the static site, when PLAYGROUND_STATIC_DIR points at its build.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .composer import ComposerFailed, ComposerUnavailable, default_composer
from .config import CHAT_PER_HOUR, DATA_PER_HOUR, HISTORY_TURNS, MAX_WIDGETS, MESSAGE_MAX, REPLY_MAX, TABLE_COLUMNS_MAX
from .data import resolve
from .hubauth import HubGate
from .hubauth import settings as hub_settings
from .market import MarketUnavailable, default_market
from .widgets import AVERAGES, KINDS, METRICS, STYLES, Invalid, apply, clean_board, normalize

log = logging.getLogger("playground.api")


class RateLimiter:
    """At most ``limit`` calls per reader in any ``window`` seconds. Per instance, in memory."""

    def __init__(self, limit: int, window: float = 3600.0):
        self.limit, self.window = limit, window
        self._calls: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, who: str) -> bool:
        now = time.monotonic()
        with self._lock:
            calls = self._calls[who]
            while calls and now - calls[0] > self.window:
                calls.popleft()
            if len(calls) >= self.limit:
                return False
            calls.append(now)
            return True


def _reader(request: Request) -> str:
    """Who asks: the signed-in user, or the address where there is no sign-in."""
    user = getattr(request.state, "user", None)
    if user:
        return f"user {user['id']}"
    # Cloud Run puts the caller first in X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def _failure(exc: Exception) -> HTTPException:
    """What the reader is told when something cannot be done. Upstream error bodies never reach
    the reader or the logs."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, ComposerUnavailable):
        return HTTPException(503, "The chat is not available right now. The board keeps working: ranges, sizes "
                                  "and order can still be changed by hand.")
    if isinstance(exc, ComposerFailed):
        return HTTPException(502, "That request could not be turned into a view. Try it in other words.")
    if isinstance(exc, MarketUnavailable):
        return HTTPException(503, "The market data provider is not available right now.")
    if isinstance(exc, anthropic.RateLimitError):
        return HTTPException(503, "The chat is busy. Try again in a moment.")
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APIStatusError)):
        log.warning("composer failure: %s", type(exc).__name__)
        return HTTPException(502, "The chat did not answer. Try again in a moment.")
    log.exception("request failed")
    return HTTPException(500, "Something failed. Try again in a moment.")


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(max_length=max(MESSAGE_MAX, REPLY_MAX))


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=MESSAGE_MAX)
    board: list[dict] = Field(default_factory=list, max_length=MAX_WIDGETS)
    history: list[Turn] = Field(default_factory=list, max_length=HISTORY_TURNS * 4)


class DataIn(BaseModel):
    widget: dict


def create_app(market=None, composer=None, static_dir: str | None = None, hub: tuple[str, str] | None | bool = True) -> FastAPI:
    """App factory. Tests pass their own pieces, so they need no network.

    ``hub`` is (hub URL, hub session secret) to admit only people signed in to Market Hub; by
    default it comes from HUB_URL and HUB_SESSION_SECRET, and None leaves the service open."""
    logging.basicConfig(level=logging.INFO)
    # yfinance prints what Yahoo answers when it has no such symbol; httpx logs every address asked.
    for noisy in ("httpx", "httpcore", "yfinance"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    app = FastAPI(title="Playground", docs_url=None, redoc_url=None, openapi_url=None)

    origins = [o.strip() for o in os.environ.get("PLAYGROUND_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"])
    hub = hub_settings() if hub is True else hub or None
    if hub:
        app.add_middleware(HubGate, hub_url=hub[0], secret=hub[1])

    market = market or default_market()
    composer = composer or default_composer()
    chatting, reading = RateLimiter(CHAT_PER_HOUR), RateLimiter(DATA_PER_HOUR)

    def allow(request: Request, limiter: RateLimiter) -> None:
        if not limiter.allow(_reader(request)):
            raise HTTPException(429, "Too many requests. Try again in an hour.")

    @app.middleware("http")
    async def no_store(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/me")
    def me(request: Request) -> dict:
        return {"user": getattr(request.state, "user", None), "hub": hub[0] if hub else None}

    @app.get("/api/catalog")
    def catalog() -> dict:
        return {
            "kinds": {name: {"ranges": list(spec["ranges"]), "tickers": list(spec["tickers"])} for name, spec in KINDS.items()},
            "metrics": [{"key": key, "label": label, "kind": kind} for key, (label, kind) in METRICS.items()],
            "styles": list(STYLES), "averages": list(AVERAGES),
            "limits": {"widgets": MAX_WIDGETS, "message": MESSAGE_MAX, "columns": TABLE_COLUMNS_MAX},
            "sample": bool(getattr(market, "sample", False)),
        }

    @app.post("/api/chat")
    def chat(body: ChatIn, request: Request) -> dict:
        allow(request, chatting)
        board = clean_board(body.board)
        try:
            turn = composer.turn(body.message.strip(), board, [t.model_dump() for t in body.history])
        except Exception as exc:
            raise _failure(exc) from None
        after, changed, problems = apply(board, turn["ops"])
        return {"reply": turn["reply"], "board": after, "changed": changed, "problems": problems}

    @app.post("/api/data")
    def data(body: DataIn, request: Request) -> dict:
        allow(request, reading)
        try:
            widget = normalize(body.widget, "w1")
        except Invalid as exc:
            raise HTTPException(400, str(exc)) from None
        try:
            return resolve(market, widget)
        except Exception as exc:
            raise _failure(exc) from None

    static_dir = static_dir or os.environ.get("PLAYGROUND_STATIC_DIR", "")
    if static_dir and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="site")
    return app
