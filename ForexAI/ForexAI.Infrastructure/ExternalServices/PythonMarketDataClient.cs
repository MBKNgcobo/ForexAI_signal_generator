using ForexAI.Application.Contracts.MarketData;
using ForexAI.Application.Interfaces;

namespace ForexAI.Infrastructure.ExternalServices;

public sealed class PythonMarketDataClient : IMarketDataClient
{
    private readonly HttpClient _httpClient;

    public PythonMarketDataClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<MarketDataResponse> GetMarketDataAsync(
        string symbol,
        string timeframe,
        int limit,
        CancellationToken cancellationToken = default)
    {
        var url =
            $"/market-data/{Uri.EscapeDataString(symbol)}" +
            $"?timeframe={Uri.EscapeDataString(timeframe)}" +
            $"&limit={limit}";

        // Retry a transient 5xx (a free-tier cold-start edge 503 or a provider
        // outage) and a connection/timeout. Each attempt issues a *fresh*
        // HttpRequestMessage via GetAsync, so the single-use restriction never
        // applies. A 4xx is reported immediately (client error).
        for (var attempt = 1; ; attempt++)
        {
            try
            {
                var response = await _httpClient.GetAsync(
                    url,
                    cancellationToken);

                var responseBody =
                    await response.Content.ReadAsStringAsync(
                        cancellationToken);

                if (!response.IsSuccessStatusCode)
                {
                    if (attempt < GatewayRetry.MaxAttempts &&
                        (int)response.StatusCode >= 500)
                    {
                        await Task.Delay(
                            GatewayRetry.Backoff(attempt),
                            cancellationToken);
                        continue;
                    }

                    throw new HttpRequestException(
                        $"Python market-data service returned " +
                        $"{(int)response.StatusCode} " +
                        $"{response.StatusCode}: {responseBody}",
                        inner: null,
                        statusCode: response.StatusCode);
                }

                var result =
                    System.Text.Json.JsonSerializer
                        .Deserialize<MarketDataResponse>(
                            responseBody,
                            new System.Text.Json.JsonSerializerOptions
                            {
                                PropertyNameCaseInsensitive = true
                            });

                if (result is null)
                {
                    throw new InvalidOperationException(
                        "Python market-data service returned an empty response.");
                }

                return result;
            }
            catch (Exception ex) when (
                attempt < GatewayRetry.MaxAttempts &&
                !cancellationToken.IsCancellationRequested &&
                GatewayRetry.IsRetryable(ex))
            {
                await Task.Delay(
                    GatewayRetry.Backoff(attempt),
                    cancellationToken);
            }
        }
    }
}
