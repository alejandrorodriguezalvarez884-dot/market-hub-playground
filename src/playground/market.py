"""Market data from Yahoo Finance, read with the yfinance library.

It takes no key and has no daily quota, but it is not an official API: yfinance asks the addresses
Yahoo's own pages ask, and Yahoo can refuse an address that asks too much (or a data centre's).
So a symbol is read in one request (five years of daily bars, whose last one is today's), the
answer is kept in memory, and after a refusal nothing is asked for a while. Nothing is sent to
Yahoo but symbols.

``SampleMarket`` answers the same questions with figures the code makes up, the same every time,
for tests and for a developer's machine (PLAYGROUND_SAMPLE=1). Its answers are marked as such.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import random
import threading
import time
from datetime import date, timedelta
from typing import Any

from .config import FAILED_SECONDS, PROFILE_TTL_SECONDS, QUOTE_TTL_SECONDS, REFUSED_SECONDS

log = logging.getLogger("playground.market")


class MarketUnavailable(Exception):
    """The provider did not answer. Says nothing of the symbol asked."""


class TTLCache:
    def __init__(self):
        self._items: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, ttl: float) -> Any | None:
        with self._lock:
            hit = self._items.get(key)
            if hit and time.monotonic() - hit[0] < ttl:
                return hit[1]
            return None

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._items[key] = (time.monotonic(), value)


def _num(v: Any) -> float | None:
    try:
        v = None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None
    return v if v is not None and v == v else None  # NaN: no figure


def _rows(frame):
    """(timestamp, open, high, low, close, volume) for each bar of a yfinance table that has a close."""
    if frame is None or getattr(frame, "empty", True):
        return
    columns = [frame[c].tolist() for c in ("Open", "High", "Low", "Close", "Volume")]
    for ts, o, h, lo, c, v in zip(frame.index, *columns):
        c = _num(c)
        if c is None:  # a day without a trade
            continue
        o, h, lo = (_num(x) or c for x in (o, h, lo))
        yield ts, o, h, lo, c, int(_num(v) or 0)


class Yahoo:
    sample = False

    def __init__(self, yf=None):
        self._yf = yf  # the yfinance module; tests pass a stand-in
        self._reads = TTLCache()  # symbol -> {"bars": daily bars, oldest first, "name": ...}
        self._facts = TTLCache()
        self._quiet_until = 0.0
        self._lock = threading.Lock()

    @property
    def yf(self):
        with self._lock:
            if self._yf is None:
                import yfinance  # slow to import (pandas): only when the first price is asked for

                try:
                    yfinance.config.debug.hide_exceptions = False  # a missing ticker raises instead of printing
                except AttributeError:
                    pass
                self._yf = yfinance
            return self._yf

    def _call(self, what: str, ask):
        """One question to Yahoo. None when Yahoo has no such symbol."""
        if time.monotonic() < self._quiet_until:
            raise MarketUnavailable("The market data provider is not answering for now.")
        yf = self.yf
        try:
            got = ask(yf)
        except Exception as exc:  # yfinance raises its own errors and those of the HTTP library under it
            kind = type(exc).__name__
            if "Missing" in kind:
                log.info("yahoo %s -> no such symbol", what)
                return None
            self._quiet_until = time.monotonic() + (REFUSED_SECONDS if "RateLimit" in kind else FAILED_SECONDS)
            # The error's name only: its text can carry the address that was asked.
            log.warning("yahoo %s -> %s", what, kind)
            raise MarketUnavailable("The market data provider did not answer.") from None
        log.info("yahoo %s -> ok", what)
        return got

    def read(self, symbol: str) -> dict:
        """A symbol's name and its daily bars, oldest first (time, open, high, low, close, volume),
        the last one today's. No bars when Yahoo has no such symbol."""
        key = symbol.upper()
        hit = self._reads.get(key, QUOTE_TTL_SECONDS)
        if hit is not None:
            return hit

        def ask(yf):
            ticker = yf.Ticker(key)
            frame = ticker.history(period="5y", interval="1d", auto_adjust=False, actions=False)
            return frame, dict(getattr(ticker, "history_metadata", None) or {})

        got = self._call(f"bars {key}", ask)
        bars = [{"time": ts.strftime("%Y-%m-%d"), "open": o, "high": h, "low": lo, "close": c, "volume": v}
                for ts, o, h, lo, c, v in _rows(got[0])] if got else []
        meta = got[1] if got else {}
        read = {"ticker": key, "name": str(meta.get("longName") or meta.get("shortName") or key), "bars": bars}
        self._reads.put(key, read)
        return read

    def profile(self, symbol: str) -> dict:
        """Facts about a company or a fund that do not come with its bars. Empty for a symbol
        Yahoo has none for."""
        key = symbol.upper()
        hit = self._facts.get(key, PROFILE_TTL_SECONDS)
        if hit is not None:
            return hit
        info = self._call(f"facts {key}", lambda yf: dict(yf.Ticker(key).info or {})) or {}
        facts = {"sector": info.get("sector") or "", "market_cap": _num(info.get("marketCap")),
                 "pe": _num(info.get("trailingPE")), "forward_pe": _num(info.get("forwardPE")),
                 "beta": _num(info.get("beta")) or _num(info.get("beta3Year")),
                 # What a share pays in a year: the declared rate, or for a fund what it paid in the last one.
                 "dividend": _num(info.get("dividendRate")) or _num(info.get("trailingAnnualDividendRate"))}
        self._facts.put(key, facts)
        return facts


# --- Figures made up by the code -------------------------------------------------------------------

SAMPLE_SECTORS = ("Technology", "Healthcare", "Financial Services", "Energy", "Industrials", "Consumer Defensive")
SAMPLE_BARS = 1300  # about five years of sessions
SAMPLE_EPOCH = date(2019, 1, 1)
# Symbols the sample market does not know, so that "no such symbol" can be seen on a developer's machine.
SAMPLE_UNKNOWN = ("NOPE", "ZZZZ")


class SampleMarket:
    """A random walk per symbol, seeded by the symbol: the same bars on every run, one more each
    weekday."""

    sample = True

    def __init__(self, today: date | None = None):
        self._today = today
        self._reads: dict[tuple[str, date], dict] = {}

    def _rng(self, key: str) -> random.Random:
        return random.Random(int(hashlib.sha256(key.encode()).hexdigest()[:12], 16))

    def read(self, symbol: str) -> dict:
        key = symbol.upper()
        if key in SAMPLE_UNKNOWN:
            return {"ticker": key, "name": key, "bars": []}
        today = self._today or date.today()
        if (key, today) in self._reads:
            return self._reads[key, today]
        rng = self._rng(key)
        drift, swing = rng.uniform(-0.0002, 0.0008), rng.uniform(0.008, 0.028)
        close, bars, day = rng.uniform(20, 400), [], SAMPLE_EPOCH
        # The walk always starts on the same day and each day's move is seeded by the symbol and
        # the day, so history never changes.
        while day <= today:
            if day.weekday() < 5:
                step = self._rng(f"{key} {day.isoformat()}")
                before, close = close, close * math.exp(step.gauss(drift, swing))
                reach = abs(step.gauss(0, swing / 2)) * close
                bars.append({"time": day.isoformat(), "open": round(before, 2), "high": round(max(before, close) + reach, 2),
                             "low": round(min(before, close) - reach, 2), "close": round(close, 2),
                             "volume": int(step.uniform(2e6, 6e7))})
            day += timedelta(days=1)
        read = {"ticker": key, "name": f"{key} (sample)", "bars": bars[-SAMPLE_BARS:]}
        self._reads[key, today] = read
        return read

    def profile(self, symbol: str) -> dict:
        rng = self._rng(f"{symbol.upper()} facts")
        return {"sector": rng.choice(SAMPLE_SECTORS), "market_cap": round(rng.uniform(5e9, 2e12)), "pe": round(rng.uniform(8, 45), 1),
                "forward_pe": round(rng.uniform(8, 35), 1), "beta": round(rng.uniform(0.5, 1.8), 2), "dividend": round(rng.uniform(0, 4), 2)}


def default_market():
    return SampleMarket() if os.environ.get("PLAYGROUND_SAMPLE", "") == "1" else Yahoo()
