"""Background SL/TP monitor: single asyncio task, poll active signals."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from app.services.signal_tracking.models import (
    EVENT_MONITORING_ERROR,
    EVENT_SIGNAL_CANCELLED,
    EVENT_SIGNAL_EXPIRED,
    EVENT_STOP_LOSS_HIT,
    EVENT_TAKE_PROFIT_HIT,
    STATUS_CANCELLED,
    STATUS_EXPIRED,
    STATUS_OUTCOME_UNRESOLVED,
    STATUS_STOP_LOSS_HIT,
    STATUS_TAKE_PROFIT_HIT,
)
from app.services.signal_tracking.outcomes import (
    AMBIGUOUS,
    NONE,
    SL,
    TP,
    evaluate_outcome,
)
from app.services.signal_tracking.quotes import (
    _now_iso,
    fetch_quote,
    publish,
    validate_quote,
)

logger = logging.getLogger(__name__)


class SignalMonitor:
    """Poll active tracked signals against the market-data provider."""

    def __init__(
        self,
        store,
        *,
        poll_seconds: float = 15.0,
        stale_seconds: float = 300.0,
        price_fetcher: Callable | None = None,
    ) -> None:
        self.store = store
        self.poll_seconds = max(2.0, float(poll_seconds))
        self.stale_seconds = float(stale_seconds)
        self._price_fetcher = price_fetcher
        self._task: asyncio.Task | None = None
        self._running = False
        self.last_cycle_at: str | None = None
        self.last_error: str | None = None
        self.provider_name: str | None = None
        self.provider_connected: bool | None = None
        self._cycle_errors = 0

    @property
    def running(self) -> bool:
        return (
            self._running
            and self._task is not None
            and not self._task.done()
        )

    def start(self) -> asyncio.Task | None:
        if self._task is not None and not self._task.done():
            return self._task
        self._running = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return None
        self._task = loop.create_task(self._run_loop(), name="signal-monitor")
        return self._task

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _run_loop(self) -> None:
        logger.info("Signal monitor started (poll=%.1fs).", self.poll_seconds)
        try:
            while self._running:
                try:
                    await self.run_once()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.last_error = f"{type(exc).__name__}: {exc}"
                    logger.warning("Signal monitor cycle failed: %s", exc)
                await asyncio.sleep(self.poll_seconds)
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Signal monitor stopped.")

    async def run_once(self) -> dict:
        active = self.store.list_active()
        checked = 0
        completed = 0
        errors = 0
        self._cycle_errors = 0
        for signal in active:
            try:
                outcome = await self.check_signal(signal)
            except Exception as exc:
                errors += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                self.store.log_monitoring_error(
                    signal.signal_id, f"{type(exc).__name__}: {exc}"
                )
                await publish(
                    {
                        "type": EVENT_MONITORING_ERROR,
                        "signal_id": signal.signal_id,
                        "message": str(exc),
                        "at": _now_iso(),
                    }
                )
                continue
            checked += 1
            if outcome is not None:
                completed += 1
        self.last_cycle_at = _now_iso()
        # ``errors`` counts raised exceptions; ``_cycle_errors`` counts
        # recoverable per-signal failures (provider outage, stale/missing
        # price) so a degraded cycle is never reported as a clean pass.
        return {
            "checked": checked,
            "completed": completed,
            "errors": errors + self._cycle_errors,
        }

    async def check_signal(self, signal) -> str | None:
        quote = await self._quote_for(signal)
        if quote is None:
            return None
        price = float(quote["price"])
        self.store.update_price(signal.signal_id, price)
        result = evaluate_outcome(
            direction=signal.direction,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            bid=quote.get("bid"),
            ask=quote.get("ask"),
            price=quote.get("price"),
            candle_high=quote.get("high"),
            candle_low=quote.get("low"),
        )
        if result == NONE:
            return None
        at = _now_iso()
        if result == AMBIGUOUS:
            _t, done = self.store.complete(
                signal.signal_id,
                status=STATUS_OUTCOME_UNRESOLVED,
                close_price=price,
                event_type="OUTCOME_UNRESOLVED",
                detail={"reason": "SL+TP in one gap; order unknowable."},
                at=at,
            )
            if done:
                await publish(
                    {"type": "OUTCOME_UNRESOLVED",
                     "signal_id": signal.signal_id,
                     "symbol": signal.symbol,
                     "direction": signal.direction,
                     "close_price": price, "at": at}
                )
            return STATUS_OUTCOME_UNRESOLVED if done else None
        is_tp = result == TP
        _sl = result == SL
        status = STATUS_TAKE_PROFIT_HIT if is_tp else STATUS_STOP_LOSS_HIT
        event = EVENT_TAKE_PROFIT_HIT if is_tp else EVENT_STOP_LOSS_HIT
        _t, done = self.store.complete(
            signal.signal_id, status=status, close_price=price,
            event_type=event,
            detail={"bid": quote.get("bid"), "ask": quote.get("ask")},
            at=at,
        )
        if done:
            await publish(
                {"type": event, "signal_id": signal.signal_id,
                 "symbol": signal.symbol, "direction": signal.direction,
                 "close_price": price, "at": at}
            )
            return status
        return None

    async def _quote_for(self, signal) -> dict | None:
        if self._price_fetcher is not None:
            quote = self._price_fetcher(signal)
            if asyncio.iscoroutine(quote):
                quote = await quote
            return self._checked(signal, quote if isinstance(quote, dict) else None)
        names: list[str] = []
        try:
            quote = await fetch_quote(signal, provider_name=names)
            self.provider_name = names[0] if names else None
            self.provider_connected = True
        except RuntimeError as exc:
            self.provider_connected = False
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._cycle_errors = getattr(self, "_cycle_errors", 0) + 1
            self.store.log_monitoring_error(signal.signal_id, str(exc))
            return None
        return self._checked(signal, quote)

    def _checked(self, signal, quote: dict | None) -> dict | None:
        valid = validate_quote(quote, stale_seconds=self.stale_seconds)
        if valid is None and quote is not None and quote.get("_stale_age") is not None:
            age = quote.get("_stale_age")
            message = f"stale price ({float(age):.0f}s old); kept active."
            self._cycle_errors = getattr(self, "_cycle_errors", 0) + 1
            self.last_error = message
            self.store.log_monitoring_error(
                signal.signal_id,
                message,
                price=quote.get("price"),
            )
        elif valid is None:
            message = "no usable price; kept active."
            self._cycle_errors = getattr(self, "_cycle_errors", 0) + 1
            self.last_error = message
            self.store.log_monitoring_error(signal.signal_id, message)
        return valid

    def cancel_signal(self, signal_id: str):
        current = self.store.get(signal_id)
        price = 0.0
        if current is not None:
            price = float(current.current_price or current.entry_price or 0.0)
        return self.store.complete(
            signal_id, status=STATUS_CANCELLED, close_price=price,
            event_type=EVENT_SIGNAL_CANCELLED,
            detail={"reason": "cancelled via API"},
        )

    def expire_signal(self, signal_id: str):
        current = self.store.get(signal_id)
        price = 0.0
        if current is not None:
            price = float(current.current_price or current.entry_price or 0.0)
        return self.store.complete(
            signal_id, status=STATUS_EXPIRED, close_price=price,
            event_type=EVENT_SIGNAL_EXPIRED,
            detail={"reason": "expired via API"},
        )
