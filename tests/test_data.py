"""The figures behind a widget, worked out from bars the tests write themselves."""

from datetime import date, timedelta

import pytest

from playground.data import average, base, change, resolve, volatility
from playground.market import MarketUnavailable, SampleMarket
from playground.widgets import normalize


def bars(closes, last=date(2026, 10, 7)):
    """Bars ending on a day, one per calendar day (simple, and enough for the arithmetic)."""
    days = [last - timedelta(days=len(closes) - 1 - i) for i in range(len(closes))]
    return [{"time": d.isoformat(), "open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 100} for d, c in zip(days, closes)]


class Fixed:
    sample = False

    def __init__(self, series, facts=None, down=()):
        self.series, self.facts, self.down = series, facts or {}, down

    def read(self, ticker):
        if ticker in self.down:
            raise MarketUnavailable("down")
        return {"ticker": ticker, "name": f"{ticker} Inc.", "bars": self.series.get(ticker, [])}

    def profile(self, ticker):
        return self.facts.get(ticker, {})


def widget(**raw):
    return normalize(raw, "w1")


def test_a_return_is_the_last_close_against_the_close_the_range_starts_from():
    b = bars([100.0] * 10 + [110.0, 121.0])
    assert change(b, "1D") == pytest.approx(0.10)
    assert change(b, "1W") == pytest.approx(0.21)
    assert change(b, "1M") is None  # the history does not reach a month back


def test_this_year_starts_from_the_last_close_of_the_year_before():
    b = bars([50.0, 100.0, 120.0, 150.0], last=date(2026, 1, 3))  # Dec 31, Jan 1, 2, 3
    assert b[base(b, "YTD")]["time"] == "2025-12-31"
    assert change(b, "YTD") == pytest.approx(2.0)


def test_averages_start_when_there_are_enough_closes():
    assert average([1.0, 2.0, 3.0, 4.0], 2) == [None, 1.5, 2.5, 3.5]


def test_volatility_of_a_flat_line_is_zero_and_needs_history():
    assert volatility(bars([100.0] * 100)) == 0.0
    assert volatility(bars([100.0] * 20)) is None


def test_a_price_chart_covers_its_range_and_carries_its_averages():
    closes = [100.0 + i for i in range(300)]
    got = resolve(Fixed({"NVDA": bars(closes)}), widget(type="price", tickers=["NVDA"], range="1M", averages=[20]))
    assert len(got["bars"]) == 22 and got["bars"][0]["close"] == closes[-22]  # 21 sessions and the one they start from
    assert got["change"] == pytest.approx(closes[-1] / closes[-22] - 1)
    assert got["name"] == "NVDA Inc." and got["last"] == closes[-1] and got["sample"] is False
    line = got["averages"]["20"]
    assert len(line) == 22 and line[-1]["value"] == pytest.approx(sum(closes[-20:]) / 20)


def test_a_comparison_starts_every_line_at_zero_on_the_same_day():
    long, short = bars([100.0] * 290 + [200.0] * 10), bars([10.0, 10.0, 20.0, 40.0, 50.0])
    got = resolve(Fixed({"OLD": long, "NEW": short}), widget(type="compare", tickers=["OLD", "NEW"], range="1Y"))
    assert got["since"] == short[0]["time"]
    assert [s["points"][0] for s in got["series"]] == [{"time": short[0]["time"], "value": 0.0}] * 2
    assert got["series"][0]["total"] == 0.0 and got["series"][1]["total"] == pytest.approx(4.0)  # OLD was already at 200


def test_a_ruler_is_sorted_and_puts_short_histories_last():
    series = {"UP": bars([100.0] * 30 + [130.0]), "DOWN": bars([100.0] * 30 + [80.0]), "YOUNG": bars([5.0, 6.0])}
    got = resolve(Fixed(series), widget(type="ruler", tickers=["DOWN", "YOUNG", "UP", "GONE"], range="1W"))
    assert [(r["ticker"], r["move"] and round(r["move"], 2)) for r in got["rows"]] == [("UP", 0.3), ("DOWN", -0.2), ("YOUNG", None)]
    assert got["missing"] == ["GONE"]


def test_a_table_computes_its_columns():
    closes = [100.0] * 260 + [110.0]
    facts = {"JPM": {"market_cap": 5e11, "pe": 12.5, "dividend": 5.5, "sector": "Financial Services", "beta": 0}}
    columns = ["price", "ret_1y", "from_high", "vs_ma50", "dividend_yield", "pe", "sector", "beta"]
    got = resolve(Fixed({"JPM": bars(closes)}, facts), widget(type="table", tickers=["JPM"], columns=columns))
    v = got["rows"][0]["values"]
    assert v["price"] == 110.0 and v["ret_1y"] == pytest.approx(0.10)
    assert v["from_high"] == pytest.approx(110 / 111 - 1)
    assert v["vs_ma50"] == pytest.approx(110 / ((49 * 100 + 110) / 50) - 1)
    assert v["dividend_yield"] == pytest.approx(0.05) and v["pe"] == 12.5 and v["sector"] == "Financial Services"
    assert v["beta"] is None  # no figure, not a zero
    assert got["columns"][0] == {"key": "price", "label": "Price", "kind": "price"}


def test_a_table_without_facts_does_not_ask_for_them():
    class NoFacts(Fixed):
        def profile(self, ticker):
            raise AssertionError("not needed")

    got = resolve(NoFacts({"JPM": bars([1.0, 2.0])}), widget(type="table", tickers=["JPM"], columns=["price"]))
    assert got["rows"][0]["values"] == {"price": 2.0}


def test_one_symbol_failing_is_missing_and_all_failing_is_an_error():
    market = Fixed({"OK": bars([1.0, 2.0])}, down=("BAD",))
    assert resolve(market, widget(type="ruler", tickers=["OK", "BAD"]))["missing"] == ["BAD"]
    with pytest.raises(MarketUnavailable):
        resolve(Fixed({}, down=("BAD", "WORSE")), widget(type="ruler", tickers=["BAD", "WORSE"]))


def test_a_symbol_nobody_has_gives_an_empty_widget():
    assert resolve(Fixed({}), widget(type="price", tickers=["NOPE"])) == {"missing": ["NOPE"], "sample": False}


def test_the_sample_market_is_the_same_every_time_and_says_what_it_is():
    a, b = SampleMarket(date(2026, 10, 7)).read("nvda"), SampleMarket(date(2026, 10, 7)).read("NVDA")
    assert a == b and len(a["bars"]) == 1300 and a["bars"][-1]["time"] == "2026-10-07"
    assert all(x["low"] <= min(x["open"], x["close"]) and x["high"] >= max(x["open"], x["close"]) for x in a["bars"])
    # One more day adds a bar and changes none of the others.
    later = SampleMarket(date(2026, 10, 8)).read("NVDA")["bars"]
    assert [x["time"] for x in later[-2:]] == ["2026-10-07", "2026-10-08"]
    assert later[-2] == a["bars"][-1]
    assert resolve(SampleMarket(date(2026, 10, 7)), widget(type="price", tickers=["NVDA"]))["sample"] is True
    assert SampleMarket().read("NOPE")["bars"] == []
