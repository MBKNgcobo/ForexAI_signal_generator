import numpy as np
import pandas as pd


# ------------------------------------------------------------------
# Label vocabulary for the trading target.
#
# 0 = SELL, 1 = NO_TRADE, 2 = BUY. Defined once so training and inference
# cannot disagree about which class index means which direction.
# ------------------------------------------------------------------

CLASS_NAMES = {
    0: "SELL",
    1: "NO_TRADE",
    2: "BUY",
}


DIRECTIONS = (
    "SELL",
    "NO_TRADE",
    "BUY",
)


def create_trading_target(
    df: pd.DataFrame,
    horizon: int = 12,
    take_profit_atr: float = 1.5,
    stop_loss_atr: float = 1.0,
) -> pd.DataFrame:

    data = df.copy()

    targets = []

    for i in range(len(data)):

        if i + horizon >= len(data):
            targets.append(np.nan)
            continue

        entry = data.loc[i, "close"]
        atr = data.loc[i, "atr_14"]

        if pd.isna(atr) or atr <= 0:
            targets.append(np.nan)
            continue

        take_profit_distance = (
            atr * take_profit_atr
        )

        stop_loss_distance = (
            atr * stop_loss_atr
        )

        buy_tp = entry + take_profit_distance
        buy_sl = entry - stop_loss_distance

        sell_tp = entry - take_profit_distance
        sell_sl = entry + stop_loss_distance

        future = data.iloc[
            i + 1:i + horizon + 1
        ]

        buy_result = None
        sell_result = None

        for _, candle in future.iterrows():

            # BUY barriers

            buy_tp_hit = candle["high"] >= buy_tp
            buy_sl_hit = candle["low"] <= buy_sl

            if buy_tp_hit and buy_sl_hit:
                buy_result = 0
                break

            if buy_tp_hit:
                buy_result = 1
                break

            if buy_sl_hit:
                buy_result = -1
                break

        for _, candle in future.iterrows():

            # SELL barriers

            sell_tp_hit = candle["low"] <= sell_tp
            sell_sl_hit = candle["high"] >= sell_sl

            if sell_tp_hit and sell_sl_hit:
                sell_result = 0
                break

            if sell_tp_hit:
                sell_result = 1
                break

            if sell_sl_hit:
                sell_result = -1
                break

        if buy_result == 1 and sell_result != 1:
            targets.append(1)

        elif sell_result == 1 and buy_result != 1:
            targets.append(-1)

        else:
            targets.append(0)

    data["target"] = targets

    return data