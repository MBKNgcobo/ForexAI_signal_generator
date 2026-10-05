using System.Net.Http.Json;
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

        var response = await _httpClient.GetAsync(
            url,
            cancellationToken);

        var responseBody =
            await response.Content.ReadAsStringAsync(
                cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            // Attach the upstream status so the controller can distinguish a
            // client error (400/422) from a service outage (5xx).
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
}