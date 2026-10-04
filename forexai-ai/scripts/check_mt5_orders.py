"""Verify MT5 order payloads (Phase 3) — DRY-RUN BY DEFAULT.

Builds market/limit/stop payloads for EURUSD against the live
terminal (real tick + symbol info) and prints them for inspection.
Nothing is sent unless ``--live`` is passed explicitly.

``--live`` sends ONE 0.01-lot market order on the connected demo
account and reports the ticket; every other flag combination stays
dry-run.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("check_mt5_orders")

# Running as a file puts scripts/ (not the repo root) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build and print MT5 order payloads for inspection. "
            "Dry-run by default; --live sends a single 0.01-lot "
            "market order on the connected demo account."
        )
    )
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--volume", type=float, default=0.01)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually send ONE market order (demo only!).",
    )
    return parser.parse_args()


def _sample_requests(symbol: str, volume: float, ask: float, bid: float):
    from app.broker.mt5_executor import (
        OrderKind,
        OrderRequest,
        OrderSide,
    )

    # SL/TP bracket the current price: ~10-pip risk / ~20-pip target.
    pip = 0.0001

    return [
        OrderRequest(
            symbol=symbol,
            side=OrderSide.BUY,
            order_kind=OrderKind.MARKET,
            volume=volume,
            sl=round(ask - 10 * pip, 5),
            tp=round(ask + 20 * pip, 5),
            comment="dryrun-market-buy",
        ),
        OrderRequest(
            symbol=symbol,
            side=OrderSide.SELL,
            order_kind=OrderKind.LIMIT,
            volume=volume,
            price=round(bid + 15 * pip, 5),
            sl=round(bid + 25 * pip, 5),
            tp=round(bid - 5 * pip, 5),
            comment="dryrun-limit-sell",
        ),
        OrderRequest(
            symbol=symbol,
            side=OrderSide.BUY,
            order_kind=OrderKind.STOP,
            volume=volume,
            price=round(ask + 15 * pip, 5),
            sl=round(ask + 5 * pip, 5),
            tp=round(ask + 35 * pip, 5),
            comment="dryrun-stop-buy",
        ),
    ]


def main() -> int:
    args = _parse_args()

    from app.broker.mt5_executor import MT5TradeExecutor

    executor = MT5TradeExecutor()  # attach mode; dry_run from config

    try:
        mt5 = executor._ensure_connected()
        broker_symbol = executor._resolve_symbol(mt5, args.symbol)
        tick = mt5.symbol_info_tick(broker_symbol)
    except RuntimeError as exc:
        logger.error("MT5 setup failed: %s", exc)
        return 1

    if tick is None:
        logger.error(
            "No tick for %s (last_error=%s).",
            broker_symbol,
            mt5.last_error(),
        )
        return 1

    ask = float(tick.ask)
    bid = float(tick.bid)
    requests = _sample_requests(args.symbol, args.volume, ask, bid)

    print(
        f"\n{args.symbol}: bid={bid:.5f} ask={ask:.5f} "
        f"live={args.live}\n"
    )

    exit_code = 0

    for req in requests:
        # --live only ever sends the market sample; pending orders
        # stay dry-run so a single flag cannot spray orders.
        send_live = args.live and req.order_kind.value == "market"

        try:
            result = executor.send(req, dry_run=not send_live)
        except ValueError as exc:
            logger.error("Request rejected by validation: %s", exc)
            return 2
        except RuntimeError as exc:
            logger.error("Order failed: %s", exc)
            exit_code = 1
            continue

        label = "LIVE" if not result.dry_run else "DRY-RUN"
        print(f"--- {label} {req.order_kind.value.upper()} "
              f"{req.side.value.upper()} {req.symbol} ---")
        print(json.dumps(result.payload, indent=2, default=str))
        print(
            f"ticket={result.ticket} retcode={result.retcode} "
            f"price={result.filled_price} comment={result.comment!r}\n"
        )

        if not result.dry_run:
            print(
                ">>> LIVE ORDER SENT — check the terminal's Trade tab; "
                "close it there if unwanted.\n"
            )

    executor.close()

    if args.live:
        print("Done (market order live; pending samples dry-run).")
    else:
        print("DRY-RUN OK: no orders sent.")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())