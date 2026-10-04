"""Dry-run MT5 connection check (Phase 1)."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("check_mt5_connection")

# Running as a file puts scripts/ (not the repo root) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the MT5 terminal is reachable and demo credentials work. "
            "Dry-run only: prints the account snapshot, places no orders."
        )
    )
    parser.add_argument("--login", type=int, default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--server", default=None)
    parser.add_argument("--path", default=None)
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    login = args.login or os.getenv("MT5_LOGIN")
    password = args.password or os.getenv("MT5_PASSWORD")
    server = args.server or os.getenv("MT5_SERVER")
    path = args.path or os.getenv("MT5_PATH")

    if not login or not password or not server:
        logger.error(
            "Missing credentials: provide --login/--password/--server "
            "or set MT5_LOGIN/MT5_PASSWORD/MT5_SERVER."
        )
        return 2

    try:
        login_int = int(login)
    except ValueError:
        logger.error("MT5_LOGIN must be a numeric account number.")
        return 2

    from app.broker.mt5_connection import (
        MT5ConnectionError,
        connect,
        shutdown,
    )

    try:
        account = connect(
            login=login_int,
            password=password,
            server=server,
            path=path,
            timeout_seconds=args.timeout,
        )
    except MT5ConnectionError as exc:
        logger.error("MT5 connection failed: %s", exc)
        return 1

    # Dry-run output: balances only, password never printed.
    logger.info(
        "DRY-RUN OK login=%s server=%s balance=%.2f %s equity=%.2f "
        "trade_allowed=%s (no orders placed)",
        account.login,
        account.server,
        account.balance,
        account.currency,
        account.equity,
        account.trade_allowed,
    )

    shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
