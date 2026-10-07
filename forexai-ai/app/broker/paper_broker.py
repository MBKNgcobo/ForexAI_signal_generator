"""Paper trading broker: fills signals against live market data in a virtual account.

Implements the same ``send()`` contract as :class:`MT5TradeExecutor`
(returning an object with ``dry_run`` / ``payload`` / ``ticket`` /
``filled_price`` / ``filled_volume`` / ``comment``) so every existing gate in
:class:`SignalBridge` (HOLD/risk/SL-TP/drift/token) is reused untouched.
Never touches MetaTrader.

State flow
----------
1. ``send(req)`` gets the latest known price for ``symbol`` from an
   injectable sync price source (default: Twelve Data via a shared
   ``MarketDataService``), validates risk bounds, and records the order with
   a synthetic ticket.  The position is credited at an entry price that
   includes the configured spread cost (``PAPER_SPREAD_PIPS``).
2. A background monitor (``start_monitor``) polls every ``PAPER_POLL_SECONDS``
   seconds: for each open position, when the stop or take profit is touched,
   a ``closed`` event is recorded, the position settled, and the virtual
   balance updated.
3. All events are appended to the trade log (``trade_log.py``); account
   state persists to ``PAPER_STATE_PATH`` (gitignored) across restarts.

Errors (unexpected price, stale data, market closed) are logged and skipped;
the monitor never crashes.  Stale data beyond ``stale_seconds`` is treated
as a market-closed condition.  Kill-switch, duplicate-window, position-cap,
daily-loss and spread gates are enforced before every fill.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.broker.mt5_executor import OrderRequest, OrderSide
from app.broker.trade_log import TradeLogEntry, trade_log_append
from app.config import (
    duplicate_window_seconds,
    max_daily_loss,
    max_open_positions,
    max_spread_pips,
    paper_initial_balance,
    paper_poll_seconds,
    paper_spread_pips,
    paper_state_path,
    stop_file_path,
    trade_log_path,
)

logger = logging.getLogger(__name__)

# Sync price source: (symbol, side) -> (price, point_digits).
PriceSource = Callable[[str, OrderSide], tuple[float, float]]


class PaperBrokerError(RuntimeError):
    """Base error for the paper broker."""


class PaperNoTradeError(ValueError):
    """The signal must not trade (HOLD, risk not approved, duplicate, cap)."""


class PaperStateFileError(PaperBrokerError):
    """Persistent paper account state could not be read/written."""


class MarketClosedError(PaperBrokerError):
    """No usable price for the symbol right now (refresh or market closed)."""


@dataclass(frozen=True)
class PaperOrderResult:
    """Outcome of ``PaperBroker.send`` (same shape ``SignalBridge`` needs)."""

    dry_run: bool
    payload: dict
    ticket: int = 0
    retcode: int = 0
    filled_price: float | None = None
    filled_volume: float | None = None
    comment: str = ""
    raw: Any = field(default=None, repr=False)


@dataclass(frozen=True)
class PaperPosition:
    """A virtual position held by the paper broker."""

    symbol: str
    side: str
    ticket: int
    entry_price: float
    sl: float
    tp: float
    volume: float
    opened_at: float
    spread_pips: float = 0.0


@dataclass
class PaperAccountState:
    """Persisted virtual account state (JSON file, gitignored)."""

    balance: float
    initial_balance: float
    opened_at: float
    daily_ntl: float = 0.0
    daily_pl: float = 0.0
    positions: dict[int, PaperPosition] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> PaperAccountState:
        p = Path(path)
        if not p.exists():
            now = time.time()
            start = float(paper_initial_balance())
            return cls(
                balance=start,
                initial_balance=start,
                opened_at=now,
                daily_ntl=0.0,
                daily_pl=0.0,
                positions={},
            )
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise PaperStateFileError(f"Cannot read {p}: {exc}") from exc
        positions: dict[int, PaperPosition] = {}
        for key, val in (raw.get("positions") or {}).items():
            try:
                ticket = int(key)
                positions[ticket] = PaperPosition(
                    symbol=str(val["symbol"]),
                    side=str(val["side"]),
                    ticket=int(val.get("ticket", ticket)),
                    entry_price=float(val["entry_price"]),
                    sl=float(val["sl"]),
                    tp=float(val["tp"]),
                    volume=float(val["volume"]),
                    opened_at=float(val.get("opened_at", 0.0)),
                    spread_pips=float(val.get("spread_pips", 0.0)),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise PaperStateFileError(
                    f"Corrupt position {key!r} in {p}: {exc}"
                ) from exc
        return cls(
            balance=float(raw.get("balance", paper_initial_balance())),
            initial_balance=float(
                raw.get("initial_balance", paper_initial_balance())
            ),
            opened_at=float(raw.get("opened_at", 0.0)),
            daily_ntl=float(raw.get("daily_ntl", 0.0)),
            daily_pl=float(raw.get("daily_pl", 0.0)),
            positions=positions,
        )

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "balance": self.balance,
            "initial_balance": self.initial_balance,
            "opened_at": self.opened_at,
            "daily_ntl": self.daily_ntl,
            "daily_pl": self.daily_pl,
            "positions": {
                str(ticket): {
                    "symbol": pos.symbol,
                    "side": pos.side,
                    "ticket": pos.ticket,
                    "entry_price": pos.entry_price,
                    "sl": pos.sl,
                    "tp": pos.tp,
                    "volume": pos.volume,
                    "opened_at": pos.opened_at,
                    "spread_pips": pos.spread_pips,
                }
                for ticket, pos in self.positions.items()
            },
        }
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(p)

    @property
    def equity(self) -> float:
        return self.balance

    @property
    def open_count(self) -> int:
        return len(self.positions)


def make_service_price_source(
    service: Any,
    timeframe: str = "M15",
    limit: int = 2,
    stale_seconds: float = 120.0,
) -> PriceSource:
    """Build a sync price source from a shared async ``MarketDataService``.

    Uses the latest candle close as the price.  Raises ``MarketClosedError``
    when the feed is stale, empty, or errors (market closed, quota, 503).
    Runs the async fetch with ``asyncio.run`` in a worker thread when the
    caller's loop is already running (the bridge is a threaded sync server).
    """

    def _fetch(symbol: str) -> tuple[float, int, float]:
        async def _go() -> tuple[float, int, float]:
            data = await service.get_market_data(
                symbol=symbol, timeframe=timeframe, limit=limit
            )
            candles = getattr(data, "candles", None) or []
            if not candles:
                raise MarketClosedError(f"no candles for {symbol}.")
            last = candles[-1]
            price = float(getattr(last, "close", 0.0) or 0.0)
            if price <= 0:
                raise MarketClosedError(f"no usable price for {symbol}.")
            digits = 5 if price < 1000 else 2
            age_s = 0.0
            ts = getattr(last, "timestamp", None)
            if ts is not None:
                try:
                    from datetime import datetime, timezone

                    moment = ts
                    if isinstance(moment, str):
                        moment = datetime.fromisoformat(moment)
                    if getattr(moment, "tzinfo", None) is None:
                        moment = moment.replace(tzinfo=timezone.utc)
                    age_s = (
                        datetime.now(timezone.utc) - moment
                    ).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    age_s = 0.0
            return price, digits, age_s

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            price, digits, age_s = asyncio.run(_go())
        else:
            box: dict[str, Any] = {}

            def _runner() -> None:
                try:
                    box["ok"] = asyncio.run(_go())
                except Exception as exc:  # noqa: BLE001
                    box["err"] = exc

            worker = threading.Thread(target=_runner, daemon=True)
            worker.start()
            worker.join(timeout=60.0)
            if "ok" not in box:
                err = box.get("err", TimeoutError("price fetch timed out."))
                raise err if isinstance(err, Exception) else MarketClosedError(
                    f"no usable price for {symbol}."
                )
            price, digits, age_s = box["ok"]
        if age_s > stale_seconds:
            raise MarketClosedError(
                f"price for {symbol} is stale ({age_s:.0f}s old)."
            )
        return price, digits, age_s

    def _source(symbol: str, side: OrderSide) -> tuple[float, float]:
        price, digits, _age = _fetch(symbol)
        return price, float(digits)

    return _source


class PaperBroker:
    """Fills signals into a virtual account using live market data."""

    def __init__(
        self,
        price_source: PriceSource | None = None,
        service: Any | None = None,
        state_path: str | Path | None = None,
        log_path: str | Path | None = None,
        poll_seconds: float | None = None,
        stale_seconds: float = 120.0,
    ) -> None:
        if price_source is None and service is None:
            raise PaperBrokerError(
                "PaperBroker needs a price_source or a MarketDataService."
            )
        self.price_source: PriceSource = (
            price_source
            if price_source is not None
            else make_service_price_source(
                service, stale_seconds=stale_seconds
            )
        )
        self.state_path = Path(
            state_path if state_path is not None else paper_state_path()
        )
        self.log_path = Path(
            log_path if log_path is not None else trade_log_path()
        )
        self.poll_seconds = float(
            poll_seconds
            if poll_seconds is not None
            else paper_poll_seconds()
        )
        self.stale_seconds = float(stale_seconds)
        self.account = PaperAccountState.load(self.state_path)
        self._lock = threading.RLock()
        self._stop_flag = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._last_send: dict[str, float] = {}

    # -- lifecycle ----------------------------------------------------------

    def start_monitor(self) -> None:
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return
        self._stop_flag.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="paper-position-monitor",
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info(
            "Paper monitor started (interval %.0fs, stale %ds, state=%s).",
            self.poll_seconds,
            self.stale_seconds,
            self.state_path,
        )

    def stop_monitor(self) -> None:
        self._stop_flag.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=self.poll_seconds + 10.0)
        self._monitor_thread = None
        logger.info("Paper monitor stopped.")


    # -- public API ---------------------------------------------------------

    def send(
        self, req: OrderRequest, dry_run: bool | None = None
    ) -> PaperOrderResult:
        if dry_run is False:
            raise PaperNoTradeError(
                "PAPER mode is simulated and can never send live orders."
            )
        with self._lock:
            self._enforce_paper_gates(req)
            price, point = self._current_price(req.symbol, req.side)
            spread_pips = float(paper_spread_pips())
            spread_cost = self._spread_cost(price, point, spread_pips)
            if req.side is OrderSide.BUY:
                entry = price + spread_cost
            else:
                entry = price - spread_cost
            ticket = self._next_ticket()
            self._record_order(req, ticket, entry, spread_pips)
            age = self._data_age(req.symbol)
            logger.info(
                "PAPER fill %s %s vol=%.2f sl=%.4f tp=%.4f entry=%.5f "
                "(spread %.2f pips, data age=%s).",
                req.symbol, req.side, req.volume, req.sl, req.tp, entry,
                spread_pips, age,
            )
            return PaperOrderResult(
                dry_run=True,
                payload=self._build_payload(req, ticket, entry),
                ticket=ticket,
                retcode=0,
                filled_price=entry,
                filled_volume=req.volume,
                comment="paper: simulated fill at price + spread cost",
            )

    def close(self, ticket: int) -> float | None:
        """Manually close one open paper position; returns realized PnL."""
        return self._close_position(ticket)

    # -- gates --------------------------------------------------------------

    def _enforce_paper_gates(self, req: OrderRequest) -> None:
        if req.volume is None or req.volume <= 0:
            raise PaperNoTradeError("volume must be > 0.")
        if req.sl is None or req.tp is None:
            raise PaperNoTradeError("paper fills require SL and TP.")
        if Path(stop_file_path()).exists():
            self._log_rejected(req, "kill switch active (stop file).")
            raise PaperNoTradeError(
                "Kill switch active: stop file present; refusing paper fill."
            )
        window = float(duplicate_window_seconds())
        if window > 0:
            key = f"{req.symbol}:{req.side.value}"
            now = time.time()
            last = self._last_send.get(key, 0.0)
            if now - last < window:
                self._log_rejected(req, "duplicate signal within window.")
                raise PaperNoTradeError(
                    f"Duplicate {req.symbol} {req.side.value} "
                    f"within {window:.0f}s window."
                )
        cap = int(max_open_positions())
        if cap > 0 and self.account.open_count >= cap:
            self._log_rejected(req, "max open positions reached.")
            raise PaperNoTradeError(
                f"Max open positions ({cap}) reached; refusing paper fill."
            )
        floor = float(max_daily_loss())
        if floor > 0 and self.account.daily_pl <= -abs(floor):
            self._log_rejected(req, "daily loss cap reached.")
            raise PaperNoTradeError(
                "Daily loss cap reached; refusing paper fill."
            )
        spread_cap = float(max_spread_pips())
        if spread_cap > 0:
            spread = float(paper_spread_pips())
            if spread > spread_cap:
                self._log_rejected(req, "spread above cap.")
                raise PaperNoTradeError(
                    f"Spread {spread:.1f} pips above cap {spread_cap:.1f}."
                )

    # -- price --------------------------------------------------------------

    def _current_price(
        self, symbol: str, side: OrderSide
    ) -> tuple[float, float]:
        try:
            price, point = self.price_source(symbol, side)
        except (MarketClosedError, PaperBrokerError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise MarketClosedError(
                f"no usable price for {symbol}: {exc}"
            ) from exc
        if price <= 0:
            raise MarketClosedError(f"no usable price for {symbol}.")
        return float(price), float(point)

    def _data_age(self, symbol: str) -> str:
        return "live"

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _spread_cost(price: float, point: float, spread_pips: float) -> float:
        pip_size = 10.0 ** (-point) * 10.0 if point > 0 else 0.0
        return pip_size * spread_pips

    def _next_ticket(self) -> int:
        existing = list(self.account.positions.keys())
        return max(existing) + 1 if existing else 100000

    @staticmethod
    def _now() -> float:
        return time.time()

    @staticmethod
    def _date() -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    @staticmethod
    def _time() -> str:
        return time.strftime("%H:%M:%S", time.gmtime())

    @staticmethod
    def _mode() -> str:
        return "paper"

    def _build_payload(
        self, req: OrderRequest, ticket: int, entry: float
    ) -> dict:
        return {
            "type": "paper_fill",
            "symbol": req.symbol,
            "side": req.side.value,
            "volume": req.volume,
            "sl": req.sl,
            "tp": req.tp,
            "price": entry,
            "ticket": ticket,
            "magic": 0,
            "comment": "paper simulated fill",
            "dry_run": True,
        }


    def _record_order(
        self,
        req: OrderRequest,
        ticket: int,
        entry: float,
        spread_pips: float,
    ) -> None:
        pos = PaperPosition(
            symbol=req.symbol,
            side=req.side.value,
            ticket=ticket,
            entry_price=entry,
            sl=float(req.sl) if req.sl is not None else 0.0,
            tp=float(req.tp) if req.tp is not None else 0.0,
            volume=float(req.volume),
            opened_at=time.time(),
            spread_pips=spread_pips,
        )
        self.account.positions[ticket] = pos
        self.account.save(self.state_path)
        self._last_send[f"{req.symbol}:{req.side.value}"] = time.time()
        date_s = self._date()
        time_s = self._time()
        trade_log_append(
            self.log_path,
            TradeLogEntry(
                date=date_s,
                time=time_s,
                mode=self._mode(),
                symbol=req.symbol,
                direction=req.side.value,
                ticket=ticket,
                price=entry,
                sl=pos.sl,
                tp=pos.tp,
                volume=pos.volume,
                spread_pips=spread_pips,
                reason="paper fill accepted",
                event_type="filled",
            ),
        )

    def _log_rejected(self, req: OrderRequest, reason: str) -> None:
        trade_log_append(
            self.log_path,
            TradeLogEntry(
                date=self._date(),
                time=self._time(),
                mode=self._mode(),
                symbol=req.symbol,
                direction=req.side.value,
                ticket=0,
                price=0.0,
                sl=float(req.sl or 0.0),
                tp=float(req.tp or 0.0),
                volume=float(req.volume or 0.0),
                spread_pips=float(paper_spread_pips()),
                reason=reason,
                event_type="signal_rejected",
            ),
        )

    def _monitor_loop(self) -> None:
        while not self._stop_flag.is_set():
            try:
                self._check_positions()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Paper monitor cycle skipped: %s", exc)
            self._stop_flag.wait(float(self.poll_seconds))

    def _check_positions(self) -> None:
        with self._lock:
            positions = list(self.account.positions.values())
        touched: list[int] = []
        for pos in positions:
            try:
                price, _point = self._current_price(
                    pos.symbol,
                    OrderSide.BUY if pos.side == "buy" else OrderSide.SELL,
                )
            except (MarketClosedError, PaperBrokerError) as exc:
                logger.debug("Paper monitor skip %s: %s", pos.symbol, exc)
                continue
            if price <= 0:
                continue
            if pos.side == "buy":
                hit = price <= pos.sl or price >= pos.tp
            else:
                hit = price >= pos.sl or price <= pos.tp
            if hit:
                touched.append(pos.ticket)
        for ticket in touched:
            try:
                self._close_position(ticket)
            except (MarketClosedError, PaperBrokerError) as exc:
                logger.debug("Paper close deferred ticket=%s: %s", ticket, exc)

    def _close_position(self, ticket: int) -> float | None:
        with self._lock:
            pos = self.account.positions.get(ticket)
            if pos is None:
                return None
        price, _point = self._current_price(
            pos.symbol,
            OrderSide.BUY if pos.side == "buy" else OrderSide.SELL,
        )
        if price <= 0:
            return None
        pnl = self._position_pnl(pos, price)
        with self._lock:
            if ticket not in self.account.positions:
                return None
            del self.account.positions[ticket]
            self.account.daily_pl += pnl
            self.account.balance += pnl
            if self.account.daily_pl < self.account.daily_ntl:
                self.account.daily_ntl = self.account.daily_pl
            self.account.save(self.state_path)
        self._log_closed_event(pos, price, pnl)
        logger.info(
            "PAPER closed %s ticket=%s exit=%.5f pnl=%.2f (bal=%.2f).",
            pos.symbol, ticket, price, pnl, self.account.balance,
        )
        return pnl

    @staticmethod
    def _position_pnl(pos: PaperPosition, exit_price: float) -> float:
        contract = 100_000.0
        if pos.side == "buy":
            diff = exit_price - pos.entry_price
        else:
            diff = pos.entry_price - exit_price
        if pos.entry_price > 1000 or exit_price > 1000:
            per_lot = diff / exit_price * contract if exit_price else 0.0
        else:
            per_lot = diff * contract
        return per_lot * pos.volume

    def _log_closed_event(
        self, pos: PaperPosition, exit_price: float, pnl: float
    ) -> None:
        trade_log_append(
            self.log_path,
            TradeLogEntry(
                date=self._date(),
                time=self._time(),
                mode=self._mode(),
                symbol=pos.symbol,
                direction=pos.side,
                ticket=pos.ticket,
                price=exit_price,
                sl=pos.sl,
                tp=pos.tp,
                volume=pos.volume,
                spread_pips=pos.spread_pips,
                reason=f"paper closed ({pnl:+.2f})",
                event_type="closed",
            ),
        )

    def _stop_file_present(self) -> bool:
        return Path(stop_file_path()).exists()

