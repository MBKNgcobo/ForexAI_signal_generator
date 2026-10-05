using System.Net.Http.Json;
using ForexAI.Application.Contracts.Analysis;
using ForexAI.Application.Interfaces;

namespace ForexAI.Infrastructure.ExternalServices;

public sealed class PythonAiAnalysisClient
    : IAiAnalysisClient
{
    private readonly HttpClient _httpClient;

    public PythonAiAnalysisClient(
        HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<AiAnalysisResponse> AnalyzeAsync(
        AnalyzeMarketRequest request,
        CancellationToken cancellationToken = default)
    {
        // Retry a transient 5xx (a free-tier cold-start edge 503 or a provider
        // rate-limit/outage) and a connection/timeout. Each attempt issues a
        // *fresh* HttpRequestMessage via PostAsJsonAsync, so the request is
        // never sent twice on the same message. A 4xx is reported immediately.
        for (var attempt = 1; ; attempt++)
        {
            try
            {
                var response =
                    await _httpClient.PostAsJsonAsync(
                        "/analysis",
                        request,
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

                    // Attach the upstream status so the controller can tell a
                    // client error (4xx) from a service failure (5xx) instead
                    // of returning a blanket 503.
                    throw new HttpRequestException(
                        $"Python AI service returned " +
                        $"{(int)response.StatusCode} " +
                        $"{response.StatusCode}: " +
                        responseBody,
                        inner: null,
                        statusCode: response.StatusCode);
                }

                var result =
                    System.Text.Json.JsonSerializer.Deserialize<
                        AiAnalysisResponse>(
                            responseBody,
                            new System.Text.Json.JsonSerializerOptions
                            {
                                PropertyNameCaseInsensitive = true
                            });

                if (result is null)
                {
                    throw new InvalidOperationException(
                        "Python AI service returned an empty response.");
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
