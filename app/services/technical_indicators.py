def calculate_ema(
    prices: list[float],
    period: int,
) -> float | None:

    if len(prices) < period:
        return None

    multiplier = 2 / (period + 1)

    ema = sum(prices[:period]) / period

    for price in prices[period:]:
        ema = (
            (price - ema) * multiplier
        ) + ema

    return ema


def calculate_rsi(
    prices: list[float],
    period: int = 14,
) -> float | None:
    """Wilder's Relative Strength Index over the whole series.

    The first average gain/loss is the simple mean of the first
    ``period`` changes; every later change is folded in with Wilder
    smoothing. Using only the first window would freeze the RSI on the
    oldest candles, which is the bug this implementation fixes.
    """

    if period < 1:
        raise ValueError("period must be >= 1")

    if len(prices) <= period:
        return None

    gains = []
    losses = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]

        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))

    average_gain = (
        sum(gains[:period]) / period
    )

    average_loss = (
        sum(losses[:period]) / period
    )

    for gain, loss in zip(
        gains[period:],
        losses[period:],
    ):

        average_gain = (
            (average_gain * (period - 1)) + gain
        ) / period

        average_loss = (
            (average_loss * (period - 1)) + loss
        ) / period

    return _rsi_from_averages(
        average_gain,
        average_loss,
    )


def _rsi_from_averages(
    average_gain: float,
    average_loss: float,
) -> float:

    if average_loss == 0:
        return 50.0 if average_gain == 0 else 100.0

    rs = average_gain / average_loss

    return 100 - (100 / (1 + rs))


def calculate_atr(
    candles: list[dict],
    period: int = 14,
) -> float | None:

    if len(candles) <= period:
        return None

    true_ranges = []

    for i, candle in enumerate(candles):

        high = candle["high"]
        low = candle["low"]

        if i == 0:
            previous_close = candle["close"]
        else:
            previous_close = candles[i - 1]["close"]

        true_range = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close),
        )

        true_ranges.append(true_range)

    return sum(
        true_ranges[-period:]
    ) / period