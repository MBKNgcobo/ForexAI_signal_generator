import numpy as np
import pandas as pd

# RSI lives in one place. ``calculate_rsi`` is re-exported here so that
# existing callers of ``app.models.features`` keep working.
from app.services.technical_indicators import (
    calculate_rsi as calculate_rsi,
    _rsi_from_averages,
)


# ------------------------------------------------------------------
# Features used by the trained models.
#
# This list was previously copy-pasted in four places (training, dataset
# building, prediction and the quant agent). A single canonical definition
# prevents the deployed feature order from silently drifting from training.
# ------------------------------------------------------------------

FEATURE_COLUMNS = [
    "return_1",
    "return_3",
    "return_5",
    "return_10",

    "price_vs_ema20",
    "price_vs_ema50",
    "price_vs_ema200",

    "ema20_above_ema50",
    "ema50_above_ema200",

    "rsi_14",

    "macd",
    "macd_signal",
    "macd_histogram",

    "atr_percentage",
    "rolling_volatility_20",

    "candle_range_percentage",
    "body_percentage_of_price",
    "upper_wick_percentage",
    "lower_wick_percentage",

    "volume_change",
    "volume_ma_20",
]


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(
        span=period,
        adjust=False
    ).mean()


def calculate_rsi_series(
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Wilder RSI for every bar, not a single value for the whole frame.

    ``calculate_rsi`` returns one number for the end of a series. Assigning
    that number to a column gives every row the same value, so the training
    feature carries no information. This builds the real per-bar series with
    the same maths (SMA seed, then Wilder smoothing).
    """

    if period < 1:
        raise ValueError("period must be >= 1")

    prices = close.to_numpy(dtype=float)

    rsi = np.full(prices.shape, np.nan)

    if prices.size <= period:
        return pd.Series(rsi, index=close.index)

    changes = np.diff(prices)

    gains = np.where(changes > 0, changes, 0.0)
    losses = np.where(changes < 0, -changes, 0.0)

    average_gain = gains[:period].mean()      # seed: simple average
    average_loss = losses[:period].mean()

    rsi[period] = _rsi_from_averages(
        average_gain,
        average_loss,
    )

    for i in range(period, gains.size):

        average_gain = (
            (average_gain * (period - 1)) + gains[i]
        ) / period

        average_loss = (
            (average_loss * (period - 1)) + losses[i]
        ) / period

        rsi[i + 1] = _rsi_from_averages(
            average_gain,
            average_loss,
        )

    return pd.Series(rsi, index=close.index)


def calculate_atr(
    df: pd.DataFrame,
    period: int = 14
) -> pd.Series:

    previous_close = df["close"].shift(1)

    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - previous_close).abs(),
            (df["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return true_range.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()


def calculate_macd(
    close: pd.Series
) -> tuple[pd.Series, pd.Series, pd.Series]:

    ema12 = calculate_ema(close, 12)
    ema26 = calculate_ema(close, 26)

    macd = ema12 - ema26

    signal = macd.ewm(
        span=9,
        adjust=False
    ).mean()

    histogram = macd - signal

    return macd, signal, histogram


def build_features(df: pd.DataFrame) -> pd.DataFrame:

    data = df.copy()

    data = data.sort_values("datetime").reset_index(drop=True)

    # ---------------------------------------------------------
    # Returns
    # ---------------------------------------------------------

    data["return_1"] = (
        data["close"].pct_change(1)
    )

    data["return_3"] = (
        data["close"].pct_change(3)
    )

    data["return_5"] = (
        data["close"].pct_change(5)
    )

    data["return_10"] = (
        data["close"].pct_change(10)
    )

    # ---------------------------------------------------------
    # Trend
    # ---------------------------------------------------------

    data["ema_10"] = calculate_ema(
        data["close"], 10
    )

    data["ema_20"] = calculate_ema(
        data["close"], 20
    )

    data["ema_50"] = calculate_ema(
        data["close"], 50
    )

    data["ema_100"] = calculate_ema(
        data["close"], 100
    )

    data["ema_200"] = calculate_ema(
        data["close"], 200
    )

    # Distance from moving averages

    data["price_vs_ema20"] = (
        data["close"] / data["ema_20"] - 1
    )

    data["price_vs_ema50"] = (
        data["close"] / data["ema_50"] - 1
    )

    data["price_vs_ema200"] = (
        data["close"] / data["ema_200"] - 1
    )

    # Trend relationships

    data["ema20_above_ema50"] = (
        data["ema_20"] > data["ema_50"]
    ).astype(int)

    data["ema50_above_ema200"] = (
        data["ema_50"] > data["ema_200"]
    ).astype(int)

    # ---------------------------------------------------------
    # Momentum
    # ---------------------------------------------------------

    data["rsi_14"] = calculate_rsi_series(
        data["close"], 14
    )

    (
        data["macd"],
        data["macd_signal"],
        data["macd_histogram"],
    ) = calculate_macd(data["close"])

    # ---------------------------------------------------------
    # Volatility
    # ---------------------------------------------------------

    data["atr_14"] = calculate_atr(
        data, 14
    )

    data["atr_percentage"] = (
        data["atr_14"] / data["close"]
    )

    data["rolling_volatility_20"] = (
        data["return_1"]
        .rolling(20)
        .std()
    )

    # ---------------------------------------------------------
    # Candle structure
    # ---------------------------------------------------------

    data["candle_range"] = (
        data["high"] - data["low"]
    )

    data["body_size"] = (
        data["close"] - data["open"]
    ).abs()

    data["body_percentage"] = (
        data["body_size"]
        / data["candle_range"].replace(0, np.nan)
    )

    data["upper_wick"] = (
        data["high"]
        - data[["open", "close"]].max(axis=1)
    )

    data["lower_wick"] = (
        data[["open", "close"]].min(axis=1)
        - data["low"]
    )

    data["candle_range_percentage"] = (
        data["candle_range"] / data["close"]
    )

    data["body_percentage_of_price"] = (
        data["body_size"] / data["close"]
    )

    data["upper_wick_percentage"] = (
        data["upper_wick"] / data["close"]
    )

    data["lower_wick_percentage"] = (
        data["lower_wick"] / data["close"]
    )

    # ---------------------------------------------------------
    # Volume
    # ---------------------------------------------------------

    if "volume" in data.columns:

        # Spot FX volume may be unavailable from the provider.
        # When volume is entirely zero, do not create volume-based
        # features because pct_change(0) produces NaN.

        if data["volume"].fillna(0).sum() > 0:

            data["volume_change"] = (
                data["volume"]
                .pct_change(fill_method=None)
            )

            data["volume_ma_20"] = (
                data["volume"]
                .rolling(20)
                .mean()
            )

        else:

            data["volume_change"] = 0.0
            data["volume_ma_20"] = 0.0

    return data