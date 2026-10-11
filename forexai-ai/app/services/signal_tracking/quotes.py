"""Background SL/TP monitor part 1: pub/sub + quote fetching."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_subscribers: set[asyncio.Queue] = set()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def publish(event: dict) -> None:
    for queue in list(_subscribers):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            continue


def subscribe() -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(queue)
    return queue


def unsubscribe(queue: asyncio.Queue) -> None:
    _subscribers.discard(queue)


async def fetch_quote(signal, *, provider_name: list | None = None) -> dict:
    """Fresh quote for ``signal`` from the configured provider.

    Prefers a native MT5 tick (bid/ask) when available, else the latest
    candle close. Never hard-coded, never simulated. Raises RuntimeError
    when unavailable so the caller logs MONITORING_ERROR and keeps the
    signal active.
    """
    try:
        from app.config import market_data_provider_name
        from app.services.market_data_provider_factory import (
            get_shared_market_data_service,
        )
    except Exception as exc:
        raise RuntimeError(f"market-data unavailable: {exc}") from exc
    name = market_data_provider_name()
    if provider_name is not None:
        provider_name.append(name)
    try:
        service = get_shared_market_data_service()
    except RuntimeError as exc:
        raise RuntimeError(str(exc)) from exc
    provider = getattr(service, "provider", None)
    get_tick = getattr(provider, "get_tick", None)
    if callable(get_tick):
        try:
            tick = get_tick(signal.symbol)
            bid = float(getattr(tick, "bid"))
            ask = float(getattr(tick, "ask"))
            ts = getattr(tick, "time", None)
            return {
                "bid": bid,
                "ask": ask,
                "price": (bid + ask) / 2.0,
                "at": ts.isoformat() if hasattr(ts, "isoformat") else None,
            }
        except Exception as exc:
            raise RuntimeError(f"MT5 tick failed: {exc}") from exc
    try:
        data = await service.get_market_data(
            symbol=signal.symbol,
            timeframe=signal.timeframe or "FifteenMinutes",
            limit=2,
        )
    except Exception as exc:
        raise RuntimeError(f"market-data fetch failed: {exc}") from exc
    candles = getattr(data, "candles", []) or []
    if not candles:
        raise RuntimeError("market-data returned no candles.")
    last = candles[-1]
    quote: dict[str, Any] = {"price": float(getattr(last, "close"))}
    try:
        quote["high"] = float(getattr(last, "high"))
        quote["low"] = float(getattr(last, "low"))
    except (TypeError, ValueError):
        pass
    ts = getattr(last, "timestamp", None)
    quote["at"] = (
        ts.isoformat() if hasattr(ts, "isoformat") else (str(ts) if ts else None)
    )
    # A candle timestamp is its BAR OPEN, so a healthy 15-minute feed can be
    # ~900 s old. Derive the staleness allowance from the project's existing
    # bar-age convention instead of a fixed window that rejects valid bars.
    try:
        from app.services.market_data_cache import max_candle_age_seconds

        quote["max_age_seconds"] = float(
            max_candle_age_seconds(signal.timeframe or "FifteenMinutes")
        )
    except Exception:  # pragma: no cover - defensive only
        pass
    return quote


def validate_quote(quote: dict | None, *, stale_seconds: float) -> dict | None:
    """None when missing/stale/unpriced (caller logs + keeps active).

    The allowance is ``stale_seconds`` unless the quote carries its own
    ``max_age_seconds`` (set for candle-based quotes from the bar length),
    in which case the more permissive of the two applies.
    """

    if not quote:
        return None
    allowance = stale_seconds
    try:
        hint = quote.get("max_age_seconds")
        if hint is not None:
            allowance = max(float(stale_seconds), float(hint))
    except (TypeError, ValueError):
        pass
    at_raw = quote.get("at")
    if at_raw:
        try:
            moment = datetime.fromisoformat(str(at_raw))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - moment).total_seconds()
            if age > allowance:
                quote["_stale_age"] = age
                return None
        except (TypeError, ValueError):
            pass
    if quote.get("price") is None:
        bid, ask = quote.get("bid"), quote.get("ask")
        if bid is not None and ask is not None:
            quote["price"] = (float(bid) + float(ask)) / 2.0
        else:
            return None
    return quote
