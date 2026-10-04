"""MT5 position/order/account synchronization (Phase 4).

Keeps the bot's internal state aligned with the broker terminal:

- ``MT5StateSynchronizer.snapshot()`` pulls ``account_info``,
  ``positions_get`` and ``orders_get`` into immutable dataclasses.
- ``poll_once()`` diffs the new snapshot against the previous one and
  returns a ``SyncReport`` (opened/closed/modified positions and
  orders, balance/equity deltas) — the drift signal the execution
  layer needs to stay truthful.
- ``run()``/``start_background()`` poll on an interval in a daemon
  thread; on any MT5 failure the connection flag resets so the next
  tick reconnects (network dropouts and terminal restarts recover
  automatically instead of killing the worker).
- Read-only: this module never sends orders (see ``mt5_executor``).

``MetaTrader5`` is imported lazily inside ``_ensure_connected`` so
Linux/Docker imports and the hermetic suite keep working.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from app.broker.mt5_connection import MT5ConnectionError, connect, shutdown

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL = 2.0


class MT5SyncError(RuntimeError):
    """A sync data query failed (None result or terminal retcode)."""


@dataclass(frozen=True)
class AccountSnapshot:
    login: int
    balance: float
    equity: float
    margin: float
    margin_free: float
    currency: str
    trade_allowed: bool


@dataclass(frozen=True)
class Position:
    ticket: int
    symbol: str
    side: str  # "buy" | "sell"
    volume: float
    price_open: float
    price_current: float
    sl: float
    tp: float
    profit: float
    swap: float
    magic: int
    comment: str
    opened_at: datetime  # UTC


@dataclass(frozen=True)
class PendingOrder:
    ticket: int
    symbol: str
    kind: str  # "buy_limit" | "sell_limit" | "buy_stop" | "sell_stop"
    volume_initial: float
    volume_current: float
    price_open: float
    sl: float
    tp: float
    state: int
    magic: int
    comment: str


@dataclass(frozen=True)
class BrokerState:
    fetched_at: datetime
    account: AccountSnapshot
    positions: tuple[Position, ...]
    orders: tuple[PendingOrder, ...]


@dataclass(frozen=True)
class SyncReport:
    """Drift between the previous acknowledged state and this one."""

    initial: bool
    state: BrokerState
    opened_positions: tuple[int, ...] = ()
    closed_positions: tuple[int, ...] = ()
    modified_positions: tuple[int, ...] = ()
    opened_orders: tuple[int, ...] = ()
    cancelled_orders: tuple[int, ...] = ()
    modified_orders: tuple[int, ...] = ()
    balance_delta: float = 0.0
    equity_delta: float = 0.0

    @property
    def has_drift(self) -> bool:
        """True when anything meaningful changed since last poll."""

        if self.initial:
            return False
        return bool(
            self.opened_positions
            or self.closed_positions
            or self.modified_positions
            or self.opened_orders
            or self.cancelled_orders
            or self.modified_orders
            or self.balance_delta
            or self.equity_delta
        )


# Position/order type value fallbacks mirror the MT5 constants; the
# terminal's own attributes win when present.
_SIDE_BY_TYPE = {0: "buy", 1: "sell"}
_KIND_BY_TYPE = {
    2: "buy_limit",
    3: "sell_limit",
    4: "buy_stop",
    5: "sell_stop",
}


class MT5StateSynchronizer:
    """Poll broker state and diff it against the previous snapshot."""

    def __init__(
        self,
        login: int | None = None,
        password: str = "",
        server: str = "",
        path: str | None = None,
        timeout_seconds: float = 60.0,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        on_change: Callable[[SyncReport], None] | None = None,
    ):
        # ``login=None`` attaches to the open terminal session.
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.poll_interval = poll_interval
        self.on_change = on_change
        self._connected = False
        self._prev: BrokerState | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- connection -------------------------------------------------------

    def _ensure_connected(self) -> Any:
        if not self._connected:
            try:
                connect(
                    login=self.login,
                    password=self.password,
                    server=self.server,
                    path=self.path,
                    timeout_seconds=self.timeout_seconds,
                )
            except MT5ConnectionError as exc:
                raise MT5SyncError(
                    f"MT5 sync connection failed: {exc}"
                ) from exc
            self._connected = True

        from app.broker.mt5_connection import _import_mt5

        return _import_mt5()

    def close(self) -> None:
        self.stop()
        shutdown()
        self._connected = False

    # -- mapping ----------------------------------------------------------

    @staticmethod
    def _to_utc(epoch: Any) -> datetime:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc)

    @classmethod
    def _map_account(cls, info: Any) -> AccountSnapshot:
        return AccountSnapshot(
            login=int(getattr(info, "login", 0) or 0),
            balance=float(getattr(info, "balance", 0.0) or 0.0),
            equity=float(getattr(info, "equity", 0.0) or 0.0),
            margin=float(getattr(info, "margin", 0.0) or 0.0),
            margin_free=float(getattr(info, "margin_free", 0.0) or 0.0),
            currency=str(getattr(info, "currency", "") or ""),
            trade_allowed=bool(getattr(info, "trade_allowed", False)),
        )

    @classmethod
    def _map_position(cls, p: Any) -> Position:
        return Position(
            ticket=int(p.ticket),
            symbol=str(p.symbol),
            side=_SIDE_BY_TYPE.get(int(p.type), str(p.type)),
            volume=float(p.volume),
            price_open=float(p.price_open),
            price_current=float(getattr(p, "price_current", 0.0) or 0.0),
            sl=float(getattr(p, "sl", 0.0) or 0.0),
            tp=float(getattr(p, "tp", 0.0) or 0.0),
            profit=float(getattr(p, "profit", 0.0) or 0.0),
            swap=float(getattr(p, "swap", 0.0) or 0.0),
            magic=int(getattr(p, "magic", 0) or 0),
            comment=str(getattr(p, "comment", "") or ""),
            opened_at=cls._to_utc(getattr(p, "time", 0) or 0),
        )

    @classmethod
    def _map_order(cls, o: Any) -> PendingOrder:
        return PendingOrder(
            ticket=int(o.ticket),
            symbol=str(o.symbol),
            kind=_KIND_BY_TYPE.get(int(o.type), str(o.type)),
            volume_initial=float(getattr(o, "volume_initial", 0.0) or 0.0),
            volume_current=float(getattr(o, "volume_current", 0.0) or 0.0),
            price_open=float(o.price_open),
            sl=float(getattr(o, "sl", 0.0) or 0.0),
            tp=float(getattr(o, "tp", 0.0) or 0.0),
            state=int(getattr(o, "state", 0) or 0),
            magic=int(getattr(o, "magic", 0) or 0),
            comment=str(getattr(o, "comment", "") or ""),
        )

    # -- snapshot ---------------------------------------------------------

    def snapshot(self) -> BrokerState:
        """One coherent read of account + positions + pending orders."""

        mt5 = self._ensure_connected()

        info = mt5.account_info()

        if info is None:
            raise MT5SyncError(
                f"account_info returned None. last_error={mt5.last_error()}"
            )

        raw_positions = mt5.positions_get()

        if raw_positions is None:
            raise MT5SyncError(
                f"positions_get returned None. last_error={mt5.last_error()}"
            )

        raw_orders = mt5.orders_get()

        if raw_orders is None:
            raise MT5SyncError(
                f"orders_get returned None. last_error={mt5.last_error()}"
            )

        return BrokerState(
            fetched_at=datetime.now(timezone.utc),
            account=self._map_account(info),
            positions=tuple(
                self._map_position(p) for p in raw_positions
            ),
            orders=tuple(self._map_order(o) for o in raw_orders),
        )

    # -- diffing ----------------------------------------------------------

    def poll_once(self) -> SyncReport:
        """Snapshot + diff against the previous acknowledged state.

        On failure the connection flag drops so the *next* poll
        reconnects from scratch; the ``MT5SyncError`` still propagates
        to the caller for logging/metrics.
        """

        try:
            state = self.snapshot()
        except MT5SyncError:
            self._connected = False
            raise

        prev = self._prev
        report = self._diff(prev, state)
        self._prev = state

        logger.debug(
            "MT5 sync poll: initial=%s drift=%s positions=%d orders=%d",
            report.initial,
            report.has_drift,
            len(state.positions),
            len(state.orders),
        )

        return report

    @staticmethod
    def _diff(prev: BrokerState | None, state: BrokerState) -> SyncReport:
        if prev is None:
            return SyncReport(initial=True, state=state)

        prev_pos = {p.ticket: p for p in prev.positions}
        now_pos = {p.ticket: p for p in state.positions}
        prev_ord = {o.ticket: o for o in prev.orders}
        now_ord = {o.ticket: o for o in state.orders}

        return SyncReport(
            initial=False,
            state=state,
            opened_positions=tuple(
                sorted(set(now_pos) - set(prev_pos))
            ),
            closed_positions=tuple(
                sorted(set(prev_pos) - set(now_pos))
            ),
            modified_positions=tuple(
                sorted(
                    t
                    for t in set(now_pos) & set(prev_pos)
                    if now_pos[t] != prev_pos[t]
                )
            ),
            opened_orders=tuple(sorted(set(now_ord) - set(prev_ord))),
            cancelled_orders=tuple(
                sorted(set(prev_ord) - set(now_ord))
            ),
            modified_orders=tuple(
                sorted(
                    t
                    for t in set(now_ord) & set(prev_ord)
                    if now_ord[t] != prev_ord[t]
                )
            ),
            balance_delta=round(
                state.account.balance - prev.account.balance, 2
            ),
            equity_delta=round(
                state.account.equity - prev.account.equity, 2
            ),
        )

    # -- background worker -------------------------------------------------

    def run(
        self,
        stop_event: threading.Event | None = None,
        poll_interval: float | None = None,
        max_iterations: int | None = None,
    ) -> None:
        """Poll until ``stop_event`` at ``poll_interval`` seconds.

        Failures log a warning and reconnect on the next tick instead
        of terminating the loop. ``max_iterations`` bounds the loop for
        tests/scripts.
        """

        stop = stop_event or self._stop
        interval = (
            poll_interval if poll_interval is not None
            else self.poll_interval
        )
        iterations = 0

        logger.info(
            "MT5 sync worker started (interval=%.1fs).", interval
        )

        while not stop.is_set():
            try:
                report = self.poll_once()
            except MT5SyncError as exc:
                logger.warning(
                    "MT5 sync poll failed; will reconnect: %s", exc
                )
            except Exception as exc:  # never kill the worker
                logger.exception(
                    "Unexpected MT5 sync error: %s", exc
                )
            else:
                if report.has_drift:
                    logger.info(
                        "MT5 drift: +pos=%s -pos=%s ~pos=%s "
                        "+ord=%s -ord=%s ~ord=%s "
                        "dbal=%.2f deq=%.2f",
                        report.opened_positions,
                        report.closed_positions,
                        report.modified_positions,
                        report.opened_orders,
                        report.cancelled_orders,
                        report.modified_orders,
                        report.balance_delta,
                        report.equity_delta,
                    )

                    if self.on_change is not None:
                        try:
                            self.on_change(report)
                        except Exception as exc:
                            logger.error(
                                "on_change callback failed: %s", exc
                            )

            iterations += 1

            if max_iterations is not None and iterations >= max_iterations:
                break

            if stop.wait(interval):
                break

        logger.info("MT5 sync worker stopped.")

    def start_background(
        self, poll_interval: float | None = None
    ) -> threading.Thread:
        """Start ``run`` in a daemon thread; returns the thread."""

        if self._thread is not None and self._thread.is_alive():
            logger.info("MT5 sync worker already running.")
            return self._thread

        self._stop.clear()
        self._thread = threading.Thread(
            target=self.run,
            kwargs={"poll_interval": poll_interval},
            name="mt5-sync",
            daemon=True,
        )
        self._thread.start()

        return self._thread

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the background worker and wait briefly for it."""

        self._stop.set()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout)

            if self._thread.is_alive():
                logger.warning(
                    "MT5 sync worker did not stop within %.1fs.",
                    timeout,
                )


