"""Local signal receiver: webhook POST -> MT5 order (the bridge server).

Run this on the Windows machine that hosts the MT5 terminal:

    python scripts/run_signal_bridge.py            # dry-run (default)
    python scripts/run_signal_bridge.py --live     # honors MT5_DRY_RUN too

Then point an analysis request at it:

    POST /analysis  { ..., "webhook_url": "http://127.0.0.1:8799/signal" }

Endpoints:
    GET  /health  -> {"ok": true}
    POST /signal?token=...  -> {accepted, dry_run, ticket, retcode,
                                order_payload}
                    200 executed | 400 rejected | 401 bad token |
                    503 terminal failure

Auth: pass --token (or set BRIDGE_TOKEN in .env). Required whenever
the receiver is reachable beyond localhost (e.g. via a cloudflared
tunnel). Binds to 127.0.0.1 by default — never expose the port
directly.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("signal_bridge")

# Running as a file puts scripts/ (not the repo root) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Receive analysis webhooks and route to MT5."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--volume", type=float, default=None)
    parser.add_argument("--min-confidence", type=float, default=None)
    parser.add_argument("--max-drift-points", type=float, default=100.0)
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Arm real MT5 orders (only with --mode mt5). Startup is REFUSED "
            "unless MT5_DRY_RUN=false is also set in the environment "
            "(dual-key safety interlock)."
        ),
    )
    parser.add_argument(
        "--mode",
        default=None,
        choices=("dry_run", "paper", "mt5"),
        help=(
            "Execution mode: dry_run validates without filling (default), "
            "paper fills against live market data in a virtual account, "
            "mt5 routes to the MT5 terminal. Overrides TRADING_MODE."
        ),
    )
    parser.add_argument(
        "--token",
        default=None,
        help=(
            "Shared secret required as ?token= on /signal. "
            "Defaults to BRIDGE_TOKEN from the environment."
        ),
    )
    return parser.parse_args()


def _resolve_volume(args: argparse.Namespace) -> float:
    if args.volume is not None:
        return args.volume
    try:
        return float(os.getenv("MT5_SIGNAL_VOLUME", "0.01"))
    except ValueError:
        return 0.01


def live_mode_refused(live_flag: bool, dry_run_value: bool) -> bool:
    """Dual-key interlock: real orders need ``--live`` AND ``MT5_DRY_RUN=false``.

    Returns True when a requested ``--live`` start must be refused. A plain
    dry-run start (``live_flag`` False) is never refused, so the default
    operation of the bridge cannot be broken by the safety switch.
    ``dry_run_value`` is the resolved ``mt5_dry_run()`` config (anything
    unset/garbage resolves to True = dry-run).
    """

    return bool(live_flag) and bool(dry_run_value)


def _resolve_mode(args: argparse.Namespace) -> str:
    """Resolve dry_run/paper/mt5: CLI --mode wins, else TRADING_MODE."""
    if args.mode is not None:
        return args.mode
    try:
        from app.config import trading_mode

        return trading_mode()
    except Exception:  # noqa: BLE001
        return "dry_run"


def _build_bridge(args: argparse.Namespace, mode: str):
    from dotenv import load_dotenv

    from app.broker.signal_bridge import SignalBridge

    load_dotenv()

    if mode == "paper":
        from app.broker.paper_broker import (
            PaperBroker,
            make_service_price_source,
        )
        from app.services.market_data_cache import MarketDataCache
        from app.services.market_data_provider_factory import (
            provider_from_env,
        )
        from app.services.market_data_service import MarketDataService

        service = MarketDataService(
            provider=provider_from_env(), cache=MarketDataCache()
        )
        source = make_service_price_source(service)
        executor = PaperBroker(price_source=source)
        executor.start_monitor()
        bridge = SignalBridge(
            executor=executor,  # type: ignore[arg-type]
            volume=_resolve_volume(args),
            min_confidence=args.min_confidence,
            max_entry_drift_points=args.max_drift_points,
            price_source=source,
        )
        bridge_executor_kind = "paper"
        bridge_executor_kind = "paper"
    else:
        from app.broker.mt5_executor import MT5TradeExecutor

        executor = MT5TradeExecutor(
            dry_run=False if args.live else None,
        )
        bridge = SignalBridge(
            executor=executor,
        volume=_resolve_volume(args),
        min_confidence=args.min_confidence,
        max_entry_drift_points=args.max_drift_points,
    )


def _make_handler(bridge, dry_run, token: str | None):
    from app.broker.signal_bridge import (
        handle_signal_payload,
        signal_token_valid,
    )

    class Handler(BaseHTTPRequestHandler):
        def _respond(self, status: int, body: dict) -> None:
            raw = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):  # noqa: N802 (stdlib naming)
            if self.path == "/health":
                self._respond(200, {"ok": True})
            else:
                self._respond(404, {"ok": False, "error": "not found"})

        def do_POST(self):  # noqa: N802
            if not self.path.startswith("/signal"):
                self._respond(404, {"error": "not found"})
                return

            if not signal_token_valid(self.path, token):
                logger.warning(
                    "Rejected /signal call from %s: bad token.",
                    self.client_address[0],
                )
                self._respond(
                    401,
                    {
                        "accepted": False,
                        "error": "missing or invalid token.",
                    },
                )
                return

            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length)
                data = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._respond(400, {"error": "invalid JSON body"})
                return

            status, body = handle_signal_payload(
                bridge, data, dry_run=dry_run
            )
            self._respond(status, body)

        def log_message(self, fmt, *log_args):
            logger.info("%s - %s", self.address_string(), fmt % log_args)

    return Handler


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()  # before arg resolution so BRIDGE_TOKEN is visible

    args = _parse_args()
    token = args.token or os.getenv("BRIDGE_TOKEN")

    # Dual-key safety interlock: --live alone must never arm real orders.
    # The environment key (MT5_DRY_RUN=false) is the explicit configuration
    # change required on top of the command-line flag.
    from app.config import mt5_dry_run

    if live_mode_refused(args.live, mt5_dry_run()):
        logger.error(
            "Refusing to start: --live was passed but MT5_DRY_RUN is not "
            "explicitly 'false'. Set MT5_DRY_RUN=false in .env to arm real "
            "orders, or drop --live to stay in dry-run (default)."
        )
        return 2

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        logger.warning(
            "Binding to %s — ensure this port is NOT publicly "
            "reachable; the bridge executes trades.",
            args.host,
        )

    bridge = _build_bridge(args)
    dry_run = None if args.live else True

    server = ThreadingHTTPServer(
        (args.host, args.port),
        _make_handler(bridge, dry_run, token),
    )

    mode = "LIVE" if args.live else "DRY-RUN"
    auth = "token" if token else "NONE (localhost only!)"
    logger.info(
        "Signal bridge listening on http://%s:%d/signal "
        "(mode=%s, volume=%.2f, auth=%s)",
        args.host,
        args.port,
        mode,
        bridge.volume,
        auth,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Signal bridge stopping.")
    finally:
        server.server_close()
        bridge.executor.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())