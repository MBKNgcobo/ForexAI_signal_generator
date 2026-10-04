"""Feature-engineering tests for the quant pipeline.

``build_features`` is the boundary between raw candles and the trained model:
if the column set drifts from ``FEATURE_COLUMNS``, inference silently reads the
wrong inputs. These tests pin that contract without needing any artefacts.
"""

import math

import pandas as pd

from app.models.features import FEATURE_COLUMNS, build_features


def _candles(rows: int = 60, volume: float = 1000.0) -> pd.DataFrame:
    base = pd.Timestamp("2026-01-01", tz="UTC")

    records = []

    price = 1.1000

    for i in range(rows):
        # A varying, sign-changing step keeps RSI informative (a monotonic
        # series would pin it at 0 or 100 and hide regressions).
        price += 0.0004 * math.sin(i / 2.0)

        records.append(
            {
                "datetime": base + pd.Timedelta(minutes=15 * i),
                "open": price,
                "high": price + 0.001,
                "low": price - 0.001,
                "close": price + 0.0005,
                "volume": volume,
            }
        )

    return pd.DataFrame(records)


def test_build_features_creates_every_trained_feature():
    featured = build_features(_candles())

    missing = [column for column in FEATURE_COLUMNS if column not in featured.columns]

    assert missing == []


def test_feature_columns_order_is_stable():
    featured = build_features(_candles())

    assert list(featured[FEATURE_COLUMNS].columns) == FEATURE_COLUMNS


def test_rsi_feature_varies_across_candles():
    featured = build_features(_candles())

    # The old whole-series RSI copied one number onto every row, which carries
    # no information for the model.
    assert featured["rsi_14"].nunique(dropna=True) > 1


def test_zero_volume_falls_back_to_zero_features():
    featured = build_features(_candles(volume=0.0))

    assert (featured["volume_change"] == 0.0).all()
    assert (featured["volume_ma_20"] == 0.0).all()
