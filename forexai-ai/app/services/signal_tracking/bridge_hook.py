"""Accepted-signal tracking from the bridge acceptance path (no dupes).

``record_bridge_acceptance`` is called after ``SignalBridge`` gates pass
(HOLD/NO_TRADE, risk approval, SL/TP presence, drift). It validates the
LONG/SHORT level arrangement and persists idempotently into the same
``SignalStore`` the ``/signals`` API and monitor share. Never raises:
tracking must not break order flow — failures are logged only.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def record_bridge_acceptance(
    payload: Any,
    *,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    signal_id: str | None = None,
    source_agent: str = "signal-bridge",
) -> str | None:
    """Persist an accepted bridge signal; return its id (None on failure)."""
    try:
        if not isinstance(payload, dict):
            return None
        from app.api.signals import get_store

        decision = payload.get("final_decision")
        decision = decision if isinstance(decision, dict) else {}
        confidence = decision.get("confidence")
        try:
            confidence_value = (
                float(confidence) if confidence is not None else None
            )
        except (TypeError, ValueError):
            confidence_value = None
        risk = payload.get("risk_assessment")
        risk = risk if isinstance(risk, dict) else {}
        rr = risk.get("risk_reward")
        try:
            rr_value = float(rr) if rr is not None else None
        except (TypeError, ValueError):
            rr_value = None
        store = get_store()
        signal, _created = store.accept(
            signal_id=(signal_id or payload.get("signal_id")),
            symbol=str(payload.get("symbol") or ""),
            direction=str(decision.get("direction") or ""),
            timeframe=str(payload.get("timeframe") or ""),
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            take_profit=float(take_profit),
            risk_reward=rr_value,
            source_agent=source_agent,
            confidence=confidence_value,
            initial_price=float(entry_price),
            current_price=float(entry_price),
        )
        return signal.signal_id
    except Exception as exc:
        logger.warning("Signal tracking record failed (non-fatal): %s", exc)
        return None
