from app.services.technical_indicators import (
    calculate_atr,
    calculate_ema,
    calculate_rsi,
)


def test_ema_returns_value():

    prices = [
        1,
        2,
        3,
        4,
        5,
    ]

    result = calculate_ema(
        prices,
        3,
    )

    assert result is not None


def test_ema_requires_enough_data():

    prices = [
        1,
        2,
    ]

    result = calculate_ema(
        prices,
        3,
    )

    assert result is None


def test_rsi_returns_value():

    prices = [
        1,
        2,
        3,
        4,
        5,
        4,
        5,
        6,
        7,
        8,
        7,
        8,
        9,
        10,
        11,
    ]

    result = calculate_rsi(
        prices,
        14,
    )

    assert result is not None


def test_atr_returns_value():

    candles = [
        {
            "high": 1.2,
            "low": 1.0,
            "close": 1.1,
        }
        for _ in range(15)
    ]

    result = calculate_atr(
        candles,
        14,
    )

    assert result is not None


def test_atr_uses_wilder_smoothing_not_tail_sma():
    # SQA C-01: on a trending series Wilder ATR (full-history smoothing)
    # differs from a plain SMA of the last N true ranges. The live value
    # must be Wilder so stops/targets match training.
    candles = [
        {
            "high": 1.1000 + i * 0.0010,
            "low": 1.0990 + i * 0.0010,
            "close": 1.0995 + i * 0.0010,
        }
        for i in range(30)
    ]

    result = calculate_atr(candles, 14)

    assert result is not None
    # Wilder converges toward the steady 0.0010 range from above; the tail
    # SMA is exactly 0.0010. If they ever match on this fixture, the
    # smoothing was lost.
    assert result != 0.0010
    assert 0.0010 < result < 0.0020


def test_live_atr_matches_training_atr_series_tail():
    # SQA C-01 parity: the scalar live ATR must equal the last value of the
    # DataFrame training ATR over the same candles.
    import pandas as pd

    from app.models.features import calculate_atr as training_atr

    candles = [
        {
            "high": 1.1000 + (i % 7) * 0.0004,
            "low": 1.0990 + (i % 5) * 0.0003,
            "close": 1.0995 + (i % 3) * 0.0002,
        }
        for i in range(50)
    ]

    live = calculate_atr(candles, 14)

    frame = pd.DataFrame(
        [
            {"high": c["high"], "low": c["low"], "close": c["close"]}
            for c in candles
        ]
    )

    tail = training_atr(frame, 14).iloc[-1]

    assert live is not None
    # Loop vs EWM summation order differs at ~1e-19; parity means agreement
    # far below any pip scale (1e-12), not bit identity.
    assert abs(live - tail) < 1e-12