"""Regression anchors for the RSI.

The values below are the published Wilder example (New Concepts in Technical
Trading Systems), frozen as golden values. The previous implementation only
averaged the first ``period`` changes, so it returned 70.5 for the whole
series and 100.0 for a collapsing market. These tests fail on that bug.
"""

import pandas as pd
import pytest

from app.models.features import calculate_rsi_series
from app.services.technical_indicators import calculate_rsi

WILDER = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89,
          46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64, 46.21, 46.25,
          45.71, 46.45, 45.78, 45.35, 44.03, 44.18, 44.22, 44.57, 43.42, 42.66, 43.13]

def test_matches_published_example():       # tolerance covers the 2-dp input rounding
    assert calculate_rsi(WILDER[:15]) == pytest.approx(70.5, abs=0.2)
    assert calculate_rsi(WILDER) == pytest.approx(37.8, abs=0.2)

def test_reflects_recent_data():
    series = [1.0 + 0.001 * i for i in range(15)] + [1.014 - 0.001 * i for i in range(1, 100)]
    assert calculate_rsi(series) < 10

def test_flat_market_is_neutral():
    assert calculate_rsi([1.1] * 30) == 50.0

def test_too_short_returns_none():
    assert calculate_rsi(WILDER[:14]) is None


def test_rejects_invalid_period():
    with pytest.raises(ValueError):
        calculate_rsi(WILDER, 0)


def test_series_matches_scalar_at_last_bar():
    series = calculate_rsi_series(pd.Series(WILDER), 14)

    assert series.iloc[-1] == pytest.approx(calculate_rsi(WILDER, 14))


def test_series_is_not_constant():
    """Guards the per-bar feature: rsi_14 must vary across candles."""

    series = calculate_rsi_series(pd.Series(WILDER), 14)

    assert series.nunique(dropna=True) > 1
    assert series.iloc[:14].isna().all()


def test_series_is_neutral_when_flat():
    series = calculate_rsi_series(pd.Series([1.1] * 30), 14)

    assert series.iloc[-1] == 50.0