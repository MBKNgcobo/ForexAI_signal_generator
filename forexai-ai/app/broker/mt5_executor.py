"""MT5 trade execution (Phase 3) — dry-run by default.

Sends market, limit and stop orders to the local terminal with a
rigid risk contract: every payload MUST carry SL and TP, validated
against the reference price before the terminal ever sees it.

Safety model:
- ``MT5_DRY_RUN`` (default **true**) — dry-run builds and logs the
  exact payload dict but never calls ``order_send``. Going live is a
  deliberate, explicit opt-out.
- Request problems raise ``ValueError`` (caller error); terminal or
  retcode failures raise ``MT5ExecutionError`` (a ``RuntimeError`` so
  the HTTP layer maps it to 503) always carrying ``mt5.last_error()``
  or the MT5 retcode (``10009`` = success).
- ``MetaTrader5`` is imported lazily inside ``_ensure_connected``
  only — Linux/Docker imports and the hermetic suite stay safe.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.broker.mt5_connection import MT5ConnectionError, connect, shutdown
from app.broker.mt5_market_data_provider import MT5MarketDataProvider
from app.config import mt5_dry_run

logger = logging.getLogger(__name__)

MT5_RETCODE_SUCCESS = 10009


class MT5ExecutionError(RuntimeError):
    """The terminal rejected an order or the IPC call failed."""


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderKind(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


@dataclass(frozen=True)
class OrderRequest:
    """A single order intent. SL and TP are mandatory, always."""

    symbol: str
    side: OrderSide
    order_kind: OrderKind
    volume: float
    sl: float
    tp: float
    price: float | None = None  # required for limit/stop
    deviation: int = 20  # max slippage, in points
    magic: int = 0
    comment: str = ""

    def __post_init__(self) -> None:
        # Accept plain strings too ("buy" / "limit") — coerce once so
        # every downstream check can rely on enum identity.
        object.__setattr__(self, "side", OrderSide(self.side))
        object.__setattr__(self, "order_kind", OrderKind(self.order_kind))

        if self.volume <= 0:
            raise ValueError("volume must be > 0.")
        if self.sl <= 0 or self.tp <= 0:
            raise ValueError(
                "Stop Loss and Take Profit are mandatory for every "
                "order (sl > 0, tp > 0)."
            )
        if self.sl == self.tp:
            raise ValueError("sl and tp must differ.")
        if self.order_kind is not OrderKind.MARKET and self.price is None:
            raise ValueError(
                f"{self.order_kind.value} orders require a price."
            )
        if self.price is not None and self.price <= 0:
            raise ValueError("price must be > 0 when provided.")


@dataclass(frozen=True)
class OrderResult:
    """Outcome of ``send`` (``dry_run=True`` means never sent)."""

    dry_run: bool
    payload: dict
    retcode: int | None = None
    ticket: int | None = None
    filled_price: float | None = None
    filled_volume: float | None = None
    comment: str = ""
    raw: Any = field(default=None, repr=False)


class MT5TradeExecutor:
    """Build and send orders; dry-run unless explicitly configured live."""

    def __init__(
        self,
        login: int | None = None,
        password: str = "",
        server: str = "",
        path: str | None = None,
        timeout_seconds: float = 60.0,
        dry_run: bool | None = None,
    ):
        # ``login=None`` attaches to the open terminal session; the
        # factory/service always passes credentials for unattended use.
        # ``dry_run=None`` defers to config ``mt5_dry_run()`` (true).
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.dry_run = dry_run
        self._connected = False

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
                raise MT5ExecutionError(
                    f"MT5 execution connection failed: {exc}"
                ) from exc
            self._connected = True

        from app.broker.mt5_connection import _import_mt5

        return _import_mt5()

    def close(self) -> None:
        shutdown()
        self._connected = False

    # -- payload building -------------------------------------------------

    @staticmethod
    def _resolve_symbol(mt5: Any, symbol: str) -> str:
        # Reuse the provider's suffix-sanitation so data and execution
        # always agree on the broker symbol.
        return MT5MarketDataProvider._resolve_symbol(mt5, symbol)

    @staticmethod
    def _filling_type(mt5: Any, info: Any) -> int:
        """Pick FOK/IOC/RETURN from the symbol's filling_mode bits."""

        mode = int(getattr(info, "filling_mode", 0) or 0)

        if mode & 1:  # SYMBOL_FILLING_FOK allowed
            return int(mt5.ORDER_FILLING_FOK)
        if mode & 2:  # SYMBOL_FILLING_IOC allowed
            return int(mt5.ORDER_FILLING_IOC)
        return int(mt5.ORDER_FILLING_RETURN)

    @staticmethod
    def _order_type(mt5: Any, side: OrderSide, kind: OrderKind) -> int:
        if kind is OrderKind.MARKET:
            name = "ORDER_TYPE_BUY" if side is OrderSide.BUY \
                else "ORDER_TYPE_SELL"
        elif kind is OrderKind.LIMIT:
            name = "ORDER_TYPE_BUY_LIMIT" if side is OrderSide.BUY \
                else "ORDER_TYPE_SELL_LIMIT"
        else:
            name = "ORDER_TYPE_BUY_STOP" if side is OrderSide.BUY \
                else "ORDER_TYPE_SELL_STOP"
        return int(getattr(mt5, name))

    @staticmethod
    def _validate_risk_bounds(
        req: OrderRequest, reference: float
    ) -> None:
        """SL/TP must bracket the fill price on the correct sides."""

        if req.side is OrderSide.BUY:
            ok = req.sl < reference < req.tp
            detail = "BUY needs sl < fill price < tp"
        else:
            ok = req.tp < reference < req.sl
            detail = "SELL needs tp < fill price < sl"

        if not ok:
            raise ValueError(
                f"Risk bounds invalid for {req.side.value}: {detail} "
                f"(sl={req.sl}, tp={req.tp}, reference={reference})."
            )

    def build_payload(
        self, mt5: Any, req: OrderRequest
    ) -> tuple[str, dict]:
        """Map an ``OrderRequest`` to the ``order_send`` dict.

        Raises ``ValueError`` for request problems (bad risk bounds,
        volume outside symbol limits) and ``MT5ExecutionError`` when
        the terminal cannot provide tick/symbol data. Also used by
        tests and the dry-run script to inspect the exact payload.
        """

        broker_symbol = self._resolve_symbol(mt5, req.symbol)
        info = mt5.symbol_info(broker_symbol)

        if info is None:
            raise MT5ExecutionError(
                f"symbol_info returned None for {broker_symbol}. "
                f"last_error={mt5.last_error()}"
            )

        digits = int(getattr(info, "digits", 5) or 5)

        if req.order_kind is OrderKind.MARKET:
            tick = mt5.symbol_info_tick(broker_symbol)

            if tick is None:
                raise MT5ExecutionError(
                    f"symbol_info_tick returned None for "
                    f"{broker_symbol}. last_error={mt5.last_error()}"
                )

            reference = float(tick.ask) if req.side is OrderSide.BUY \
                else float(tick.bid)
            action = mt5.TRADE_ACTION_DEAL
        else:
            reference = float(req.price or 0.0)
            action = mt5.TRADE_ACTION_PENDING

        self._validate_risk_bounds(req, reference)

        v_min = float(getattr(info, "volume_min", 0.0) or 0.0)
        v_max = float(getattr(info, "volume_max", 0.0) or 0.0)

        if v_min and req.volume < v_min:
            raise ValueError(
                f"volume {req.volume} below symbol minimum {v_min}."
            )
        if v_max and req.volume > v_max:
            raise ValueError(
                f"volume {req.volume} above symbol maximum {v_max}."
            )

        payload = {
            "action": int(action),
            "symbol": broker_symbol,
            "volume": float(req.volume),
            "type": self._order_type(mt5, req.side, req.order_kind),
            "price": round(reference, digits),
            "sl": round(float(req.sl), digits),
            "tp": round(float(req.tp), digits),
            "deviation": int(req.deviation),
            "magic": int(req.magic),
            "comment": req.comment,
            "type_time": int(mt5.ORDER_TIME_GTC),
            "type_filling": self._filling_type(mt5, info),
        }

        return broker_symbol, payload

    # -- sending ----------------------------------------------------------

    def send(
        self, req: OrderRequest, dry_run: bool | None = None
    ) -> OrderResult:
        """Validate, build and (unless dry-run) send one order.

        Dry-run precedence: explicit ``dry_run`` argument > executor
        setting > ``MT5_DRY_RUN`` config (default true). Success means
        retcode 10009 (done) or 10010 (done partial); anything else
        raises ``MT5ExecutionError`` with the retcode attached.
        """

        mt5 = self._ensure_connected()
        broker_symbol, payload = self.build_payload(mt5, req)

        effective_dry = (
            dry_run
            if dry_run is not None
            else (
                self.dry_run
                if self.dry_run is not None
                else mt5_dry_run()
            )
        )

        logger.info(
            "MT5 order payload (%s): %s",
            "DRY-RUN" if effective_dry else "LIVE",
            payload,
        )

        if effective_dry:
            logger.warning(
                "DRY-RUN: %s %s %s vol=%.2f sl=%.5f tp=%.5f NOT sent.",
                broker_symbol,
                req.side,
                req.order_kind,
                req.volume,
                req.sl,
                req.tp,
            )
            return OrderResult(
                dry_run=True,
                payload=payload,
                filled_price=float(payload["price"]),
                filled_volume=float(payload["volume"]),
                comment="dry-run: order not sent",
            )

        try:
            result = mt5.order_send(payload)
        except Exception as exc:
            raise MT5ExecutionError(
                f"order_send raised {type(exc).__name__}: {exc}. "
                f"last_error={mt5.last_error()}"
            ) from exc

        if result is None:
            raise MT5ExecutionError(
                f"order_send returned None for {broker_symbol}. "
                f"last_error={mt5.last_error()}"
            )

        retcode = int(getattr(result, "retcode", 0))
        comment = str(getattr(result, "comment", "") or "")

        if retcode not in (10009, 10010):  # done | done partial
            raise MT5ExecutionError(
                f"MT5 order rejected: retcode={retcode} "
                f"comment={comment!r} payload={payload}"
            )

        ticket = int(getattr(result, "order", 0))

        logger.info(
            "MT5 order accepted: ticket=%s retcode=%s price=%s "
            "volume=%s comment=%r",
            ticket,
            retcode,
            getattr(result, "price", None),
            getattr(result, "volume", None),
            comment,
        )

        return OrderResult(
            dry_run=False,
            payload=payload,
            retcode=retcode,
            ticket=ticket,
            filled_price=float(getattr(result, "price", 0.0) or 0.0),
            filled_volume=float(getattr(result, "volume", 0.0) or 0.0),
            comment=comment,
            raw=result,
        )


