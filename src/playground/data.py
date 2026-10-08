"""The figures behind a widget. Every number a board shows is worked out here, from daily bars:
the model that composes the board never sees one.

A return over a range is the last close against the close the range starts from: one session
back for "1D", the last close of the year before for "YTD". Without dividends.
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

from .market import MarketUnavailable
from .widgets import METRICS

# Sessions a range goes back.
SESSIONS = {"1D": 1, "1W": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252, "2Y": 504, "5Y": 1260}
YEAR = 252
WORKERS = 8
# The figures of a table that do not come from the bars.
FACTS = ("market_cap", "pe", "forward_pe", "dividend_yield", "beta", "sector")
RETURNS = {"change_1d": "1D", "ret_1w": "1W", "ret_1m": "1M", "ret_3m": "3M", "ret_6m": "6M", "ret_ytd": "YTD", "ret_1y": "1Y"}


def base(bars: list[dict], rng: str) -> int:
    """Where a range starts in a symbol's bars: the bar whose close everything is measured from.
    The first bar there is, when the history is shorter than the range."""
    if rng == "YTD":
        year = bars[-1]["time"][:4]
        first = next(i for i, b in enumerate(bars) if b["time"][:4] == year)
        return max(0, first - 1)
    return max(0, len(bars) - 1 - SESSIONS[rng])


def change(bars: list[dict], rng: str) -> float | None:
    """The return over a range, as a fraction. None when the history does not reach that far."""
    if len(bars) < 2 or (rng != "YTD" and len(bars) - 1 < SESSIONS[rng]):
        return None
    start = bars[base(bars, rng)]["close"]
    return bars[-1]["close"] / start - 1 if start else None


def average(closes: list[float], n: int) -> list[float | None]:
    """The mean of the last ``n`` closes at each bar; None until there are ``n``."""
    out, total = [], 0.0
    for i, c in enumerate(closes):
        total += c - (closes[i - n] if i >= n else 0.0)
        out.append(total / n if i >= n - 1 else None)
    return out


def volatility(bars: list[dict]) -> float | None:
    """The spread of a year of daily returns, as a yearly figure."""
    closes = [b["close"] for b in bars[-(YEAR + 1):]]
    moves = [math.log(b / a) for a, b in zip(closes, closes[1:]) if a > 0 and b > 0]
    if len(moves) < 60:
        return None
    mean = sum(moves) / len(moves)
    return math.sqrt(sum((m - mean) ** 2 for m in moves) / (len(moves) - 1) * YEAR)


def _reads(market, tickers: list[str]) -> tuple[list[dict], list[str]]:
    """Each ticker's name and bars, in the order asked, and the tickers the provider has nothing for."""
    def read(t: str):
        try:
            return market.read(t)
        except MarketUnavailable:
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        reads = list(pool.map(read, tickers))
    if all(r is None for r in reads):
        raise MarketUnavailable("The market data provider did not answer.")
    found = [r for r in reads if r and r["bars"]]
    return found, [t for t, r in zip(tickers, reads) if not r or not r["bars"]]


def _price(market, widget: dict) -> dict:
    found, missing = _reads(market, widget["tickers"])
    if not found:
        return {"missing": missing}
    read = found[0]
    bars = read["bars"]
    start = base(bars, widget["range"])
    closes = [b["close"] for b in bars]
    lines = {str(n): [{"time": b["time"], "value": round(v, 4)} for b, v in zip(bars[start:], average(closes, n)[start:]) if v is not None]
             for n in widget["averages"]}
    return {"ticker": read["ticker"], "name": read["name"], "bars": bars[start:], "averages": lines,
            "last": closes[-1], "change": closes[-1] / closes[start] - 1 if closes[start] else None, "missing": missing}


def _compare(market, widget: dict) -> dict:
    found, missing = _reads(market, widget["tickers"])
    if not found:
        return {"series": [], "missing": missing}
    # Every line starts at zero on the same day: the latest of the days each one's range starts.
    since = max(r["bars"][base(r["bars"], widget["range"])]["time"] for r in found)
    series = []
    for r in found:
        bars = [b for b in r["bars"] if b["time"] >= since]
        start = bars[0]["close"]
        points = [{"time": b["time"], "value": round(b["close"] / start - 1, 6)} for b in bars] if start else []
        series.append({"ticker": r["ticker"], "name": r["name"], "points": points, "total": points[-1]["value"] if points else None})
    return {"since": since, "series": series, "missing": missing}


def _ruler(market, widget: dict) -> dict:
    found, missing = _reads(market, widget["tickers"])
    rows = [{"ticker": r["ticker"], "name": r["name"], "price": r["bars"][-1]["close"], "move": change(r["bars"], widget["range"])}
            for r in found]
    # From the strongest to the weakest; the ones whose history does not reach, last.
    rows.sort(key=lambda row: (row["move"] is None, -(row["move"] or 0.0)))
    return {"rows": rows, "missing": missing}


def _facts(market, ticker: str) -> dict:
    try:
        return market.profile(ticker)
    except MarketUnavailable:
        return {}  # the bars came: the table is shown without these


def _table(market, widget: dict) -> dict:
    found, missing = _reads(market, widget["tickers"])
    columns = widget["columns"]
    facts: dict[str, dict] = {}
    if any(c in FACTS for c in columns):
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            facts = dict(zip((r["ticker"] for r in found), pool.map(lambda r: _facts(market, r["ticker"]), found)))
    rows = []
    for r in found:
        bars, known = r["bars"], facts.get(r["ticker"], {})
        closes, last = [b["close"] for b in bars], bars[-1]["close"]
        values: dict = {}
        for c in columns:
            if c == "price":
                values[c] = last
            elif c in RETURNS:
                values[c] = change(bars, RETURNS[c])
            elif c == "volatility":
                values[c] = volatility(bars)
            elif c == "from_high":
                high = max(b["high"] for b in bars[-YEAR:])
                values[c] = last / high - 1 if high else None
            elif c in ("vs_ma50", "vs_ma200"):
                mean = average(closes, 50 if c == "vs_ma50" else 200)[-1]
                values[c] = last / mean - 1 if mean else None
            elif c == "dividend_yield":
                values[c] = known["dividend"] / last if known.get("dividend") and last else None
            else:
                values[c] = known.get(c) or None
        rows.append({"ticker": r["ticker"], "name": r["name"], "values": values})
    return {"columns": [{"key": c, "label": METRICS[c][0], "kind": METRICS[c][1]} for c in columns], "rows": rows, "missing": missing}


RESOLVERS = {"price": _price, "compare": _compare, "ruler": _ruler, "table": _table}


def resolve(market, widget: dict) -> dict:
    """What a widget (in its one shape: ``widgets.normalize``) needs to be drawn."""
    return {**RESOLVERS[widget["type"]](market, widget), "sample": bool(getattr(market, "sample", False))}
