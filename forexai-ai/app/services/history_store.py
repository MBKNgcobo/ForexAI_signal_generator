"""Persistent rolling-window store for the History Node (SQLite + WAL)."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history_bars (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    true_range REAL NOT NULL,
    PRIMARY KEY (symbol, timeframe, ts)
);
CREATE TABLE IF NOT EXISTS history_windows (
    symbol TEXT NOT NULL,
    window TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (symbol, window)
);
CREATE TABLE IF NOT EXISTS strategy_snapshot (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    payload TEXT NOT NULL,
    computed_at TEXT NOT NULL
);
"""

_lock = threading.Lock()


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(
        db_path,
        timeout=10.0,
        check_same_thread=False,
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


class HistoryStore:
    """SQLite persistence for bars, window aggregates and snapshot."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def initialise(self) -> None:
        """Create schema (and parent dirs). Raises on failure."""

        try:
            Path(self.db_path).parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            with _lock:
                conn = _connect(self.db_path)
                try:
                    conn.executescript(_SCHEMA)
                    conn.commit()
                finally:
                    conn.close()
        except Exception as exc:
            logger.error(
                "HistoryStore initialise failed for %s: %s",
                self.db_path,
                exc,
            )
            raise

    def upsert_bars(
        self,
        rows: list[dict],
        *,
        retention_days: int = 7,
        now: datetime | None = None,
    ) -> int:
        """Insert closed bars (INSERT OR REPLACE). Returns rows written."""

        if not rows:
            return 0

        moment = now or datetime.now(timezone.utc)
        cutoff = (moment - timedelta(days=retention_days)).isoformat()

        with _lock:
            conn = _connect(self.db_path)
            try:
                conn.executescript(_SCHEMA)
                conn.executemany(
                    "INSERT OR REPLACE INTO history_bars"
                    " (symbol, timeframe, ts, open, high, low, close,"
                    " true_range)"
                    " VALUES (:symbol, :timeframe, :ts, :open, :high,"
                    " :low, :close, :true_range)",
                    rows,
                )
                conn.execute(
                    "DELETE FROM history_bars WHERE ts < ?",
                    (cutoff,),
                )
                conn.commit()
            finally:
                conn.close()

        return len(rows)

    def fetch_window_bars(
        self,
        symbol: str,
        timeframe: str,
        *,
        lookback_hours: int,
        now: datetime | None = None,
    ) -> list[dict]:
        """Rolling fetch: ts >= now - lookback_hours, ascending."""

        moment = now or datetime.now(timezone.utc)
        cutoff = (moment - timedelta(hours=lookback_hours)).isoformat()
        conn = _connect(self.db_path)
        try:
            cur = conn.execute(
                "SELECT symbol, timeframe, ts, open, high, low,"
                " close, true_range FROM history_bars"
                " WHERE symbol = ? AND timeframe = ? AND ts >= ?"
                " ORDER BY ts ASC",
                (symbol, timeframe, cutoff),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def latest_ts(
        self,
        symbol: str,
        timeframe: str,
    ) -> str | None:
        """Newest stored bar timestamp (for delta fetches)."""

        conn = _connect(self.db_path)
        try:
            cur = conn.execute(
                "SELECT MAX(ts) FROM history_bars"
                " WHERE symbol = ? AND timeframe = ?",
                (symbol, timeframe),
            )
            row = cur.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def save_window(
        self,
        symbol: str,
        window: str,
        payload: dict,
    ) -> None:
        """Upsert one derived window aggregate."""

        with _lock:
            conn = _connect(self.db_path)
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO history_windows"
                    " (symbol, window, computed_at, payload)"
                    " VALUES (?, ?, ?, ?)",
                    (
                        symbol,
                        window,
                        datetime.now(timezone.utc).isoformat(),
                        json.dumps(payload),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def save_snapshot(self, payload: dict) -> None:
        """Upsert the single global strategy snapshot row."""

        with _lock:
            conn = _connect(self.db_path)
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO strategy_snapshot"
                    " (id, payload, computed_at) VALUES (1, ?, ?)",
                    (
                        json.dumps(payload),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def load_snapshot(self) -> dict | None:
        """Load the global snapshot dict, or None when absent."""

        conn = _connect(self.db_path)
        try:
            cur = conn.execute(
                "SELECT payload FROM strategy_snapshot WHERE id = 1"
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if not row:
            return None

        try:
            data = json.loads(row[0])
        except Exception as exc:
            logger.error("History snapshot JSON corrupt: %s", exc)
            raise ValueError(f"corrupt snapshot: {exc}") from exc

        return data if isinstance(data, dict) else None


