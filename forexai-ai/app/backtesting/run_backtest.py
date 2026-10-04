import pandas as pd

from app.backtesting.engine import BacktestEngine
from app.backtesting.metrics import calculate_metrics


INPUT_FILE = (
    "data/historical/"
    "EURUSD_15m_predictions.csv"
)


def main():

    df = pd.read_csv(INPUT_FILE)

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        utc=True,
    )

    engine = BacktestEngine(
        stop_loss_atr=1.0,
        take_profit_atr=1.5,
        max_holding_period=12,
        # Typical EURUSD round-trip frictions, in price units. Zero keeps
        # the frictionless baseline; set realistic values for reporting.
        spread=0.00015,
        commission=0.0,
        slippage=0.00005,
    )

    threshold = 0.60

    trades = engine.run(
        df,
        probability_threshold=threshold,
    )

    metrics = calculate_metrics(trades)

    print()
    print("=" * 60)
    print("FOREXAI FIRST BACKTEST")
    print("=" * 60)

    print(f"Threshold: {threshold}")

    for name, value in metrics.items():

        if isinstance(value, float):

            print(
                f"{name:20}: "
                f"{value:.4f}"
            )

        else:

            print(
                f"{name:20}: "
                f"{value}"
            )

    print()
    print("=" * 60)
    print("TRADES")
    print("=" * 60)

    for trade in trades:

        print(
            f"{trade.timestamp} | "
            f"{trade.direction:4} | "
            f"entry={trade.entry_price:.5f} | "
            f"exit={trade.exit_price:.5f} | "
            f"result={trade.result:10} | "
            f"profit={trade.profit:.6f}"
        )


if __name__ == "__main__":
    main()