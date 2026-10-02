using ForexAI.Application.Contracts.MarketData;
using ForexAI.Application.Interfaces;

namespace ForexAI.Application.Services;

public sealed class MarketDataService
{
    private readonly IMarketDataClient _marketDataClient;

    public MarketDataService(
        IMarketDataClient marketDataClient)
    {
        _marketDataClient = marketDataClient;
    }

    public async Task<MarketDataResponse> ExecuteAsync(
        string symbol,
        string timeframe,
        int limit,
        CancellationToken cancellationToken = default)
    {
        var result = await _marketDataClient.GetMarketDataAsync(
            symbol,
            timeframe,
            limit,
            cancellationToken);
        if (string.IsNullOrWhiteSpace(symbol))
        {
            throw new ArgumentException(
                "Symbol is required.",
                nameof(symbol));
        }

        if (string.IsNullOrWhiteSpace(timeframe))
        {
            throw new ArgumentException(
                "Timeframe is required.",
                nameof(timeframe));
        }

        if (limit <= 0)
        {
            throw new ArgumentException(
                "Limit must be greater than zero.",
                nameof(limit));
        }

        if (limit > 500)
        {
            throw new ArgumentException(
                "Limit cannot exceed 500.",
                nameof(limit));
        }

        return result;
    }
    
}