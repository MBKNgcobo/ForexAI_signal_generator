"""Read + summary queries for the signal store (split for edit size)."""

from __future__ import annotations

import json
from typing import Any

from app.services.signal_tracking.models import (
    STATUS_ACTIVE,
    TrackedSignal,
    normalize_direction,
)
from app.services.signal_tracking.store import _connect


def get_signal(store, signal_id: str) -> TrackedSignal | None:
    conn = _connect(store.db_path)
    try:
        row = conn.execute(
            "SELECT * FROM tracked_signals WHERE signal_id = ?",
            (signal_id,),
        ).fetchone()
    finally:
        conn.close()
    return store._row_to_signal(row) if row is not None else None


def list_signals(
    store,
    *,
    status: str | None = None,
    statuses: list[str] | None = None,
    symbol: str | None = None,
    direction: str | None = None,
    outcome: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 200,
) -> list[TrackedSignal]:
    clauses: list[str] = []
    params: list[Any] = []
    wanted = list(statuses or [])
    if status:
        wanted.append(status)
    if wanted:
        clauses.append("status IN (%s)" % ",".join("?" for _ in wanted))
        params.extend(wanted)
    if symbol:
        clauses.append("symbol = ?")
        params.append(symbol.strip().upper())
    if direction:
        resolved = normalize_direction(direction)
        if resolved:
            clauses.append("direction = ?")
            params.append(resolved)
    if outcome:
        clauses.append("outcome = ?")
        params.append(outcome)
    if since:
        clauses.append("accepted_at >= ?")
        params.append(since)
    if until:
        clauses.append("accepted_at <= ?")
        params.append(until)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    conn = _connect(store.db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM tracked_signals" + where
            + " ORDER BY accepted_at DESC LIMIT ?",
            (*params, max(1, min(int(limit), 1000))),
        ).fetchall()
    finally:
        conn.close()
    return [store._row_to_signal(row) for row in rows]


def signal_events(store, signal_id: str) -> list[dict]:
    conn = _connect(store.db_path)
    try:
        rows = conn.execute(
            "SELECT signal_id, event_type, created_at, price, detail"
            " FROM signal_events WHERE signal_id = ? ORDER BY id ASC",
            (signal_id,),
        ).fetchall()
    finally:
        conn.close()
    out: list[dict] = []
    for row in rows:
        detail = None
        if row["detail"]:
            try:
                detail = json.loads(row["detail"])
            except (TypeError, ValueError):
                detail = {"raw": row["detail"]}
        out.append(
            {
                "signal_id": row["signal_id"],
                "event_type": row["event_type"],
                "created_at": row["created_at"],
                "price": row["price"],
                "detail": detail,
            }
        )
    return out


def signal_summary(store) -> dict:
    conn = _connect(store.db_path)
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n"
            " FROM tracked_signals GROUP BY status"
        ).fetchall()
    finally:
        conn.close()
    total = 0
    active = 0
    tp_hits = 0
    sl_hits = 0
    cancelled_or_unresolved = 0
    for row in rows:
        n = int(row["n"])
        total += n
        status = str(row["status"])
        if status in ("ACCEPTED", STATUS_ACTIVE):
            active += n
        elif status == "TAKE_PROFIT_HIT":
            tp_hits += n
        elif status == "STOP_LOSS_HIT":
            sl_hits += n
        elif status in ("CANCELLED", "EXPIRED", "OUTCOME_UNRESOLVED"):
            cancelled_or_unresolved += n
    decided = tp_hits + sl_hits
    return {
        "total_accepted": total,
        "active": active,
        "take_profit_hits": tp_hits,
        "stop_loss_hits": sl_hits,
        "cancelled_or_unresolved": cancelled_or_unresolved,
        "outcome_rate": (tp_hits / decided) if decided else None,
        "outcome_rate_note": (
            "TP-hit rate over TP+SL outcomes only; not profitability."
        ),
    }
