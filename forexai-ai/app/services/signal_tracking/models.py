"""Accepted-signal data model, validation and instrument precision.

Maps the pipeline vocabulary (BUY/SELL) to the tracking vocabulary
(LONG/SHORT): BUY -> LONG, SELL -> SHORT. HOLD/NO_TRADE are never
trackable and are rejected at validation.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


LONG = "LONG"
SHORT = "SHORT"

STATUS_ACCEPTED = "ACCEPTED"
STATUS_ACTIVE = "ACTIVE"
STATUS_TAKE_PROFIT_HIT = "TAKE_PROFIT_HIT"
STATUS_STOP_LOSS_HIT = "STOP_LOSS_HIT"
STATUS_CANCELLED = "CANCELLED"
STATUS_EXPIRED = "EXPIRED"
STATUS_OUTCOME_UNRESOLVED = "OUTCOME_UNRESOLVED"

TERMINAL_STATUSES = frozenset(
    {
        STATUS_TAKE_PROFIT_HIT,
        STATUS_STOP_LOSS_HIT,
        STATUS_CANCELLED,
        STATUS_EXPIRED,
        STATUS_OUTCOME_UNRESOLVED,
    }
)

ACTIVE_STATUSES = frozenset({STATUS_ACCEPTED, STATUS_ACTIVE})

EVENT_SIGNAL_ACCEPTED = "SIGNAL_ACCEPTED"
EVENT_MONITORING_STARTED = "SIGNAL_MONITORING_STARTED"
EVENT_PRICE_UPDATED = "PRICE_UPDATED"
EVENT_TAKE_PROFIT_HIT = "TAKE_PROFIT_HIT"
EVENT_STOP_LOSS_HIT = "STOP_LOSS_HIT"
EVENT_SIGNAL_CANCELLED = "SIGNAL_CANCELLED"
EVENT_SIGNAL_EXPIRED = "SIGNAL_EXPIRED"
EVENT_MONITORING_ERROR = "MONITORING_ERROR"


def normalize_direction(raw: object) -> str | None:
    """Map BUY/SELL/LONG/SHORT to LONG/SHORT; None when not executable."""

    if raw is None:
        return None
    text = str(raw).strip().upper()
    if text in ("BUY", "LONG"):
        return LONG
    if text in ("SELL", "SHORT"):
        return SHORT
    return None


def instrument_precision(symbol: str) -> int:
    """Price decimals for ``symbol`` (JPY-quoted pairs use 3, else 5)."""

    sym = (symbol or "").upper()
    if len(sym) >= 6 and ("JPY" in sym):
        return 3
    return 5


def quantize(price: float, symbol: str) -> float:
    """Round ``price`` to the instrument precision (never used to trigger)."""

    return round(float(price), instrument_precision(symbol))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TrackedSignal:
    """One accepted signal and its monitoring state."""

    signal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    symbol: str = ""
    direction: str = LONG
    timeframe: str = ""
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_reward: float | None = None
    generated_at: str | None = None
    accepted_at: str = field(default_factory=_now_iso)
    source_agent: str | None = None
    confidence: float | None = None
    status: str = STATUS_ACTIVE
    initial_price: float | None = None
    current_price: float | None = None
    last_price_at: str | None = None
    close_price: float | None = None
    closed_at: str | None = None
    outcome: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def validate_signal(
    *,
    symbol: object,
    direction: object,
    entry_price: object,
    stop_loss: object,
    take_profit: object,
) -> tuple[str | None, str | None]:
    """Validate raw acceptance fields.

    Returns ``(direction, error)``: ``direction`` is LONG/SHORT on success,
    ``error`` is a human message on failure. Missing/invalid prices are
    never invented — they are reported so the caller can fix the flow.
    """

    if not symbol or not isinstance(symbol, str) or not symbol.strip():
        return None, "symbol is required (e.g. EURUSD)."
    resolved = normalize_direction(direction)
    if resolved is None:
        return None, (
            f"direction {direction!r} is not executable "
            "(expected BUY/SELL or LONG/SHORT; HOLD/NO_TRADE rejected)."
        )
    try:
        entry = float(entry_price)  # type: ignore[arg-type]
        sl = float(stop_loss)  # type: ignore[arg-type]
        tp = float(take_profit)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, (
            "entry_price, stop_loss and take_profit must all be numeric; "
            "refusing to invent a missing price."
        )
    if not (entry > 0 and sl > 0 and tp > 0):
        return None, "entry_price, stop_loss and take_profit must be > 0."
    if resolved == LONG:
        if not sl < entry < tp:
            return None, (
                "invalid LONG levels: require stop_loss < entry_price "
                f"< take_profit (got SL={sl} entry={entry} TP={tp})."
            )
    else:
        if not tp < entry < sl:
            return None, (
                "invalid SHORT levels: require take_profit < entry_price "
                f"< stop_loss (got TP={tp} entry={entry} SL={sl})."
            )
    return resolved, None
