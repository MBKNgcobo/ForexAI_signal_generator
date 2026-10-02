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