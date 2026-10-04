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

logger = logging.getLogger(__name__)

EXECUTABLE_DIRECTIONS = {"BUY", "SELL"}


class SignalRejectedError(ValueError):
    """The incoming signal is not safe/eligible to execute."""


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
) -> OrderRequest:
    """Map an ``AiAnalysisResponse`` dict to an ``OrderRequest``.

    Pure: no terminal access, no I/O. Raises ``SignalRejectedError``
    for every gate failure with a human-readable reason.
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
        return OrderRequest(
            symbol=symbol,
            side=side,
            order_kind=OrderKind.MARKET,
            volume=volume,
            sl=float(sl),
            tp=float(tp),
            comment=comment,
        )
    except ValueError as exc:
        raise SignalRejectedError(f"signal failed validation: {exc}")


class SignalBridge:
    """Execute analysis payloads through an ``MT5TradeExecutor``.

    ``max_entry_drift_points`` (default 100 points = 10 pips on a
    5-digit broker) rejects signals whose market price has moved away
    from ``entry_price`` since analysis; set 0 to disable.
    """

    def __init__(
        self,
        executor: MT5TradeExecutor,
        volume: float = 0.01,
        min_confidence: float | None = None,
        max_entry_drift_points: float = 100.0,
    ):
        self.executor = executor
        self.volume = volume
        self.min_confidence = min_confidence
        self.max_entry_drift_points = max_entry_drift_points

    def prepare(self, payload: Any) -> OrderRequest:
        """Gate + map a payload (no terminal access)."""

        return prepare_order_request(
            payload,
            volume=self.volume,
            min_confidence=self.min_confidence,
        )

    def _current_price(self, symbol: str, side: OrderSide) -> tuple[
        float, float
    ]:
        """(price, point_size) from the live tick for ``symbol``."""

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
