using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

using ForexAI.Domain.Enums;

namespace ForexAI.Domain.Entities;

public class MarketCandle
{
    public Guid Id { get; private set; }

    public Guid ForexPairId { get; private set; }

    public DateTimeOffset Timestamp { get; private set; }

    public decimal Open { get; private set; }

    public decimal High { get; private set; }

    public decimal Low { get; private set; }

    public decimal Close { get; private set; }

    public decimal Volume { get; private set; }

    public Timeframe Timeframe { get; private set; }

    private MarketCandle()
    {
    }

    public MarketCandle(
        Guid forexPairId,
        DateTimeOffset timestamp,
        decimal open,
        decimal high,
        decimal low,
        decimal close,
        decimal volume,
        Timeframe timeframe)
    {
        if (forexPairId == Guid.Empty)
            throw new ArgumentException(
                "Forex pair ID is required.",
                nameof(forexPairId));

        if (high < low)
            throw new ArgumentException(
                "High price cannot be lower than low price.");

        if (open < low || open > high)
            throw new ArgumentException(
                "Open price must be between low and high.");

        if (close < low || close > high)
            throw new ArgumentException(
                "Close price must be between low and high.");

        if (volume < 0)
            throw new ArgumentException(
                "Volume cannot be negative.");

        Id = Guid.NewGuid();
        ForexPairId = forexPairId;
        Timestamp = timestamp;
        Open = open;
        High = high;
        Low = low;
        Close = close;
        Volume = volume;
        Timeframe = timeframe;
    }
}
