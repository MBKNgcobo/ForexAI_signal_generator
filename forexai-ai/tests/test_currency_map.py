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


def test_split_accepts_every_seeded_pair():
    """Every pair in the dashboard's picker must survive this parser.

    The picker is populated from forex_pairs, which is seeded by
    ForexPairConfiguration, while this map decides which symbols the
    analysis endpoint accepts. A pair present in one and missing from the
    other would be listed in the UI and then fail with a 400 on selection,
    so the two lists are pinned together here.
    """

    seeded_pairs = [
        "AUDJPY", "AUDUSD", "EURCHF", "EURGBP", "EURJPY", "EURUSD",
        "EURZAR", "GBPJPY", "GBPUSD", "NZDUSD", "USDCAD", "USDCHF",
        "USDJPY", "USDZAR",
    ]

    for symbol in seeded_pairs:
        base, quote = split_forex_symbol(symbol)
        assert f"{base}{quote}" == symbol


def test_country_lookup_covers_zrand_nzd():
    assert country_for_currency("ZAR") == "ZAF"
    assert country_for_currency("NZD") == "NZL"
