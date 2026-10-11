"""Accepted-signal tracking API: accept, list, detail, summary, SSE, health."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.api.security import require_api_key
from app.services.signal_tracking.models import (
    LONG,
    STATUS_ACTIVE,
    TERMINAL_STATUSES,
    TrackedSignal,
    normalize_direction,
)
from app.services.signal_tracking.monitor import SignalMonitor
from app.services.signal_tracking.quotes import publish, subscribe, unsubscribe
from app.services.signal_tracking.store import SignalStore

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/signals",
    tags=["Signals"],
    dependencies=[Depends(require_api_key)],
)

_store_lock = threading.Lock()
_store: SignalStore | None = None
_monitor_lock = threading.Lock()
_monitor: SignalMonitor | None = None


def get_store() -> SignalStore:
    global _store
    with _store_lock:
        if _store is None:
            from app.config import signal_db_path

            _store = SignalStore(signal_db_path())
            _store.initialise()
        return _store


def get_monitor() -> SignalMonitor:
    global _monitor
    with _monitor_lock:
        if _monitor is None:
            from app.config import signal_poll_seconds, signal_stale_seconds

            _monitor = SignalMonitor(
                get_store(),
                poll_seconds=signal_poll_seconds(),
                stale_seconds=signal_stale_seconds(),
            )
        else:
            _monitor.store = get_store()
        return _monitor


def reset_signal_tracking() -> None:
    """Drop singletons (tests only — never call in production)."""
    global _store, _monitor
    with _store_lock:
        _store = None

class AcceptSignalRequest(BaseModel):
    signal_id: str | None = None
    symbol: str
    direction: str = Field(description="BUY/SELL or LONG/SHORT")
    timeframe: str = ""
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float | None = None
    generated_at: str | None = None
    source_agent: str | None = None
    confidence: float | None = None
    initial_price: float | None = None
    current_price: float | None = None


def _present(signal: TrackedSignal) -> dict:
    data = signal.to_dict()
    active = signal.status in ("ACCEPTED", STATUS_ACTIVE)
    data["is_active"] = active
    data["is_completed"] = signal.status in TERMINAL_STATUSES
    if signal.entry_price and signal.current_price:
        if signal.direction == LONG:
            data["distance_to_sl"] = signal.current_price - signal.stop_loss
            data["distance_to_tp"] = signal.take_profit - signal.current_price
            data["unrealized_move"] = signal.current_price - signal.entry_price
        else:
            data["distance_to_sl"] = signal.stop_loss - signal.current_price
            data["distance_to_tp"] = signal.current_price - signal.take_profit
            data["unrealized_move"] = signal.entry_price - signal.current_price
    else:
        data["distance_to_sl"] = None
        data["distance_to_tp"] = None
        data["unrealized_move"] = None
    return data


@router.post("/accept")
async def accept_signal(body: AcceptSignalRequest) -> dict:
    """Validate + persist an accepted signal (idempotent on signal_id)."""
    try:
        signal, created = get_store().accept(
            signal_id=body.signal_id,
            symbol=body.symbol,
            direction=body.direction,
            timeframe=body.timeframe,
            entry_price=body.entry_price,
            stop_loss=body.stop_loss,
            take_profit=body.take_profit,
            risk_reward=body.risk_reward,
            generated_at=body.generated_at,
            source_agent=body.source_agent,
            confidence=body.confidence,
            initial_price=body.initial_price,
            current_price=body.current_price,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if created:
        await publish(
            {
                "type": "SIGNAL_ACCEPTED",
                "signal_id": signal.signal_id,
                "symbol": signal.symbol,
                "direction": signal.direction,
                "entry_price": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "at": signal.accepted_at,
            }
        )
    return {"accepted": True, "created": created, "signal": _present(signal)}


@router.post("/accept-analysis")
async def accept_analysis(payload: dict) -> dict:
    """Accept an AiAnalysisResponse-shaped payload (pipeline vocabulary)."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object.")
    risk = payload.get("risk_assessment") or {}
    decision = payload.get("final_decision") or {}
    if not isinstance(risk, dict) or not isinstance(decision, dict):
        raise HTTPException(status_code=400, detail="missing risk/decision blocks.")
    direction = decision.get("direction")
    if normalize_direction(direction) is None:
        raise HTTPException(
            status_code=422,
            detail=f"direction {direction!r} is not executable.",
        )
    if risk.get("approved") is not True:
        raise HTTPException(
            status_code=422, detail="risk_assessment.approved is not true."
        )
    body = AcceptSignalRequest(
        signal_id=payload.get("signal_id"),
        symbol=str(payload.get("symbol") or ""),
        direction=str(direction),
        timeframe=str(payload.get("timeframe") or ""),
        entry_price=float(risk.get("entry_price") or 0),
        stop_loss=float(risk.get("stop_loss") or 0),
        take_profit=float(risk.get("take_profit") or 0),
        risk_reward=(
            float(risk["risk_reward"]) if risk.get("risk_reward") is not None else None
        ),
        source_agent="analysis-pipeline",
        confidence=(
            float(decision["confidence"])
            if decision.get("confidence") is not None
            else None
        ),
    )
    return await accept_signal(body)


@router.get("")
async def list_tracked(
    status: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    completed_only: bool = Query(default=False),
    symbol: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict:
    """List tracked signals with filters (active vs completed, symbol, ...)."""
    if active_only and completed_only:
        raise HTTPException(
            status_code=400, detail="active_only and completed_only conflict."
        )
    statuses: list[str] | None = None
    if active_only:
        statuses = ["ACCEPTED", STATUS_ACTIVE]
    elif completed_only:
        statuses = sorted(TERMINAL_STATUSES)
    signals = get_store().list_signals(
        status=status,
        statuses=statuses,
        symbol=symbol,
        direction=direction,
        outcome=outcome,
        since=since,
        until=until,
        limit=limit,
    )
    return {"count": len(signals), "signals": [_present(s) for s in signals]}


@router.get("/summary")
async def tracking_summary() -> dict:
    return get_store().summary()


@router.get("/health")
async def monitoring_health() -> dict:
    monitor = get_monitor()
    provider_ok: bool | None = None
    provider_error: str | None = None
    provider_name: str | None = monitor.provider_name
    try:
        from app.config import market_data_provider_name
        from app.services.market_data_provider_factory import (
            get_shared_market_data_service,
        )

        provider_name = provider_name or market_data_provider_name()
        get_shared_market_data_service()
        provider_ok = True
    except RuntimeError as exc:
        provider_ok = False
        provider_error = str(exc)
    active = get_store().list_active()
    monitoring_available = bool(provider_ok)
    return {
        "monitoring_running": monitor.running,
        "monitoring_available": monitoring_available,
        "provider": provider_name,
        "provider_connected": (
            monitor.provider_connected if monitor.provider_connected is not None
            else provider_ok
        ),
        "provider_error": provider_error or monitor.last_error,
        "last_cycle_at": monitor.last_cycle_at,
        "last_error": monitor.last_error,
        "active_count": len(active),
        "poll_seconds": monitor.poll_seconds,
        "note": (
            None
            if monitoring_available
            else "Live monitoring unavailable: configure the market-data"
            " provider. Signals stay ACTIVE; no outcome is fabricated."
        ),
    }


@router.get("/stream")
async def stream_events():
    """Server-sent events: SIGNAL_ACCEPTED / TP / SL / errors, no polling."""

    async def _gen():
        queue = subscribe()
        try:
            yield ": connected\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            return
        finally:
            unsubscribe(queue)

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def signals_dashboard() -> HTMLResponse:
    from app.api.signals_page import PAGE

    return HTMLResponse(PAGE)


@router.get("/{signal_id}")
async def get_tracked(signal_id: str) -> dict:
    signal = get_store().get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="signal not found.")
    return {"signal": _present(signal), "events": get_store().events(signal_id)}


@router.post("/{signal_id}/cancel")
async def cancel_tracked(signal_id: str) -> dict:
    tracked, done = get_monitor().cancel_signal(signal_id)
    if tracked is None:
        raise HTTPException(status_code=404, detail="signal not found.")
    if done:
        await publish(
            {"type": "SIGNAL_CANCELLED", "signal_id": signal_id,
             "at": datetime.now(timezone.utc).isoformat()}
        )
    return {"cancelled": done, "signal": _present(tracked)}


@router.post("/{signal_id}/expire")
async def expire_tracked(signal_id: str) -> dict:
    tracked, done = get_monitor().expire_signal(signal_id)
    if tracked is None:
        raise HTTPException(status_code=404, detail="signal not found.")
    if done:
        await publish(
            {"type": "SIGNAL_EXPIRED", "signal_id": signal_id,
             "at": datetime.now(timezone.utc).isoformat()}
        )
    return {"expired": done, "signal": _present(tracked)}
