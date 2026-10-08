"""Constants of the service. Secrets come from the environment (or .env locally), never from here."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

# --- The board -----------------------------------------------------------------------------

MAX_WIDGETS = 12
TITLE_MAX = 80  # characters of a widget's own title
TABLE_COLUMNS_MAX = 8
# What one turn of the chat takes: the reader's words, and the last turns for context.
MESSAGE_MAX = 500
HISTORY_TURNS = 8
OPS_MAX = 16  # changes to the board in one turn

# --- Market data ---------------------------------------------------------------------------

# A symbol's daily bars carry its last price: they are read again this often.
QUOTE_TTL_SECONDS = 120
PROFILE_TTL_SECONDS = 7 * 86400
# After Yahoo refuses a request nothing is asked for this long; after any other failure, for a
# shorter while, so a provider that is down does not slow every widget.
REFUSED_SECONDS = 300
FAILED_SECONDS = 60

# --- The composer --------------------------------------------------------------------------

# The model that turns what the reader asks into changes to the board. It never sees or writes a
# market figure: it names widgets and tickers, and the code fetches and computes.
COMPOSER_MODEL = os.environ.get("PLAYGROUND_MODEL", "claude-opus-5-5")
COMPOSER_EFFORT = os.environ.get("PLAYGROUND_EFFORT", "low")
COMPOSER_MAX_TOKENS = 4000  # of an answer: the thinking counts too
REPLY_MAX = 400  # characters of the sentence shown in the chat
# USD per million tokens (input, output), to log what each turn cost. Thinking tokens bill as
# output. Spend has no cap here: the owner limits it with the credit on the API account.
MODEL_PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-4-5": (1.00, 5.00),
}

# Turns of the chat one reader (or one address, where there is no sign-in) can take in an hour,
# and requests for a widget's figures. A brake on a runaway page, not a spending cap.
CHAT_PER_HOUR = 60
DATA_PER_HOUR = 1500
