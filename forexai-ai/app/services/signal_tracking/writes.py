"""Monitoring writes for the signal store (split for edit size)."""

from __future__ import annotations

from app.services.signal_tracking.models import TERMINAL_STATUSES
from app.services.signal_tracking.store import _connect, _lock, _now_iso


def update_price(store, signal_id: str, price: float, *, at=None):
    moment = at or _now_iso()
    with _lock:
        conn = _connect(store.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM tracked_signals WHERE signal_id = ?",
                (signal_id,),
            ).fetchone()
            if row is None:
                return None
            if str(row["status"]) in TERMINAL_STATUSES:
                return store._row_to_signal(row)
            conn.execute(
                "UPDATE tracked_signals SET current_price = ?,"
                " last_price_at = ? WHERE signal_id = ?",
                (float(price), moment, signal_id),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM tracked_signals WHERE signal_id = ?",
                (signal_id,),
            ).fetchone()
            return store._row_to_signal(updated) if updated else None
        finally:
            conn.close()


def complete_signal(
    store,
    signal_id: str,
    *,
    status: str,
    close_price: float,
    event_type: str,
    detail: dict | None = None,
    at=None,
):
    """Mark terminal outcome exactly once; False when already terminal."""
    moment = at or _now_iso()
    with _lock:
        conn = _connect(store.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM tracked_signals WHERE signal_id = ?",
                (signal_id,),
            ).fetchone()
            if row is None:
                return None, False
            if str(row["status"]) in TERMINAL_STATUSES:
                return store._row_to_signal(row), False
            conn.execute(
                "UPDATE tracked_signals SET status = ?, close_price = ?,"
                " closed_at = ?, outcome = ?, current_price = ?,"
                " last_price_at = ? WHERE signal_id = ?",
                (
                    status, float(close_price), moment, status,
                    float(close_price), moment, signal_id,
                ),
            )
            store._append_event(
                conn, signal_id, event_type,
                price=float(close_price), detail=detail,
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM tracked_signals WHERE signal_id = ?",
                (signal_id,),
            ).fetchone()
            return (
                (store._row_to_signal(updated), True)
                if updated else (None, False)
            )
        finally:
            conn.close()


def log_monitoring_error(store, signal_id, message, *, price=None) -> None:
    from app.services.signal_tracking.models import EVENT_MONITORING_ERROR

    with _lock:
        conn = _connect(store.db_path)
        try:
            store._append_event(
                conn, signal_id, EVENT_MONITORING_ERROR,
                price=price, detail={"message": message},
            )
            conn.commit()
        finally:
            conn.close()
