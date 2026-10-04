"""Trading-target labelling tests.

``create_trading_target`` decides whether history was a BUY, SELL or NO_TRADE
using the same ATR barriers the risk agent applies live. Pinning the labelling
keeps training and inference aligned.
"""

import math

import pandas as pd

from app.models.targets import create_trading_target


def _row(close, atr, high, low):
    return {"close": close, "atr_14": atr, "high": high, "low": low}


def test_labels_buy_sell_and_no_trade():
    # horizon=1: every row is labelled by the single following candle.
    # atr=1.0 -> BUY TP 101.5 / SL 99.0, SELL TP 98.5 / SL 101.0.
    df = pd.DataFrame(
        [
            _row(100.0, 1.0, 100.2, 99.8),  # entry for the BUY case
            _row(100.0, 1.0, 102.0, 99.5),  # high >= BUY TP -> BUY
            _row(100.0, 1.0, 100.5, 98.0),  # low <= SELL TP -> SELL
            _row(100.0, 1.0, 100.3, 99.7),  # neither barrier -> NO_TRADE
        ]
    )

    targets = create_trading_target(df, horizon=1)["target"].tolist()

    assert targets[0] == 1
    assert targets[1] == -1
    assert targets[2] == 0
    assert math.isnan(targets[3])  # no future candle exists for the last row


def test_rows_without_a_full_horizon_are_nan():
    df = pd.DataFrame([_row(100.0, 1.0, 100.2, 99.8) for _ in range(3)])

    targets = create_trading_target(df, horizon=2)["target"].tolist()

    assert math.isnan(targets[-1])
    assert math.isnan(targets[-2])


def test_invalid_atr_produces_nan_labels():
    df = pd.DataFrame(
        [
            _row(100.0, 0.0, 100.2, 99.8),
            _row(100.0, 1.0, 100.5, 99.5),
        ]
    )

    targets = create_trading_target(df, horizon=1)["target"].tolist()

    assert math.isnan(targets[0])
