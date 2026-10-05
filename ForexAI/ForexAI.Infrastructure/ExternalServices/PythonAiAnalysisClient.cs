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
            // Attach the upstream status so the controller can tell a client
            // error (4xx, e.g. an unsupported symbol) from a service failure
            // (5xx / unavailable) instead of blanket-mapping every failure to
            // 503 for the dashboard.
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
}