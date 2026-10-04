import pandas as pd

from app.backtesting.engine import BacktestEngine
from app.backtesting.metrics import calculate_metrics


INPUT_FILE = (
    "data/historical/"
    "EURUSD_15m_full_"
    "xgboost_validation_predictions.csv"
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
        # Same frictions as run_backtest.py so threshold comparisons are
        # apples-to-apples with reported backtests.
        spread=0.00015,
        commission=0.0,
        slippage=0.00005,
    )

    thresholds = [
        0.50,
        0.55,
        0.60,
        0.65,
        0.70,
        0.75,
        0.80,
    ]

    results = []

    for threshold in thresholds:

        trades = engine.run(
            df,
            probability_threshold=threshold,
        )

        metrics = calculate_metrics(trades)

        results.append({
            "threshold": threshold,
            "trades": metrics[
                "total_trades"
            ],
            "win_rate": metrics[
                "win_rate"
            ],
            "profit_factor": metrics[
                "profit_factor"
            ],
            "total_profit": metrics[
                "total_profit"
            ],
        })

    results_df = pd.DataFrame(results)

    print()
    print("=" * 75)
    print("VALIDATION THRESHOLD ANALYSIS")
    print("=" * 75)

    print(
        results_df.to_string(
            index=False,
            formatters={
                "win_rate": "{:.3f}".format,
                "profit_factor": "{:.3f}".format,
                "total_profit": "{:.6f}".format,
            },
        )
    )

    # Calibration table: predicted-bucket -> empirical win rate. Paste the
    # output below into models/calibration.json under the "quant" source to
    # regenerate the shipped prior from real validation data instead of the
    # hand-seeded neutral map.
    print()
    print("-" * 75)
    print("QUANT CALIBRATION TABLE (predicted bucket -> empirical win rate)")
    print("-" * 75)

    calibration_rows = []

    for row in results:
        calibration_rows.append(
            {
                "predicted": row["threshold"],
                "empirical_win_rate": round(row["win_rate"], 4),
                "trades": row["trades"],
            }
        )

    calibration_df = pd.DataFrame(calibration_rows)

    print(
        calibration_df.to_string(
            index=False,
            formatters={
                "predicted": "{:.2f}".format,
                "empirical_win_rate": "{:.4f}".format,
            },
        )
    )

    output_file = (
        "data/historical/"
        "EURUSD_15m_threshold_analysis.csv"
    )

    results_df.to_csv(
        output_file,
        index=False,
    )

    print()
    print(
        f"Saved results to: {output_file}"
    )


if __name__ == "__main__":
    main()