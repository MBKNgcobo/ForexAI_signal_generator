"""MT5 broker package: terminal connection, market data, execution, sync.

Phase 1 ships the connection layer only. Execution (Phase 3) lives here
later, always dry-run first per the trading safety guardrails.
"""

from app.broker.mt5_sync import MT5StateSynchronizer

__all__ = [
    "MT5ConnectionError",
    "MT5TradeExecutor",
    "OrderKind",
    "OrderRequest",
    "OrderResult",
    "OrderSide",
    "MT5StateSynchronizer",
    "connect",
    "shutdown",
    "ensure_terminal_running",
]
