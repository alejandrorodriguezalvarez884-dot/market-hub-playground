"""The board: widgets in their one shape, and the changes a turn can make."""

import pytest

from playground.config import MAX_WIDGETS
from playground.widgets import DEFAULT_COLUMNS, Invalid, apply, clean_board, normalize


def op(kind, **fields):
    return {"op": kind, **fields}


def test_a_widget_gets_its_defaults():
    w = normalize({"type": "price", "tickers": ["nvda"]}, "w1")
    assert w == {"id": "w1", "type": "price", "title": "", "tickers": ["NVDA"], "size": "m", "range": "1Y",
                 "style": "candles", "averages": []}


def test_a_price_chart_keeps_one_ticker_and_known_averages():
    w = normalize({"type": "price", "tickers": ["$AAPL", "MSFT"], "averages": [200, 7, 50], "style": "line", "range": "5Y"}, "w1")
    assert w["tickers"] == ["AAPL"] and w["averages"] == [50, 200] and w["style"] == "line" and w["range"] == "5Y"


def test_a_range_the_kind_does_not_offer_falls_to_its_default():
    assert normalize({"type": "price", "tickers": ["SPY"], "range": "1D"}, "w1")["range"] == "1Y"
    assert normalize({"type": "ruler", "tickers": ["XLK", "XLE"], "range": "5Y"}, "w1")["range"] == "1D"


def test_a_table_keeps_known_columns_once():
    w = normalize({"type": "table", "tickers": ["JPM"], "columns": ["pe", "nonsense", "pe", "ret_1y"]}, "w1")
    assert w["columns"] == ["pe", "ret_1y"]
    assert normalize({"type": "table", "tickers": ["JPM"], "columns": []}, "w1")["columns"] == list(DEFAULT_COLUMNS)
    assert "range" not in w


@pytest.mark.parametrize("raw", [
    {"type": "pie", "tickers": ["SPY"]},
    {"type": "price", "tickers": []},
    {"type": "compare", "tickers": ["AAPL"]},
    {"type": "compare", "tickers": ["AAPL", "aapl"]},
    {"type": "ruler", "tickers": ["<script>", "DROP TABLE"]},
    {"type": "price"},
])
def test_what_cannot_be_drawn_is_refused(raw):
    with pytest.raises(Invalid):
        normalize(raw, "w1")


def test_symbols_of_every_kind_pass():
    w = normalize({"type": "ruler", "tickers": ["^GSPC", "GC=F", "EURUSD=X", "BTC-USD", "BRK-B"]}, "w1")
    assert w["tickers"] == ["^GSPC", "GC=F", "EURUSD=X", "BTC-USD", "BRK-B"]


def test_a_title_that_advises_is_dropped():
    assert normalize({"type": "price", "tickers": ["NVDA"], "title": "  My   semis "}, "w1")["title"] == "My semis"
    assert normalize({"type": "price", "tickers": ["NVDA"], "title": "Stocks you should buy now"}, "w1")["title"] == ""


def test_adding_gives_each_widget_its_own_id():
    board, changed, problems = apply([], [op("add", type="price", tickers=["NVDA"]), op("add", type="compare", tickers=["AAPL", "MSFT"])])
    assert [w["id"] for w in board] == ["w1", "w2"] and changed == ["w1", "w2"] and not problems


def test_adding_at_a_position():
    board, _, _ = apply([], [op("add", type="price", tickers=["AA"]), op("add", type="price", tickers=["BB"]),
                             op("add", type="price", tickers=["CC"], position=1)])
    assert [w["tickers"][0] for w in board] == ["CC", "AA", "BB"]


def test_updating_changes_only_what_is_set_and_keeps_the_place():
    board, _, _ = apply([], [op("add", type="price", tickers=["NVDA"], averages=[50]), op("add", type="price", tickers=["AMD"])])
    after, changed, problems = apply(board, [op("update", id="w1", range="2Y", tickers=None, style=None)])
    assert after[0] == {**board[0], "range": "2Y"} and after[1] == board[1]
    assert changed == ["w1"] and not problems


def test_updating_can_change_the_kind():
    board, _, _ = apply([], [op("add", type="compare", tickers=["AAPL", "MSFT"], range="6M")])
    after, _, _ = apply(board, [op("update", id="w1", type="ruler")])
    assert after[0]["type"] == "ruler" and after[0]["range"] == "6M" and after[0]["tickers"] == ["AAPL", "MSFT"]


def test_an_update_that_cannot_be_drawn_leaves_the_widget_as_it_was():
    board, _, _ = apply([], [op("add", type="compare", tickers=["AAPL", "MSFT"])])
    after, changed, problems = apply(board, [op("update", id="w1", tickers=["AAPL"])])
    assert after == board and not changed and problems == ["A compare view needs two or more tickers."]


def test_an_empty_title_puts_the_automatic_one_back():
    board, _, _ = apply([], [op("add", type="price", tickers=["NVDA"], title="Chips")])
    assert board[0]["title"] == "Chips"
    assert apply(board, [op("update", id="w1", title="")])[0][0]["title"] == ""


def test_removing_moving_and_clearing():
    board, _, _ = apply([], [op("add", type="price", tickers=[t]) for t in ("AA", "BB", "CC")])
    assert [w["id"] for w in apply(board, [op("remove", id="w2")])[0]] == ["w1", "w3"]
    assert [w["id"] for w in apply(board, [op("move", id="w3", position=1)])[0]] == ["w3", "w1", "w2"]
    assert [w["id"] for w in apply(board, [op("move", id="w1")])[0]] == ["w2", "w3", "w1"]
    cleared, changed, _ = apply(board, [op("clear"), op("add", type="price", tickers=["DD"])])
    assert [w["id"] for w in cleared] == ["w4"] and changed == ["w4"]


def test_a_widget_that_is_not_there_is_a_problem_not_an_error():
    board, changed, problems = apply([], [op("remove", id="w9"), op("update", id="w9", range="1M"), {"op": "explode"}, "nonsense"])
    assert board == [] and changed == [] and len(problems) == 2


def test_the_board_does_not_grow_past_its_limit():
    board, _, problems = apply([], [op("add", type="price", tickers=["SPY"])] * (MAX_WIDGETS + 2))
    assert len(board) == MAX_WIDGETS and problems


def test_a_board_from_the_browser_is_cleaned():
    raw = [{"id": "w1", "type": "price", "tickers": ["NVDA"], "evil": "<img>"}, {"id": "w1", "type": "price", "tickers": ["AMD"]},
           {"id": "x", "type": "price", "tickers": ["AMD"]}, {"id": "w2", "type": "compare", "tickers": ["ONE"]}, "junk", None,
           {"id": "w3", "type": "table", "tickers": ["JPM"]}]
    board = clean_board(raw)
    assert [w["id"] for w in board] == ["w1", "w3"] and "evil" not in board[0]
    assert clean_board("not a list") == [] and clean_board(None) == []
