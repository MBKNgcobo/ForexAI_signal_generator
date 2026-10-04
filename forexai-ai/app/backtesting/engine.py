import pandas as pd

from app.backtesting.trade import Trade


class BacktestEngine:

    def __init__(
        self,
        stop_loss_atr: float = 1.0,
        take_profit_atr: float = 1.5,
        max_holding_period: int = 12,
        spread: float = 0.0,
        commission: float = 0.0,
        slippage: float = 0.0,
    ):
        if max_holding_period < 1:
            raise ValueError(
                "max_holding_period must be >= 1"
            )

        self.stop_loss_atr = stop_loss_atr
        self.take_profit_atr = take_profit_atr
        self.max_holding_period = max_holding_period

        # Costs are in price units and default to zero, so the engine keeps
        # its frictionless behaviour unless a caller opts in.
        self.spread = max(0.0, spread)
        self.commission = max(0.0, commission)
        self.slippage = max(0.0, slippage)

    def _round_trip_cost(self) -> float:
        """Cost charged against the gross profit of one completed trade.

        The spread is crossed once per round trip, slippage applies on both
        the entry and the exit, and the commission is charged once.
        """

        return (
            self.spread
            + (2 * self.slippage)
            + self.commission
        )

    def _make_trade(
        self,
        df: pd.DataFrame,
        entry_index: int,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        exit_index: int,
        exit_price: float,
        result: str,
        gross_profit: float,
    ) -> Trade:

        # An ambiguous candle has no determinable outcome, so no cost is
        # attributed to it (and its profit stays at zero).
        cost = (
            0.0
            if result == "AMBIGUOUS"
            else self._round_trip_cost()
        )

        return Trade(
            timestamp=df.iloc[entry_index]["datetime"],
            direction=direction,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            exit_price=exit_price,
            exit_timestamp=df.iloc[exit_index]["datetime"],
            result=result,
            profit=gross_profit - cost,
            cost=cost,
        )

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

        last_available_index = len(df) - 1

        # Respect the configured horizon (previously stored but ignored, so a
        # trade could linger for the rest of the file). The scan window is
        # clamped; a trade with no barrier hit inside the window TIME_EXITs
        # at the window's last candle.
        last_window_index = min(
            entry_index + self.max_holding_period,
            last_available_index,
        )

        for j in range(
            entry_index + 1,
            last_window_index + 1,
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

                    return self._make_trade(
                        df,
                        entry_index,
                        direction,
                        entry,
                        stop_loss,
                        take_profit,
                        j,
                        take_profit,
                        "WIN",
                        take_profit - entry,
                    )

                if hit_sl:

                    return self._make_trade(
                        df,
                        entry_index,
                        direction,
                        entry,
                        stop_loss,
                        take_profit,
                        j,
                        stop_loss,
                        "LOSS",
                        stop_loss - entry,
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

                    return self._make_trade(
                        df,
                        entry_index,
                        direction,
                        entry,
                        stop_loss,
                        take_profit,
                        j,
                        entry,
                        result,
                        0.0,
                    )

                if hit_tp:

                    return self._make_trade(
                        df,
                        entry_index,
                        direction,
                        entry,
                        stop_loss,
                        take_profit,
                        j,
                        take_profit,
                        "WIN",
                        entry - take_profit,
                    )

                if hit_sl:

                    return self._make_trade(
                        df,
                        entry_index,
                        direction,
                        entry,
                        stop_loss,
                        take_profit,
                        j,
                        stop_loss,
                        "LOSS",
                        entry - stop_loss,
                    )

        # If no barrier is reached inside the holding window, close the trade
        # at the window's last candle instead of silently ignoring it. The
        # exit can be profitable or unprofitable - metrics.py already handles
        # TIME_EXIT - and the round-trip cost still applies.

        exit_price = df.iloc[last_window_index]["close"]

        gross_profit = (
            exit_price - entry
            if direction == "BUY"
            else entry - exit_price
        )

        return self._make_trade(
            df,
            entry_index,
            direction,
            entry,
            stop_loss,
            take_profit,
            last_window_index,
            exit_price,
            "TIME_EXIT",
            gross_profit,
        )