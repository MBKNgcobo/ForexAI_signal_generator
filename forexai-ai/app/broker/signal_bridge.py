"""Signal bridge: analysis payload -> MT5 order (the final connector).

Pipeline this module completes:

    POST /analysis (or /analysis/batch) with webhook_url
        -> AiAnalysisResponse JSON
        -> [this module] gates + maps
        -> OrderRequest (mandatory SL/TP, validated)
        -> MT5TradeExecutor.send()  (dry-run by default)

Design rules:
- ``SignalRejectedError(ValueError)`` for anything that means "this
  signal must not trade" (HOLD, risk not approved, missing exits,
  confidence too low, price drifted past the entry). 400-class.
- ``prepare_order_request`` is a pure function (payload -> intent) so
  the mapping is unit-testable without any terminal.
- ``execute`` adds an entry-drift guard: if the market moved more than
  ``max_entry_drift_points`` from the signal's ``entry_price``, the
  signal is rejected instead of filled at a worse price.
- Terminal failures stay ``RuntimeError`` (503-class); the receiver
  maps them. Everything dry-runs unless ``MT5_DRY_RUN=false``/``--live``.
"""

from __future__ import annotations

import hmac
import logging
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.broker.mt5_executor import (
    MT5TradeExecutor,
    OrderKind,
    OrderRequest,
    OrderSide,
)
from app.broker.mt5_market_data_provider import MT5DataError
from app.broker.trade_log import (
    TradeLogEntry,
    trade_log_append,
    _default_path,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    """Short date string for trade-log records."""
    from datetime import date

    return date.today().isoformat()


def _now() -> str:
    """Short time string for trade-log records."""
    from datetime import datetime

    return datetime.now().strftime("%H:%M:%S")


def _is_paper_executor(executor: Any) -> bool:
    """True when the bridge was wired with a paper broker."""
    # Local import keeps the bridge importable without the paper broker's
    # dependency tree and avoids any import-order cycles at module load.
    from app.broker.paper_broker import PaperBroker

    if isinstance(executor, PaperBroker):
        return True

    return isinstance(getattr(executor, "executor", None), PaperBroker)


def _getenv(name: str, default: str | None = None) -> str | None:
    """Dotenv-aware env read (loads ``.env``, strips whitespace/quoting)."""
    from dotenv import load_dotenv

    load_dotenv()
    return _strip_env(getenv(name, default))


def _strip_env(raw: str | None) -> str | None:
    """Strip whitespace and surrounding quotes from an env value."""
    if raw is None:
        return None
    raw = raw.strip()
    if len(raw) >= 2 and ((raw[0] == raw[-1] == "'") or (raw[0] == raw[-1] == '"')):
        raw = raw[1:-1]
    return raw


def getenv(name: str, default: str | None = None) -> str | None:
    """Read an env var, merging ``.env`` when present."""
    from app.config import get_env as _getenv

    return _getenv(name, default)


EXECUTABLE_DIRECTIONS = {"BUY", "SELL"}


class SignalRejectedError(ValueError):
    """The incoming signal is not safe/eligible to execute."""


def _coerce_history(strategy: Any | None) -> dict | None:
    """Normalise dict/StrategyObject/None to a dict (never raises)."""

    if strategy is None:
        return None

    try:
        if isinstance(strategy, dict):
            return strategy

        to_dict = getattr(strategy, "to_dict", None)

        if callable(to_dict):
            data = to_dict()
            return data if isinstance(data, dict) else None

        return None
    except Exception:
        return None


def signal_token_valid(request_path: str, expected: str | None) -> bool:
    """Check ``?token=`` on the request path against ``expected``.

    Token auth lives in the URL because the webhook layer can only
    POST JSON — no custom headers. No expected token configured means
    auth is off (localhost-only mode).
    """

    if not expected:
        return True

    query = parse_qs(urlparse(request_path).query)
    provided = query.get("token", [""])[0]

    # Bytes comparison: any unicode token from a hostile client can
    # never raise TypeError the way str-vs-str compare_digest can.
    return hmac.compare_digest(
        provided.encode("utf-8"),
        expected.encode("utf-8"),
    )


def prepare_order_request(
    payload: Any,
    volume: float,
    min_confidence: float | None = None,
    history_strategy: Any | None = None,
    mode: str | None = None,
) -> OrderRequest:
    """Map an ``AiAnalysisResponse`` dict to an ``OrderRequest``.

    Pure: no terminal access, no I/O. Raises ``SignalRejectedError``
    for every gate failure with a human-readable reason.

    ``history_strategy`` is the advisory History Node gate (dict or
    StrategyObject): blocked pairs are refused and ``volume`` is scaled
    by ``volume_multiplier``. ``None`` disables the gate (back-compat).

    ``mode`` (``"paper"`` / ``"mt5"``) is the audit-trail label: when it
    is given, the accepted signal is appended to the JSONL trade log as
    an ``order_sent`` event so the dashboard keeps a P&L-ready history.
    ``None`` keeps the function side-effect free (unit tests, callers
    that log elsewhere).
    """

    if not isinstance(payload, dict):
        raise SignalRejectedError("payload must be a JSON object.")

    symbol = payload.get("symbol")
    decision = payload.get("final_decision")
    risk = payload.get("risk_assessment")
    decision = decision if isinstance(decision, dict) else {}
    risk = risk if isinstance(risk, dict) else {}

    if not symbol or not isinstance(symbol, str):
        raise SignalRejectedError("payload is missing 'symbol'.")

    history = _coerce_history(history_strategy)

    if history is not None:
        allowed = history.get("allowed_pairs") or []
        blocked = history.get("blocked_pairs") or {}

        if allowed and "*" not in allowed and symbol not in allowed:
            detail = blocked.get(symbol, "not in allowed_pairs")
            raise SignalRejectedError(
                f"HistoryNode blocks {symbol}: {detail}."
            )

        if symbol in blocked and "*" in allowed:
            raise SignalRejectedError(
                f"HistoryNode blocks {symbol}: {blocked.get(symbol)}."
            )

        try:
            multiplier = float(history.get("volume_multiplier", 1.0))
        except (TypeError, ValueError):
            multiplier = 1.0

        multiplier = min(1.0, max(0.25, multiplier))
        volume = volume * multiplier

    direction = str(decision.get("direction") or "").upper()

    if not direction or direction in {"HOLD", "NO_TRADE"}:
        raise SignalRejectedError(
            f"direction {direction or '<missing>'!r} is not executable."
        )

    if direction not in EXECUTABLE_DIRECTIONS:
        raise SignalRejectedError(
            f"unknown direction {direction!r} "
            f"(expected BUY or SELL)."
        )

    if risk.get("approved") is not True:
        raise SignalRejectedError(
            "risk_assessment.approved is not true; signal refused."
        )

    entry = risk.get("entry_price")
    sl = risk.get("stop_loss")
    tp = risk.get("take_profit")

    if sl is None or tp is None:
        raise SignalRejectedError(
            "stop_loss/take_profit missing — refusing to trade "
            "without an exit plan."
        )

    if entry is None:
        raise SignalRejectedError("entry_price missing from signal.")

    if min_confidence is not None:
        confidence = decision.get("confidence")

        if confidence is None or float(confidence) < min_confidence:
            raise SignalRejectedError(
                f"confidence {confidence} below required "
                f"{min_confidence}."
            )

    side = OrderSide.BUY if direction == "BUY" else OrderSide.SELL
    timeframe = str(payload.get("timeframe") or "?")
    # MT5 caps order comments at 31 chars.
    comment = f"sig {direction} {timeframe}"[:31]

    try:
        order = OrderRequest(
            symbol=symbol,
            side=side,
            order_kind=OrderKind.MARKET,
            volume=volume,
            sl=float(sl),
            tp=float(tp),
            comment=comment,
        )
    except ValueError as exc:
        raise SignalRejectedError(f"signal failed validation: {exc}") from exc

    # Record the accepted signal to the JSONL trade log so the dashboard
    # has a persistent, P&L-ready audit trail even before the order fills.
    if mode is not None:
        trade_log_append(
            _default_path(),
            TradeLogEntry(
                date=_today(),
                time=_now(),
                mode=mode,
                symbol=symbol,
                direction=direction,
                ticket=0,
                price=float(entry),
                sl=float(order.sl),
                tp=float(order.tp),
                volume=float(order.volume),
                spread_pips=0.0,
                reason=f"order_sent ({direction})",
                event_type="order_sent",
                pnl=None,
                pnl_basis=None,
                pnl_exit=None,
                profit=None,
            ),
        )

    return order


class SignalBridge:
    """Maps analysis payloads to orders and routes them to an executor.

    The executor is any object with ``send(req, dry_run=...)`` returning an
    object with ``dry_run`` / ``payload`` / ``ticket`` — ``MT5TradeExecutor``
    for demo orders, ``PaperBroker`` for simulated fills.  The price source
    defaults to the MT5 terminal tick (for the entry-drift guard) but can be
    injected (paper mode passes its own source) so the bridge never imports
    MetaTrader when it is not needed.

    ``max_entry_drift_points`` (default 100 points = 10 pips on a
    5-digit broker) rejects signals whose market price has moved away
    from ``entry_price`` since analysis; set 0 to disable.
    """

    def __init__(
        self,
        executor: MT5TradeExecutor | Any,
        volume: float = 0.01,
        min_confidence: float | None = 0.0,
        max_entry_drift_points: float = 100.0,
        price_source: Any | None = None,
        history_strategy: Any | None = None,
        history_node: Any | None = None,
    ) -> None:
        self.executor = executor
        self.volume = volume
        self.min_confidence = min_confidence
        self.max_entry_drift_points = max_entry_drift_points
        self.price_source = price_source
        self.history_strategy = history_strategy
        self.history_node = history_node

    def _resolve_history(self, payload: Any) -> Any | None:
        if isinstance(payload, dict):
            embedded = payload.get("history_context")

            if embedded is not None:
                return embedded

        if self.history_strategy is not None:
            return self.history_strategy

        if self.history_node is not None:
            try:
                getter = getattr(self.history_node, "get_strategy_safe", None)

                if callable(getter):
                    return getter()

                return self.history_node
            except Exception:
                return None

        return None

    def prepare(self, payload: Any) -> OrderRequest:
        """Gate + map a payload (no terminal access)."""

        return prepare_order_request(
            payload,
            volume=self.volume,
            min_confidence=self.min_confidence,
            history_strategy=self._resolve_history(payload),
            mode="paper" if _is_paper_executor(self.executor) else "mt5",
        )

    def _current_price(self, symbol: str, side: OrderSide) -> tuple[
        float, float
    ]:
        """(price, point_size) from the live tick for ``symbol``."""

        if self.price_source is not None:
            return self.price_source(symbol, side)

        mt5 = self.executor._ensure_connected()
        broker_symbol = self.executor._resolve_symbol(mt5, symbol)
        info = mt5.symbol_info(broker_symbol)
        tick = mt5.symbol_info_tick(broker_symbol)

        if info is None or tick is None:
            raise MT5DataError(
                f"no symbol data for {broker_symbol} during drift "
                f"check. last_error={mt5.last_error()}"
            )

        price = float(tick.ask) if side is OrderSide.BUY \
            else float(tick.bid)
        point = float(getattr(info, "point", 0.0) or 0.0)

        return price, point

    def check_entry_drift(self, req: OrderRequest, entry: float) -> None:
        """Reject when market price left the signal's entry zone."""

        if self.max_entry_drift_points <= 0:
            return

        price, point = self._current_price(req.symbol, req.side)

        if point <= 0:
            logger.warning("Symbol point size unknown; drift skip.")
            return

        drift_points = abs(price - float(entry)) / point

        if drift_points > self.max_entry_drift_points:
            raise SignalRejectedError(
                f"entry drift {drift_points:.0f} points exceeds "
                f"max {self.max_entry_drift_points:.0f} "
                f"(entry={entry}, market={price})."
            )

        logger.debug(
            "Drift check OK: %.0f/%.0f points.",
            drift_points,
            self.max_entry_drift_points,
        )

    def execute(self, payload: Any, dry_run: bool | None = None) -> Any:
        """Full pipeline: gate -> drift guard -> executor.send()."""

        req = self.prepare(payload)

        risk = payload.get("risk_assessment") or {}
        entry = risk.get("entry_price")

        if entry is not None:
            self.check_entry_drift(req, float(entry))

        result = self.executor.send(req, dry_run=dry_run)

        # Record the fill to the trade log (paper simulated fills / MT5 live
        # fills).  On dry-run the order was never sent, so nothing is logged;
        # the ``closed`` event carries P&L for real fills.  Paper mode writes
        # its own ``filled`` event inside PaperBroker.send(), so only MT5
        # fills are recorded here (paper's send() is always dry_run=True and
        # therefore never reaches this branch).
        if not result.dry_run:
            trade_log_append(
                _default_path(),
                TradeLogEntry(
                    date=_today(),
                    time=_now(),
                    mode="paper" if _is_paper_executor(self.executor) else "mt5",
                    symbol=req.symbol,
                    direction=req.side.value.upper(),
                    ticket=result.ticket or 0,
                    price=result.filled_price or 0.0,
                    sl=float(req.sl) if req.sl is not None else 0.0,
                    tp=float(req.tp) if req.tp is not None else 0.0,
                    volume=float(req.volume) if req.volume is not None else 0.0,
                    spread_pips=0.0,
                    reason=result.comment or f"filled ({req.symbol})",
                    event_type="filled",
                    pnl=None,
                    pnl_basis=None,
                    pnl_exit=None,
                    profit=None,
                ),
            )

        logger.info(
            "Signal %s %s -> %s (dry_run=%s ticket=%s)",
            payload.get("symbol"),
            payload["final_decision"]["direction"]
            if isinstance(payload.get("final_decision"), dict)
            else "?",
            result.payload.get("type"),
            result.dry_run,
            result.ticket,
        )

        return result


def handle_signal_payload(
    bridge: SignalBridge,
    data: Any,
    dry_run: bool | None = None,
) -> tuple[int, dict]:
    """HTTP-shaped mapping of ``bridge.execute`` outcomes.

    Returns ``(status_code, json_body)``:
    200 executed (or dry-run logged), 400 signal rejected/invalid,
    503 terminal/market-data failure (Retry-After friendly).
    """

    if not isinstance(data, dict):
        return 400, {
            "accepted": False,
            "error": "payload must be a JSON object.",
        }

    try:
        result = bridge.execute(data, dry_run=dry_run)
    except SignalRejectedError as exc:
        logger.info("Signal rejected: %s", exc)
        return 400, {"accepted": False, "error": str(exc)}
    except ValueError as exc:
        return 400, {"accepted": False, "error": str(exc)}
    except RuntimeError as exc:
        logger.error("Signal execution failed: %s", exc)
        return 503, {"accepted": False, "error": str(exc)}

    return 200, {
        "accepted": True,
        "dry_run": result.dry_run,
        "ticket": result.ticket,
        "retcode": result.retcode,
        "order_payload": result.payload,
    }
