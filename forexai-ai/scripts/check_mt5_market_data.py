"""Verify MT5 market-data ingestion against the live terminal (Phase 2).

Dry-run only: fetches 5 recent EURUSD candles plus the latest tick,
prints them for schema-shape inspection, then disconnects. No orders.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("check_mt5_market_data")

# Running as a file puts scripts/ (not the repo root) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch a 5-candle snapshot and latest tick from the local "
            "MT5 terminal to verify schema alignment. Places no orders."
        )
    )
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--timeframe", default="FiveMinutes")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--login", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--server", default=None)
    parser.add_argument("--path", default=None)
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    from app.broker.mt5_market_data_provider import (
        MT5MarketDataProvider,
    )

    login = args.login or os.getenv("MT5_LOGIN")
    password = args.password or os.getenv("MT5_PASSWORD")
    server = args.server or os.getenv("MT5_SERVER")
    path = args.path or os.getenv("MT5_PATH")

    if not login and not password and not server:
        # Attach mode: reuse the terminal's active (logged-in) session.
        logger.warning(
            "No MT5 credentials provided; attaching to the open "
            "terminal session."
        )
        login_int = None
    elif not login or not password or not server:
        logger.error(
            "Partial credentials: provide all of --login/--password/"
            "--server (or none to attach)."
        )
        return 2
    else:
        try:
            login_int = int(login)
        except ValueError:
            logger.error("MT5_LOGIN must be a numeric account number.")
            return 2

    provider = MT5MarketDataProvider(
        login=login_int,
        password=password or "",
        server=server or "",
        path=path,
    )

    try:
        data = await provider.get_market_data(
            symbol=args.symbol,
            timeframe=args.timeframe,
            limit=args.limit,
        )
        tick = provider.get_tick(args.symbol)
    except RuntimeError as exc:
        logger.error("MT5 market-data fetch failed: %s", exc)
        return 1

    # -- Dry-run output: schema shape inspection, no secrets. --
    print(
        f"\nMarketData(symbol={data.symbol!r}, "
        f"timeframe={data.timeframe!r}, "
        f"candles={len(data.candles)})"
    )
    print(f"{'timestamp (UTC)':<26} {'open':>10} {'high':>10} "
          f"{'low':>10} {'close':>10} {'volume':>10}")

    for c in data.candles:
        print(
            f"{str(c.timestamp):<26} {c.open:>10.5f} {c.high:>10.5f} "
            f"{c.low:>10.5f} {c.close:>10.5f} {c.volume or 0:>10.0f}"
        )

    print(
        f"\nTick @ {tick.time.isoformat()}  "
        f"bid={tick.bid:.5f}  ask={tick.ask:.5f}"
    )
    print("DRY-RUN OK: no orders placed.\n")

    provider.close()  # releases the IPC handle (calls mt5.shutdown)
    return 0


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
