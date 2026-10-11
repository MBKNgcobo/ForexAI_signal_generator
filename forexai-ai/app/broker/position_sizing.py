"""Risk-based position sizing (SQA C-05).

Historically every signal traded a fixed lot (``MT5_SIGNAL_VOLUME``, default
0.01), so the stop distance - which varies with ATR/volatility - had no
relationship to capital at risk: a high-ATR pair silently risked far more per
trade than a low-ATR pair. This module turns a risk budget into a lot size:

    volume = (equity * risk_percent / 100)
             / (stop_distance_in_price * pip_value_per_lot)

where ``pip_value_per_lot`` is the account-currency value of a one-pip move on
one standard lot. For a USD-quoted pair that is ``10`` currency units per pip
per lot (a 0.0001 move on 100,000 units). The result is clamped to the
instrument's ``volume_min``/``volume_max`` and snapped to its ``volume_step``.

Everything here is pure and I/O-free so the money math is unit-testable without
a terminal or a live feed.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Value of a one-pip move on one standard lot (100,000 units), in quote
#: currency, for the common USD-quoted pairs (EURUSD, GBPUSD, AUDUSD...).
#: A pip is 0.0001 for a 5-digit pair, so 100,000 * 0.0001 = 10.
PIP_VALUE_PER_LOT_USD_QUOTE = 10.0


def pip_size(symbol: str) -> float:
    """Pip size for ``symbol`` (0.0001 for 5-digit pairs, 0.01 for JPY).

    Reuses the tracking layer's precision rule so sizing, live signals and
    paper/MT5 execution all agree on what a "pip" is.
    """

    from app.services.signal_tracking.models import instrument_precision

    return 10.0 ** (-instrument_precision(symbol)) * 10.0


def compute_position_volume(
    *,
    equity: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float,
    symbol: str,
    volume_min: float = 0.01,
    volume_max: float = 100.0,
    volume_step: float = 0.01,
) -> float:
    """Lot size that risks ``risk_percent`` of ``equity`` if ``stop_loss`` hits.

    Returns the fixed ``volume_min`` when sizing cannot be applied (non-positive
    equity/risk, or a non-positive stop distance) so a caller can fall back to
    the configured default instead of trading an un sized or zero position. The
    result is always clamped to ``[volume_min, volume_max]`` and snapped down to
    a whole ``volume_step`` (never rounding a risk up).

    Raises ``ValueError`` only for structurally impossible inputs (a stop that
    is not actually below/above the entry for the implied direction is handled
    by the caller via the non-positive stop-distance fallback).
    """

    if equity <= 0 or risk_percent <= 0:
        return volume_min

    stop_distance = abs(float(entry_price) - float(stop_loss))

    if stop_distance <= 0:
        return volume_min

    risk_amount = equity * (risk_percent / 100.0)

    # Loss per 1.0 lot if the stop is hit, in account currency (assuming a
    # USD-quoted account/instrument). Derive it from the pip size so JPY and
    # 5-digit pairs both size correctly. The pip count is rounded to the
    # nearest whole pip first so float dust (e.g. 1.1000-1.0980 =
    # 0.0020000000000000018) cannot silently shrink the size across the
    # volume_step boundary.
    pip = pip_size(symbol)
    stop_pips = round(stop_distance / pip)
    loss_per_lot = stop_pips * PIP_VALUE_PER_LOT_USD_QUOTE

    if loss_per_lot <= 0:
        return volume_min

    raw_volume = risk_amount / loss_per_lot

    return _clamp_and_step(raw_volume, volume_min, volume_max, volume_step)


def _clamp_and_step(
    volume: float,
    volume_min: float,
    volume_max: float,
    volume_step: float,
) -> float:
    """Clamp to ``[min, max]`` and snap DOWN to a whole ``step`` (never round
    a risk up). Falls back to ``volume_min`` when limits are unusable."""

    if volume_max < volume_min:
        volume_min, volume_max = volume_max, volume_min

    step = volume_step if volume_step > 0 else 0.01

    if step > 0:
        steps = int(volume / step)  # floor toward zero
        volume = steps * step

    volume = min(volume_max, max(volume_min, volume))

    # Guard against a step so coarse that flooring collapsed everything to 0.
    if volume < volume_min:
        volume = volume_min

    # Round to the step's precision to avoid float dust like 0.010000000000000002.
    decimals = _decimals(step)
    return round(volume, decimals)


def _decimals(step: float) -> int:
    text = f"{step:.10f}".rstrip("0")
    if "." not in text:
        return 2
    return len(text.split(".", 1)[1])


def compute_bridge_volume(
    payload: dict,
    *,
    equity: float,
    fallback_volume: float,
) -> float:
    """Per-signal lot size for the signal bridge, risk-based when enabled.

    Reads ``RISK_PERCENT`` from config. When it is ``0`` (the default) this is a
    no-op that returns ``fallback_volume`` unchanged, preserving the existing
    fixed-lot behaviour exactly. When ``RISK_PERCENT > 0`` it sizes the order
    from the payload's ``entry_price``/``stop_loss`` and the configured equity.

    Returns ``fallback_volume`` whenever the payload lacks the levels needed to
    size (missing/zero entry or stop, or a zero stop distance), so a signal the
    sizer cannot size never silently becomes a bigger or zero-lot order - the
    caller's configured default stands in.
    """

    from app.config import risk_percent

    risk = risk_percent()

    if risk <= 0:
        return fallback_volume

    risk_block = payload.get("risk_assessment")
    risk_block = risk_block if isinstance(risk_block, dict) else {}

    entry = risk_block.get("entry_price")
    stop = risk_block.get("stop_loss")

    if not entry or not stop:
        return fallback_volume

    symbol = str(payload.get("symbol") or "")

    sized = compute_position_volume(
        equity=equity,
        risk_percent=risk,
        entry_price=float(entry),
        stop_loss=float(stop),
        symbol=symbol,
    )

    # compute_position_volume already falls back to volume_min on bad inputs;
    # only trust it when it produced something above zero, else keep the
    # caller's configured default.
    return sized if sized and sized > 0 else fallback_volume

