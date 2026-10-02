import pandas as pd


def calculate_metrics(trades) -> dict:

    if not trades:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "time_exits": 0,
            "ambiguous_trades": 0,
            "win_rate": 0.0,
            "total_profit": 0.0,
            "profit_factor": 0.0,
        }

    winning_trades = [
        trade
        for trade in trades
        if trade.result == "WIN"
    ]

    losing_trades = [
        trade
        for trade in trades
        if trade.result == "LOSS"
    ]

    time_exits = [
        trade
        for trade in trades
        if trade.result == "TIME_EXIT"
    ]

    ambiguous_trades = [
        trade
        for trade in trades
        if trade.result == "AMBIGUOUS"
    ]

    gross_profit = sum(
        trade.profit
        for trade in winning_trades
    )

    gross_loss = abs(
        sum(
            trade.profit
            for trade in losing_trades
        )
    )

    # A trade closed by TIME_EXIT can be
    # profitable or unprofitable, so include
    # it when measuring realised P/L.

    realised_trades = [
        trade
        for trade in trades
        if trade.result != "AMBIGUOUS"
    ]

    profitable_trades = [
        trade
        for trade in realised_trades
        if trade.profit > 0
    ]

    win_rate = (
        len(profitable_trades)
        / len(realised_trades)
        if realised_trades
        else 0.0
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else 0.0
    )

    total_profit = sum(
        trade.profit
        for trade in realised_trades
    )

    return {
        "total_trades": len(trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "time_exits": len(time_exits),
        "ambiguous_trades": len(ambiguous_trades),
        "win_rate": win_rate,
        "total_profit": total_profit,
        "profit_factor": profit_factor,
    }