"""The composer, with a stand-in for the API: what is sent, what is spent, what is shown."""

import json
import logging
from types import SimpleNamespace

import anthropic
import pytest

from playground.advice import unfit
from playground.composer import (DECLINED, DONE, NOTHING, SCHEMA, SYSTEM, Composer, ComposerFailed, ComposerUnavailable,
                                 ScriptedComposer, cost_usd, prompt)
from playground.widgets import apply

BOARD = [{"id": "w1", "type": "price", "title": "", "tickers": ["NVDA"], "size": "m", "range": "1Y", "style": "candles", "averages": []}]


def answer(body, stop="end_turn", model="claude-opus-5-5", tokens=(3000, 200)):
    text = body if isinstance(body, str) else json.dumps(body)
    return SimpleNamespace(content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
                           stop_reason=stop, model=model,
                           usage=SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1], cache_creation_input_tokens=0, cache_read_input_tokens=0))


class FakeMessages:
    def __init__(self, response):
        self.response, self.calls = response, []

    def create(self, **asked):
        self.calls.append(asked)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeClient:
    def __init__(self, response):
        self.messages = FakeMessages(response)
        self.beta = SimpleNamespace(messages=FakeMessages(response))


def composer(response, **kwargs):
    client = FakeClient(response)
    return Composer(client=client, **kwargs), client


def test_a_turn_sends_the_board_the_conversation_and_the_request_and_no_figure():
    c, client = composer(answer({"ops": [{"op": "update", "id": "w1", "range": "2Y"}], "reply": "The chart now covers two years."}))
    history = [{"role": "user", "text": "chart nvidia"}, {"role": "assistant", "text": "Added a price chart of NVDA."}]
    turn = c.turn("make it two years", BOARD, history)
    assert turn == {"ops": [{"op": "update", "id": "w1", "range": "2Y"}], "reply": "The chart now covers two years."}
    asked = client.beta.messages.calls[0]
    assert asked["model"] == "claude-opus-5-5" and asked["fallbacks"] == "default" and asked["betas"] == ["server-side-fallback-2026-07-01"]
    assert asked["output_config"] == {"format": {"type": "json_schema", "schema": SCHEMA}, "effort": "low"}
    assert asked["system"] == [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}]
    sent = asked["messages"][0]["content"]
    assert json.dumps(BOARD, separators=(",", ":")) in sent and "Reader: chart nvidia" in sent and "You: Added a price chart" in sent
    assert sent.endswith("<request>\nmake it two years\n</request>")
    assert apply(BOARD, turn["ops"])[0][0]["range"] == "2Y"


def test_a_model_without_fallback_or_effort_is_asked_plainly():
    c, client = composer(answer({"ops": [], "reply": "Nothing to change."}), model="claude-haiku-4-5")
    c.turn("hello", [], [])
    asked = client.messages.calls[0]
    assert "fallbacks" not in asked and "betas" not in asked and "effort" not in asked["output_config"]
    assert not client.beta.messages.calls


def test_the_conversation_is_cut_to_its_last_turns():
    history = [{"role": "user", "text": f"turn {i}"} for i in range(30)]
    sent = prompt("now", [], history)
    assert "turn 29" in sent and "turn 22" in sent and "turn 21" not in sent


def test_every_turn_logs_its_cost_at_the_model_that_served_it_and_never_the_words(caplog):
    c, _ = composer(answer({"ops": [], "reply": "Nothing to change."}, model="claude-sonnet-5-5", tokens=(1_000_000, 100_000)))
    with caplog.at_level(logging.INFO, logger="playground.composer"):
        c.turn("a private question about my savings", [], [])
    assert "usd=3.0000" in caplog.text and "savings" not in caplog.text and "Nothing to change" not in caplog.text


def test_cached_tokens_are_priced_as_cached():
    usage = SimpleNamespace(input_tokens=1000, output_tokens=0, cache_creation_input_tokens=1000, cache_read_input_tokens=10000)
    assert cost_usd("claude-opus-5-5", usage) == pytest.approx((1000 + 1250 + 1000) * 4 / 1_000_000)


def test_there_is_no_spending_cap_of_our_own():
    c, client = composer(answer({"ops": [], "reply": "Nothing to change."}, tokens=(5_000_000, 500_000)))
    for _ in range(50):
        c.turn("hello", [], [])
    assert len(client.beta.messages.calls) == 50 and client.beta.messages.calls[0]["max_tokens"] == 4000


@pytest.mark.parametrize("error", [anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.BadRequestError])
def test_a_key_turned_down_or_out_of_credit_stops_the_chat_for_a_while(error, monkeypatch):
    c, client = composer(error.__new__(error))
    with pytest.raises(ComposerUnavailable):
        c.turn("hello", [], [])
    with pytest.raises(ComposerUnavailable):
        c.turn("hello again", [], [])
    assert len(client.beta.messages.calls) == 1  # the second turn did not reach the API
    monkeypatch.setattr("playground.composer.PAUSE_SECONDS", 0)
    client.beta.messages.response = answer({"ops": [], "reply": "Nothing to change."})
    assert c.turn("hello", [], [])["reply"] == "Nothing to change."


def test_a_refusal_is_a_reply():
    c, _ = composer(answer("", stop="refusal"))
    assert c.turn("something odd", [], []) == {"ops": [], "reply": DECLINED}


def test_an_answer_cut_off_cannot_be_used():
    c, _ = composer(answer('{"ops": [{"op": "add"', stop="max_tokens"))
    with pytest.raises(ComposerFailed):
        c.turn("hello", [], [])


@pytest.mark.parametrize("reply", ["You should buy NVDA now.", "NVDA looks cheap here.", "This is a good time to add to it.",
                                   "The stock is poised for a breakout.", ""])
def test_a_reply_that_advises_is_never_shown(reply):
    with_ops, _ = composer(answer({"ops": [{"op": "clear"}], "reply": reply}))
    assert with_ops.turn("what do I buy", [], [])["reply"] == DONE
    without, _ = composer(answer({"ops": [], "reply": reply}))
    assert without.turn("what do I buy", [], [])["reply"] == NOTHING


@pytest.mark.parametrize("reply", ["Added a one-year price chart of NVDA.", "The board shows figures and does not advise. I added a table of the three.",
                                   "This board does not give advice or recommendations.", "Fundamentals are not available here."])
def test_a_reply_that_describes_is_shown(reply):
    assert not unfit(reply)
    c, _ = composer(answer({"ops": [], "reply": reply}))
    assert c.turn("x", [], [])["reply"] == reply


def test_the_pages_own_sentences_pass_the_filter():
    assert not any(unfit(s) for s in (DONE, NOTHING, DECLINED))


def test_the_instructions_name_every_kind_and_column_and_carry_no_date():
    for word in ("price", "compare", "ruler", "table", "ret_ytd", "dividend_yield", "never advises"):
        assert word in SYSTEM
    assert "2026" not in SYSTEM  # anything that changes would empty the cache of the instructions


def test_the_scripted_composer_understands_a_handful_of_words():
    s = ScriptedComposer()
    one = apply([], s.turn("chart NVDA 2Y with the 50 and 200 day averages", [], [])["ops"])[0]
    assert one[0]["type"] == "price" and one[0]["range"] == "2Y" and one[0]["averages"] == [50, 200]
    assert apply([], s.turn("AAPL MSFT GOOGL YTD", [], [])["ops"])[0][0] == {
        "id": "w1", "type": "compare", "title": "", "tickers": ["AAPL", "MSFT", "GOOGL"], "size": "m", "range": "YTD"}
    assert apply([], s.turn("a table of JPM and BAC", [], [])["ops"])[0][0]["type"] == "table"
    assert apply([], s.turn("XLK XLE on one scale 1M", [], [])["ops"])[0][0]["range"] == "1M"
    assert apply(one, s.turn("remove it", one, [])["ops"])[0] == []
    assert apply(one, s.turn("clear", one, [])["ops"])[0] == []
    assert s.turn("hello there", [], [])["ops"] == []
