"""Append-only thread-safe JSONL trade/signal log.

Used by :mod:`paper_broker` for paper mode and by the MT5 sync watcher to
record real demo orders.  Events are never overwritten or truncated: each
line is one JSON object carrying one event.

Event types
-----------
signal_rejected : signal was refused by a gate (HOLD, risk not approved,
                  duplicate, kill switch, daily-loss cap, spread gate).
order_sent       : order was accepted and submitted.
filled           : order was filled (paper) / accepted (MT5).
closed           : position closed (paper SL/TP or MT5 close).
breaker_trip     : emergency stop file present; not a real close.

The log path is configurable (``TRADE_LOG_PATH``) and the file is gitignored.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TradeLogError(RuntimeError):
    """Base error for the trade log."""


class TradeLogPathError(TradeLogError):
    """Could not resolve the trade log path."""


@dataclass(frozen=True)
class TradeLogEntry:
    """A single record appended to the log."""

    date: str
    time: str
    mode: str
    symbol: str
    direction: str
    ticket: int
    price: float
    sl: float
    tp: float
    volume: float
    spread_pips: float
    reason: str
    event_type: str = "filled"


def _default_path() -> str:
    from app.config import trade_log_path

    return trade_log_path()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_locale() -> tuple[str, str]:
    now = datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")


def trade_log_append(log_path: str | Path, entry: TradeLogEntry) -> None:
    """Append one event to the JSONL log (thread-safe)."""
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    record: dict[str, Any] = {
        "timestamp_utc": _now_iso(),
        "date": entry.date,
        "time": entry.time,
        "mode": entry.mode,
        "event": entry.event_type,
        "symbol": entry.symbol,
        "direction": entry.direction,
        "ticket": entry.ticket,
        "price": entry.price,
        "sl": entry.sl,
        "tp": entry.tp,
        "volume": entry.volume,
        "spread_pips": entry.spread_pips,
        "reason": entry.reason,
    }

    lock = _file_lock(path)
    with lock:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
    logger.debug("Trade log appended: %s", entry.event_type)



_LOCKS: dict[Path, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _file_lock(path: Path) -> threading.Lock:
    key = Path(path)
    lock = _LOCKS.get(key)
    if lock is None:
        with _LOCKS_GUARD:
            lock = _LOCKS.get(key)
            if lock is None:
                lock = threading.Lock()
                _LOCKS[key] = lock
    return lock


class TradeLog:
    """Convenience wrapper binding a log path to append/read helpers."""

    def __init__(self, log_path: str | Path | None = None) -> None:
        self.log_path = Path(log_path) if log_path else Path(_default_path())

    def append(self, entry: TradeLogEntry) -> None:
        trade_log_append(self.log_path, entry)

    def read_all(self) -> list[dict[str, Any]]:
        return trade_log_read_all(self.log_path)

    def read_events(self, event: str) -> list[dict[str, Any]]:
        return [r for r in self.read_all() if r.get("event") == event]


def trade_log_read_all(log_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Read every record from the JSONL log (skips blank/corrupt lines)."""
    path = Path(log_path) if log_path else Path(_default_path())
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with _file_lock(path):
        text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Skipping corrupt trade-log line in %s.", path)
    return records
