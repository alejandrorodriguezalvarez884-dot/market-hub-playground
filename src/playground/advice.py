"""The rule of every Market Hub page, as a filter: describe, never advise. The composer is told the
same in its instructions; this is what catches a sentence or a title that slips through. The
same vocabulary the portal filters (insights.ADVICE and watch.TRADE in market-hub-landing)."""

from __future__ import annotations

import re

ADVICE = re.compile(
    r"\b(you should|you could|you may want|you might|consider (adding|trimming|selling|buying|reducing|rebalancing|diversif\w*)|"
    r"(buy|sell|hold|trim|add to|reduce|rebalance|diversify)\b[^.]{0,40}\b(now|soon|your)|recommend\w*|advis\w*|"
    r"undervalued|overvalued|cheap|expensive|attractive|bargain|price target|will (rise|fall|go up|go down|outperform|underperform|recover)|"
    r"is (likely|set|poised|expected) to|too (concentrated|risky|exposed|much)|should)\b", re.I)
# The vocabulary of a trade.
TRADE = re.compile(
    r"\b(overbought|oversold|opportunit\w+|entry|entries|exit|buy point|support|resistance|breakout|break out|upside|downside|"
    r"due for|room to|poised|bullish|bearish|stop loss|take profits?|buy|buying|buyers?|sell|selling|sellers?|"
    r"(good|bad|right|wrong|best|better) (moment|time|point|place|level))\b", re.I)
# The composer's own way of declining ("does not advise", "no advice") is not advice.
DECLINING = re.compile(r"\b(does not|doesn't|do not|don't|never|not|no|cannot|can't|without) (\w+ ){0,4}(advis\w*|recommend\w*)", re.I)


def unfit(text: str) -> bool:
    """Whether a sentence or a title reads as advice, a forecast or a trade."""
    text = DECLINING.sub(" ", text)
    return bool(ADVICE.search(text) or TRADE.search(text))
