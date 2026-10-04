"""Forex symbol parsing.

Unsupported pairs must raise ``ValueError`` at parse time so the API can answer
400 rather than failing deep inside the fundamental agent.
"""

import pytest

from app.fundamentals.currency_map import (
    country_for_currency,
    split_forex_symbol,
)


def test_split_supported_pair():
    assert split_forex_symbol("eurusd") == ("EUR", "USD")


def test_split_rejects_wrong_length():
    with pytest.raises(ValueError):
        split_forex_symbol("EUR")


def test_split_rejects_unknown_currency():
    with pytest.raises(ValueError):
        split_forex_symbol("ZZZUSD")


def test_country_lookup_is_case_insensitive():
    assert country_for_currency("usd") == "USA"


def test_country_lookup_rejects_unknown_currency():
    with pytest.raises(ValueError):
        country_for_currency("XYZ")
