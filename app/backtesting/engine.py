import pandas as pd

from app.backtesting.trade import Trade


class BacktestEngine:

    def __init__(
        self,
        stop_loss_atr: float = 1.0,
        take_profit_atr: float = 1.5,
        max_holding_period: int = 12,
    ):
        self.stop_loss_atr = stop_loss_atr
        self.take_profit_atr = take_profit_atr
        self.max_holding_period = max_holding_period

    def run(
        self,
        df: pd.DataFrame,
        probability_threshold: float = 0.60,
    ) -> list[Trade]:

        trades: list[Trade] = []

        for i in range(len(df) - 1):

            row = df.iloc[i]

            buy_probability = row[
                "buy_probability"
            ]

            sell_probability = row[
                "sell_probability"
            ]

            # Only trade when one direction
            # passes the confidence threshold.

            if (
                buy_probability >= probability_threshold
                and buy_probability > sell_probability
            ):
                direction = "BUY"

            elif (
                sell_probability >= probability_threshold
                and sell_probability > buy_probability
            ):
                direction = "SELL"

            else:
                continue

            entry = row["close"]
            atr = row["atr_14"]

            if pd.isna(atr) or atr <= 0:
                continue

            if direction == "BUY":

                stop_loss = (
                    entry
                    - self.stop_loss_atr * atr
                )

                take_profit = (
                    entry
                    + self.take_profit_atr * atr
                )

            else:

                stop_loss = (
                    entry
                    + self.stop_loss_atr * atr
                )

                take_profit = (
                    entry
                    - self.take_profit_atr * atr
                )

            trade = self._simulate_trade(
                df,
                entry_index=i,
                direction=direction,
                entry=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            if trade is not None:
                trades.append(trade)

        return trades

    def _simulate_trade(
        self,
        df: pd.DataFrame,
        entry_index: int,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
    ) -> Trade | None:

        for j in range(
            entry_index + 1,
            len(df),
        ):

            candle = df.iloc[j]

            if direction == "BUY":

                hit_tp = (
                    candle["high"]
                    >= take_profit
                )

                hit_sl = (
                    candle["low"]
                    <= stop_loss
                )

                # We cannot determine which
                # barrier occurred first if both
                # occur in the same OHLC candle.

                if hit_tp and hit_sl:
                    result = "AMBIGUOUS"

                    return Trade(
                        timestamp=df.iloc[
                            entry_index
                        ]["datetime"],
                        direction=direction,
                        entry_price=entry,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        exit_price=entry,
                        exit_timestamp=candle[
                            "datetime"
                        ],
                        result=result,
                    )

                if hit_tp:

                    return Trade(
                        timestamp=df.iloc[
                            entry_index
                        ]["datetime"],
                        direction=direction,
                        entry_price=entry,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        exit_price=take_profit,
                        exit_timestamp=candle[
                            "datetime"
                        ],
                        result="WIN",
                        profit=take_profit - entry,
                    )

                if hit_sl:

                    return Trade(
                        timestamp=df.iloc[
                            entry_index
                        ]["datetime"],
                        direction=direction,
                        entry_price=entry,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        exit_price=stop_loss,
                        exit_timestamp=candle[
                            "datetime"
                        ],
                        result="LOSS",
                        profit=stop_loss - entry,
                    )

            else:

                hit_tp = (
                    candle["low"]
                    <= take_profit
                )

                hit_sl = (
                    candle["high"]
                    >= stop_loss
                )

                if hit_tp and hit_sl:
                    result = "AMBIGUOUS"

                    return Trade(
                        timestamp=df.iloc[
                            entry_index
                        ]["datetime"],
                        direction=direction,
                        entry_price=entry,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        exit_price=entry,
                        exit_timestamp=candle[
                            "datetime"
                        ],
                        result=result,
                    )

                if hit_tp:

                    return Trade(
                        timestamp=df.iloc[
                            entry_index
                        ]["datetime"],
                        direction=direction,
                        entry_price=entry,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        exit_price=take_profit,
                        exit_timestamp=candle[
                            "datetime"
                        ],
                        result="WIN",
                        profit=entry - take_profit,
                    )

                if hit_sl:

                    return Trade(
                        timestamp=df.iloc[
                            entry_index
                        ]["datetime"],
                        direction=direction,
                        entry_price=entry,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        exit_timestamp=candle[
                            "datetime"
                        ],
                        result="LOSS",
                        profit=entry - stop_loss,
                    )

        # If neither barrier is reached before
        # the available test data ends,
        # we currently ignore the trade.

        return None