"""What a board is made of: the kinds of widget, what each one takes, and the changes one turn of
the chat can make to a board.

Everything that reaches here is untrusted (the model's answer, the board the browser sends back):
it is checked and put in its one shape, or left out. A widget says what to show and never carries
a figure: those are worked out by ``data.py`` when the page asks.

    {"id": "w1", "type": "price",   "tickers": ["NVDA"], "range": "1Y", "style": "candles", "averages": [50, 200], ...}
    {"id": "w2", "type": "compare", "tickers": ["AAPL", "MSFT"], "range": "2Y", ...}
    {"id": "w3", "type": "ruler",   "tickers": ["XLK", "XLE", ...], "range": "1D", ...}
    {"id": "w4", "type": "table",   "tickers": ["JPM", "BAC"], "columns": ["price", "ret_1y"], ...}

and every one has ``size`` ("s", "m", "l") and ``title`` (empty: the page titles it from its contents).
"""

from __future__ import annotations

import re

from .advice import unfit
from .config import MAX_WIDGETS, OPS_MAX, TABLE_COLUMNS_MAX, TITLE_MAX

# The stretch of time a chart covers, and the period a move is measured over.
WINDOWS = ("1M", "3M", "6M", "YTD", "1Y", "2Y", "5Y")
PERIODS = ("1D", "1W", "1M", "3M", "6M", "YTD", "1Y")
RANGES = ("1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "2Y", "5Y")
SIZES = ("s", "m", "l")
STYLES = ("candles", "line")
AVERAGES = (20, 50, 200)  # moving averages a price chart can carry, in sessions

# The figures a table can show: its label and how the page writes it (site/src/lib/format.ts).
METRICS = {
    "price": ("Price", "price"),
    "change_1d": ("Day", "spct"),
    "ret_1w": ("1 week", "spct"),
    "ret_1m": ("1 month", "spct"),
    "ret_3m": ("3 months", "spct"),
    "ret_6m": ("6 months", "spct"),
    "ret_ytd": ("This year", "spct"),
    "ret_1y": ("1 year", "spct"),
    "volatility": ("Volatility, 1 year", "pct"),
    "from_high": ("From 52-week high", "spct"),
    "vs_ma50": ("To 50-day average", "spct"),
    "vs_ma200": ("To 200-day average", "spct"),
    "market_cap": ("Market value", "money"),
    "pe": ("P/E", "mult"),
    "forward_pe": ("Forward P/E, analysts' consensus", "mult"),
    "dividend_yield": ("Dividend yield", "pct"),
    "beta": ("Beta", "num"),
    "sector": ("Sector", "text"),
}
DEFAULT_COLUMNS = ("price", "change_1d", "ret_1m", "ret_ytd", "ret_1y")

# Per kind: how many tickers it takes, the ranges it offers and the one it opens on, and its size.
KINDS = {
    "price": {"tickers": (1, 1), "ranges": WINDOWS, "range": "1Y", "size": "m"},
    "compare": {"tickers": (2, 8), "ranges": WINDOWS, "range": "1Y", "size": "m"},
    "ruler": {"tickers": (2, 20), "ranges": PERIODS, "range": "1D", "size": "s"},
    "table": {"tickers": (1, 20), "ranges": (), "range": None, "size": "m"},
}
OPS = ("add", "update", "remove", "move", "clear")
# What an op can set on a widget.
FIELDS = ("type", "tickers", "range", "style", "averages", "columns", "size", "title")

# A Yahoo symbol: a stock or fund (AAPL, BRK-B), an index (^GSPC), a future (GC=F), a currency
# pair (EURUSD=X), a coin (BTC-USD).
TICKER = re.compile(r"[A-Z0-9^][A-Z0-9.\-=^]{0,11}")
ID = re.compile(r"w[1-9][0-9]{0,3}")
NEEDS = {"price": "one ticker", "compare": "two or more tickers", "ruler": "two or more tickers", "table": "at least one ticker"}


class Invalid(Exception):
    """A widget that cannot be drawn. Its message is for the reader."""


def _tickers(raw) -> list[str]:
    seen: list[str] = []
    for t in raw if isinstance(raw, list) else []:
        t = t.strip().upper().lstrip("$") if isinstance(t, str) else ""
        if TICKER.fullmatch(t) and t not in seen:
            seen.append(t)
    return seen


def _title(raw) -> str:
    title = " ".join(raw.split())[:TITLE_MAX] if isinstance(raw, str) else ""
    return "" if unfit(title) else title


def normalize(raw: dict, wid: str) -> dict:
    """A widget in its one shape, with every setting it does not bring at its default."""
    kind = raw.get("type")
    if kind not in KINDS:
        raise Invalid("There is no such kind of view.")
    spec = KINDS[kind]
    tickers = _tickers(raw.get("tickers"))
    fewest, most = spec["tickers"]
    if len(tickers) < fewest:
        raise Invalid(f"A {kind} view needs {NEEDS[kind]}.")
    widget: dict = {"id": wid, "type": kind, "title": _title(raw.get("title")), "tickers": tickers[:most],
                    "size": raw.get("size") if raw.get("size") in SIZES else spec["size"]}
    if spec["ranges"]:
        widget["range"] = raw.get("range") if raw.get("range") in spec["ranges"] else spec["range"]
    if kind == "price":
        widget["style"] = raw.get("style") if raw.get("style") in STYLES else "candles"
        asked = raw.get("averages") if isinstance(raw.get("averages"), list) else []
        widget["averages"] = [a for a in AVERAGES if a in asked]
    if kind == "table":
        asked = raw.get("columns") if isinstance(raw.get("columns"), list) else []
        columns = [c for c in dict.fromkeys(c for c in asked if isinstance(c, str)) if c in METRICS]
        widget["columns"] = columns[:TABLE_COLUMNS_MAX] or list(DEFAULT_COLUMNS)
    return widget


def clean_board(raw) -> list[dict]:
    """The board a browser sends back, with whatever is not a widget left out."""
    board: list[dict] = []
    for item in raw if isinstance(raw, list) else []:
        wid = item.get("id") if isinstance(item, dict) else None
        if not isinstance(wid, str) or not ID.fullmatch(wid) or any(w["id"] == wid for w in board):
            continue
        try:
            board.append(normalize(item, wid))
        except Invalid:
            continue
        if len(board) == MAX_WIDGETS:
            break
    return board


def _next_id(board: list[dict], used: set[str]) -> str:
    n = max((int(i[1:]) for i in used | {w["id"] for w in board}), default=0) + 1
    return f"w{n}"


def _place(board: list[dict], widget: dict, position) -> None:
    """Puts a widget at a place on the board, counted from 1; at the end when none is given."""
    at = position - 1 if isinstance(position, int) and not isinstance(position, bool) else len(board)
    board.insert(max(0, min(at, len(board))), widget)


def apply(board: list[dict], ops) -> tuple[list[dict], list[str], list[str]]:
    """A board after the changes of one turn: the new board, the ids of the widgets that are new
    or different, and what could not be done, in words for the reader."""
    board = [dict(w) for w in board]
    used = {w["id"] for w in board}  # an id is not given twice in a turn, even after a clear
    changed: list[str] = []
    problems: list[str] = []
    for op in (ops if isinstance(ops, list) else [])[:OPS_MAX]:
        if not isinstance(op, dict) or op.get("op") not in OPS:
            continue
        kind = op["op"]
        if kind == "clear":
            board = []
            continue
        if kind == "add":
            if len(board) >= MAX_WIDGETS:
                problems.append(f"The board is full: it holds {MAX_WIDGETS} views.")
                continue
            try:
                widget = normalize(op, _next_id(board, used))
            except Invalid as exc:
                problems.append(str(exc))
                continue
            used.add(widget["id"])
            _place(board, widget, op.get("position"))
            changed.append(widget["id"])
            continue
        at = next((i for i, w in enumerate(board) if w["id"] == op.get("id")), None)
        if at is None:
            problems.append("That view is not on the board.")
            continue
        target = board.pop(at)
        if kind == "remove":
            continue
        if kind == "update":
            try:
                target = normalize({**target, **{k: op[k] for k in FIELDS if op.get(k) is not None}}, target["id"])
            except Invalid as exc:
                problems.append(str(exc))
                board.insert(at, target)
                continue
            changed.append(target["id"])
        _place(board, target, op.get("position") if kind == "move" or op.get("position") is not None else at + 1)
    live = {w["id"] for w in board}
    return board, [i for i in dict.fromkeys(changed) if i in live], problems
