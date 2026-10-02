using ForexAI.Application.Contracts.MarketData;

namespace ForexAI.Application.Interfaces;

public interface IMarketDataClient
{
    Task<MarketDataResponse> GetMarketDataAsync(
        string symbol,
        string timeframe,
        int limit,
        CancellationToken cancellationToken = default);
}