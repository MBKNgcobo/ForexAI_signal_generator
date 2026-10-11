"""Pure SL/TP outcome evaluation (no I/O, fully unit-testable).

Price convention (documented, matches MT5 execution reality):

* LONG: adverse move hits the **bid** (what you can sell at), favourable
  move needs the **ask** (what you must buy back at).
* SHORT: adverse move hits the **ask**, favourable move needs the **bid**.
* Candle fallback (Twelve Data / no tick): the candle ``close`` is used
  for both bid and ask.

Comparisons are exact on the raw floats — triggering uses ``<=`` / ``>=``
directly, never rounded values (rounding display-only via ``quantize``).
When one polling gap (or one candle) spans *both* SL and TP, the fill
order is unknowable: the outcome is ``AMBIGUOUS`` and the caller must
mark the signal OUTCOME_UNRESOLVED with the retained price data, never
arbitrarily award a win or loss.
"""

from __future__ import annotations

from app.services.signal_tracking.models import LONG, SHORT


TP = "TP"
SL = "SL"
NONE = "NONE"
AMBIGUOUS = "AMBIGUOUS"


def evaluate_outcome(
    *,
    direction: str,
    stop_loss: float,
    take_profit: float,
    bid: float | None = None,
    ask: float | None = None,
    price: float | None = None,
    candle_high: float | None = None,
    candle_low: float | None = None,
) -> str:
    """Return TP / SL / NONE / AMBIGUOUS for one price observation."""

    is_long = direction == LONG
    is_short = direction == SHORT
    if not (is_long or is_short):
        raise ValueError(f"unknown direction {direction!r}")

    if bid is None and ask is None and price is not None:
        bid = ask = float(price)

    sl_hit = False
    tp_hit = False

    # Tick-level evaluation with the documented bid/ask convention.
    if bid is not None and ask is not None:
        b = float(bid)
        a = float(ask)
        if is_long:
            sl_hit = b <= float(stop_loss)
            tp_hit = a >= float(take_profit)
        else:
            sl_hit = a >= float(stop_loss)
            tp_hit = b <= float(take_profit)
    # Single-price fallback (candle close).
    elif price is not None:
        p = float(price)
        if is_long:
            sl_hit = p <= float(stop_loss)
            tp_hit = p >= float(take_profit)
        else:
            sl_hit = p >= float(stop_loss)
            tp_hit = p <= float(take_profit)

    # Candle-range evaluation: a range spanning both levels is ambiguous.
    if candle_high is not None and candle_low is not None:
        hi = float(candle_high)
        lo = float(candle_low)
        if is_long:
            rng_sl = lo <= float(stop_loss)
            rng_tp = hi >= float(take_profit)
        else:
            rng_sl = hi >= float(stop_loss)
            rng_tp = lo <= float(take_profit)
        if rng_sl and rng_tp:
            return AMBIGUOUS
        sl_hit = sl_hit or rng_sl
        tp_hit = tp_hit or rng_tp

    if sl_hit and tp_hit:
        return AMBIGUOUS
    if tp_hit:
        return TP
    if sl_hit:
        return SL
    return NONE
