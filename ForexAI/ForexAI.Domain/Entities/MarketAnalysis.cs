using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace ForexAI.Domain.Entities;

public class MarketAnalysis
{
    public Guid Id { get; private set; }

    public Guid ForexPairId { get; private set; }

    public DateTimeOffset CreatedAt { get; private set; }

    public string Trend { get; private set; }

    public decimal Volatility { get; private set; }

    public string MarketRegime { get; private set; }

    public string Summary { get; private set; }

    private MarketAnalysis()
    {   
        // Required by some persistence frameworks later.
        Trend = string.Empty;
        MarketRegime = string.Empty;
        Summary = string.Empty;
    }

    public MarketAnalysis(
        Guid forexPairId,
        string trend,
        decimal volatility,
        string marketRegime,
        string summary)
    {
        if (forexPairId == Guid.Empty)
            throw new ArgumentException(
                "Forex pair ID is required.",
                nameof(forexPairId));

        if (string.IsNullOrWhiteSpace(trend))
            throw new ArgumentException(
                "Trend is required.",
                nameof(trend));

        if (volatility < 0)
            throw new ArgumentException(
                "Volatility cannot be negative.",
                nameof(volatility));

        if (string.IsNullOrWhiteSpace(marketRegime))
            throw new ArgumentException(
                "Market regime is required.",
                nameof(marketRegime));

        if (string.IsNullOrWhiteSpace(summary))
            throw new ArgumentException(
                "Summary is required.",
                nameof(summary));

        Id = Guid.NewGuid();
        ForexPairId = forexPairId;
        CreatedAt = DateTimeOffset.UtcNow;
        Trend = trend;
        Volatility = volatility;
        MarketRegime = marketRegime;
        Summary = summary;
    }
}
