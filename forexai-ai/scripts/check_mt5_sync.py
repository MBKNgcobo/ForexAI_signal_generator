"""Verify MT5 state synchronization (Phase 4) — read-only.

Takes N snapshots of account + positions + pending orders from the
connected terminal and prints the drift report between polls. Never
sends orders.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("check_mt5_sync")

# Running as a file puts scripts/ (not the repo root) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Poll MT5 account/positions/orders and print drift "
            "reports. Read-only; sends no orders."
        )
    )
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--interval", type=float, default=2.0)
    return parser.parse_args()


def _print_state(report, index: int) -> None:
    state = report.state
    acc = state.account

    print(f"\n=== poll {index} "
          f"{'(initial baseline)' if report.initial else ''} ===")
    print(
        f"Account login={acc.login} balance={acc.balance:.2f} "
        f"equity={acc.equity:.2f} margin={acc.margin:.2f} "
        f"free={acc.margin_free:.2f} {acc.currency} "
        f"trade_allowed={acc.trade_allowed}"
    )

    print(f"Positions ({len(state.positions)}):")
    if not state.positions:
        print("  (none)")
    for p in state.positions:
        print(
            f"  #{p.ticket} {p.symbol} {p.side} vol={p.volume} "
            f"open={p.price_open} cur={p.price_current} "
            f"sl={p.sl} tp={p.tp} profit={p.profit:.2f} "
            f"opened={p.opened_at.isoformat()}"
        )

    print(f"Pending orders ({len(state.orders)}):")
    if not state.orders:
        print("  (none)")
    for o in state.orders:
        print(
            f"  #{o.ticket} {o.symbol} {o.kind} "
            f"vol={o.volume_current}/{o.volume_initial} "
            f"price={o.price_open} sl={o.sl} tp={o.tp} "
            f"state={o.state}"
        )

    if not report.initial:
        print(f"Drift: has_drift={report.has_drift}")
        if report.has_drift:
            print(
                f"  opened_pos={list(report.opened_positions)} "
                f"closed_pos={list(report.closed_positions)} "
                f"modified_pos={list(report.modified_positions)}"
            )
            print(
                f"  opened_ord={list(report.opened_orders)} "
                f"cancelled_ord={list(report.cancelled_orders)} "
                f"modified_ord={list(report.modified_orders)}"
            )
            print(
                f"  balance_delta={report.balance_delta:.2f} "
                f"equity_delta={report.equity_delta:.2f}"
            )


def main() -> int:
    args = _parse_args()

    from app.broker.mt5_sync import MT5StateSynchronizer, MT5SyncError

    sync = MT5StateSynchronizer(poll_interval=args.interval)

    try:
        for i in range(1, args.count + 1):
            report = sync.poll_once()
            _print_state(report, i)
            if i < args.count:
                time.sleep(args.interval)
    except MT5SyncError as exc:
        logger.error("MT5 sync failed: %s", exc)
        return 1
    finally:
        sync.close()

    print("\nSYNC CHECK OK: read-only, no orders sent.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())