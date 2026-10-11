"""SQLite persistence for accepted signals + lifecycle event audit trail.

Tables (WAL mode, same pattern as ``HistoryStore``):

* ``tracked_signals`` — one row per accepted signal (current status).
* ``signal_events`` — append-only audit trail (never overwritten).

Idempotency: ``accept()`` is keyed on ``signal_id`` (UNIQUE); a repeat
acceptance of the same id returns the existing row without a duplicate
record or duplicate ``SIGNAL_ACCEPTED`` event.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.services.signal_tracking.models import (
    EVENT_MONITORING_STARTED,
    EVENT_SIGNAL_ACCEPTED,
    STATUS_ACTIVE,
    TrackedSignal,
    validate_signal,
)

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracked_signals (
    signal_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    risk_reward REAL,
    generated_at TEXT,
    accepted_at TEXT NOT NULL,
    source_agent TEXT,
    confidence REAL,
    status TEXT NOT NULL,
    initial_price REAL,
    current_price REAL,
    last_price_at TEXT,
    close_price REAL,
    closed_at TEXT,
    outcome TEXT
);
CREATE INDEX IF NOT EXISTS idx_tracked_signals_status
    ON tracked_signals(status);
CREATE INDEX IF NOT EXISTS idx_tracked_signals_symbol
    ON tracked_signals(symbol);
CREATE TABLE IF NOT EXISTS signal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    price REAL,
    detail TEXT,
    FOREIGN KEY (signal_id) REFERENCES tracked_signals(signal_id)
);
CREATE INDEX IF NOT EXISTS idx_signal_events_signal
    ON signal_events(signal_id);
"""

_lock = threading.Lock()


class SignalStore:
    """Thread-safe SQLite repository for tracked signals and events."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def initialise(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            conn = _connect(self.db_path)
            try:
                conn.executescript(_SCHEMA)
                conn.commit()
            finally:
                conn.close()

    def accept(
        self,
        *,
        signal_id: str | None = None,
        symbol: str,
        direction: str,
        timeframe: str = "",
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        risk_reward: float | None = None,
        generated_at: str | None = None,
        accepted_at: str | None = None,
        source_agent: str | None = None,
        confidence: float | None = None,
        initial_price: float | None = None,
        current_price: float | None = None,
    ) -> tuple[TrackedSignal, bool]:
        """Validate + persist (idempotent on signal_id)."""
        resolved, error = validate_signal(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        if error is not None:
            raise ValueError(error)
        assert resolved is not None
        import uuid as _uuid

        now = accepted_at or _now_iso()
        newcomer = TrackedSignal(
            signal_id=(signal_id or "").strip() or _uuid.uuid4().hex[:16],
            symbol=str(symbol).strip().upper(),
            direction=resolved,
            timeframe=str(timeframe or ""),
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            take_profit=float(take_profit),
            risk_reward=(float(risk_reward) if risk_reward is not None else None),
            generated_at=generated_at,
            accepted_at=now,
            source_agent=source_agent,
            confidence=(float(confidence) if confidence is not None else None),
            status=STATUS_ACTIVE,
            initial_price=(float(initial_price) if initial_price is not None else None),
            current_price=(
                float(current_price)
                if current_price is not None
                else (float(initial_price) if initial_price is not None else None)
            ),
            last_price_at=(
                now if (initial_price is not None or current_price is not None) else None
            ),
        )
        with _lock:
            conn = _connect(self.db_path)
            try:
                conn.executescript(_SCHEMA)
                existing = conn.execute(
                    "SELECT * FROM tracked_signals WHERE signal_id = ?",
                    (newcomer.signal_id,),
                ).fetchone()
                if existing is not None:
                    return self._row_to_signal(existing), False
                conn.execute(
                    "INSERT INTO tracked_signals (signal_id, symbol, direction,"
                    " timeframe, entry_price, stop_loss, take_profit,"
                    " risk_reward, generated_at, accepted_at, source_agent,"
                    " confidence, status, initial_price, current_price,"
                    " last_price_at, close_price, closed_at, outcome)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        newcomer.signal_id, newcomer.symbol, newcomer.direction,
                        newcomer.timeframe, newcomer.entry_price, newcomer.stop_loss,
                        newcomer.take_profit, newcomer.risk_reward,
                        newcomer.generated_at, newcomer.accepted_at,
                        newcomer.source_agent, newcomer.confidence, newcomer.status,
                        newcomer.initial_price, newcomer.current_price,
                        newcomer.last_price_at, None, None, None,
                    ),
                )
                self._append_event(
                    conn, newcomer.signal_id, EVENT_SIGNAL_ACCEPTED,
                    price=newcomer.current_price,
                    detail={
                        "direction": newcomer.direction,
                        "entry_price": newcomer.entry_price,
                        "stop_loss": newcomer.stop_loss,
                        "take_profit": newcomer.take_profit,
                    },
                )
                self._append_event(
                    conn, newcomer.signal_id, EVENT_MONITORING_STARTED,
                    price=newcomer.current_price,
                    detail={"status": newcomer.status},
                )
                conn.commit()
                return newcomer, True
            finally:
                conn.close()


    def get(self, signal_id: str) -> TrackedSignal | None:
        from app.services.signal_tracking import queries as _q

        return _q.get_signal(self, signal_id)

    def list_signals(self, **kwargs) -> list[TrackedSignal]:
        from app.services.signal_tracking import queries as _q

        return _q.list_signals(self, **kwargs)

    def list_active(self) -> list[TrackedSignal]:
        return self.list_signals(statuses=[STATUS_ACTIVE, "ACCEPTED"], limit=1000)

    def events(self, signal_id: str) -> list[dict]:
        from app.services.signal_tracking import queries as _q

        return _q.signal_events(self, signal_id)

    def summary(self) -> dict:
        from app.services.signal_tracking import queries as _q

        return _q.signal_summary(self)

    def update_price(
        self, signal_id: str, price: float, *, at: str | None = None
    ) -> TrackedSignal | None:
        from app.services.signal_tracking import writes as _w

        return _w.update_price(self, signal_id, price, at=at)

    def complete(self, signal_id: str, **kwargs):
        from app.services.signal_tracking import writes as _w

        return _w.complete_signal(self, signal_id, **kwargs)

    def log_monitoring_error(
        self, signal_id: str, message: str, *, price: float | None = None
    ) -> None:
        from app.services.signal_tracking import writes as _w

        _w.log_monitoring_error(self, signal_id, message, price=price)



    def _append_event(
        self, conn, signal_id: str, event_type: str,
        *, price: float | None, detail: dict | None,
    ) -> None:
        conn.execute(
            "INSERT INTO signal_events"
            " (signal_id, event_type, created_at, price, detail)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                signal_id, event_type, _now_iso(),
                (float(price) if price is not None else None),
                (json.dumps(detail) if detail is not None else None),
            ),
        )

    @staticmethod
    def _row_to_signal(row) -> TrackedSignal:
        return TrackedSignal(
            signal_id=str(row["signal_id"]),
            symbol=str(row["symbol"]),
            direction=str(row["direction"]),
            timeframe=str(row["timeframe"] or ""),
            entry_price=float(row["entry_price"]),
            stop_loss=float(row["stop_loss"]),
            take_profit=float(row["take_profit"]),
            risk_reward=(
                float(row["risk_reward"])
                if row["risk_reward"] is not None else None
            ),
            generated_at=(
                str(row["generated_at"])
                if row["generated_at"] is not None else None
            ),
            accepted_at=str(row["accepted_at"]),
            source_agent=(
                str(row["source_agent"])
                if row["source_agent"] is not None else None
            ),
            confidence=(
                float(row["confidence"])
                if row["confidence"] is not None else None
            ),
            status=str(row["status"]),
            initial_price=(
                float(row["initial_price"])
                if row["initial_price"] is not None else None
            ),
            current_price=(
                float(row["current_price"])
                if row["current_price"] is not None else None
            ),
            last_price_at=(
                str(row["last_price_at"])
                if row["last_price_at"] is not None else None
            ),
            close_price=(
                float(row["close_price"])
                if row["close_price"] is not None else None
            ),
            closed_at=(
                str(row["closed_at"])
                if row["closed_at"] is not None else None
            ),
            outcome=(
                str(row["outcome"])
                if row["outcome"] is not None else None
            ),
        )

def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    # Ensure schema on every connect: each ':memory:' connection is a fresh
    # database, and file DBs may be opened before initialise() in tests.
    conn.executescript(_SCHEMA)
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


