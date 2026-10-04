"""MT5 broker package: terminal connection, market data, execution, sync.

Phase 1 ships the connection layer only. Execution (Phase 3) lives here
later, always dry-run first per the trading safety guardrails.
"""

from app.broker.mt5_connection import (
    MT5ConnectionError,
    connect,
    ensure_terminal_running,
    shutdown,
)

__all__ = [
    "MT5ConnectionError",
    "connect",
    "ensure_terminal_running",
    "shutdown",
]
