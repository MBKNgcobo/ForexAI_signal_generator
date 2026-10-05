using System.Net;
using System.Text;
using System.Text.Json;
using ForexAI.Application.Contracts.Analysis;
using ForexAI.Domain.Enums;
using ForexAI.Infrastructure.ExternalServices;
using Xunit;

namespace ForexAI.Tests.Application;

/// <summary>
/// How the gateway actually calls the hosted Python service. The API key
/// matters most: the Python deployment is public and rejects any request
/// without it, so a missing header here means every hosted analysis fails
/// with 401.
/// </summary>
public class PythonAiAnalysisClientTests
{
    private static readonly Guid PairId =
        Guid.Parse("11111111-1111-1111-1111-111111111111");

    private sealed class _RecordingHandler : HttpMessageHandler
    {
        private readonly HttpStatusCode _status;
        private readonly string _body;

        public _RecordingHandler(
            HttpStatusCode status,
            string body)
        {
            _status = status;
            _body = body;
        }

        public HttpRequestMessage? Request { get; private set; }

        public string RequestBody { get; private set; } = string.Empty;

        protected override async Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            Request = request;

            RequestBody = request.Content is null
                ? string.Empty
                : await request.Content.ReadAsStringAsync(
                    cancellationToken);

            return new HttpResponseMessage(_status)
            {
                Content = new StringContent(
                    _body,
                    Encoding.UTF8,
                    "application/json")
            };
        }
    }

    private const string ValidResponse =
        """
        {
          "symbol": "EURUSD",
          "timeframe": "FifteenMinutes",
          "technical_analysis": {
            "direction": "BUY",
            "confidence": 0.72,
            "summary": "trend up"
          },
          "fundamental_analysis": {
            "direction": "BUY",
            "confidence": 0.61,
            "summary": "supportive"
          },
          "quant_prediction": {
            "direction": "BUY",
            "confidence": 0.68,
            "summary": "ensemble agrees"
          },
          "risk_assessment": {
            "risk_level": "LOW",
            "approved": true,
            "agreement": 1.0,
            "reason": "unanimous"
          },
          "final_decision": {
            "direction": "BUY",
            "confidence": 0.71,
            "reasoning": "all agents agree"
          }
        }
        """;

    private static (
        PythonAiAnalysisClient Client,
        _RecordingHandler Handler) Build(
            HttpStatusCode status,
            string body,
            string? apiKey)
    {
        var handler = new _RecordingHandler(status, body);

        var httpClient = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://python-ai.example")
        };

        if (apiKey is not null)
        {
            httpClient.DefaultRequestHeaders.Add(
                "X-API-Key",
                apiKey);
        }

        return (new PythonAiAnalysisClient(httpClient), handler);
    }

    private static AnalyzeMarketRequest Request(
        string? webhookUrl = null) =>
        new(
            PairId,
            "EURUSD",
            Timeframe.FifteenMinutes,
            webhookUrl);

    [Fact]
    public async Task AnalyzeAsync_PostsToTheAnalysisRoute()
    {
        // Arrange
        var (client, handler) = Build(
            HttpStatusCode.OK,
            ValidResponse,
            null);

        // Act
        await client.AnalyzeAsync(Request());

        // Assert
        Assert.NotNull(handler.Request);
        Assert.Equal(
            HttpMethod.Post,
            handler.Request.Method);
        Assert.Equal(
            "/analysis",
            handler.Request.RequestUri?.AbsolutePath);
    }

    [Fact]
    public async Task AnalyzeAsync_ForwardsTheWebhookUrl()
    {
        // Arrange: this is the field that carries a hosted signal to the
        // local MT5 bridge.
        var (client, handler) = Build(
            HttpStatusCode.OK,
            ValidResponse,
            null);

        // Act
        await client.AnalyzeAsync(
            Request("https://tunnel.trycloudflare.com/signal?token=abc"));

        // Assert
        using var json = JsonDocument.Parse(handler.RequestBody);

        Assert.Equal(
            "https://tunnel.trycloudflare.com/signal?token=abc",
            json.RootElement.GetProperty("webhook_url").GetString());
    }

    [Fact]
    public async Task AnalyzeAsync_SendsTheApiKeyHeaderWhenConfigured()
    {
        // Arrange
        var (client, handler) = Build(
            HttpStatusCode.OK,
            ValidResponse,
            "secret-key");

        // Act
        await client.AnalyzeAsync(Request());

        // Assert
        Assert.NotNull(handler.Request);
        Assert.True(
            handler.Request.Headers.TryGetValues(
                "X-API-Key",
                out var values));
        Assert.Equal("secret-key", Assert.Single(values));
    }

    [Fact]
    public async Task AnalyzeAsync_OmitsTheApiKeyHeaderWhenNotConfigured()
    {
        // Arrange: local development keeps working without a guard.
        var (client, handler) = Build(
            HttpStatusCode.OK,
            ValidResponse,
            null);

        // Act
        await client.AnalyzeAsync(Request());

        // Assert
        Assert.NotNull(handler.Request);
        Assert.False(
            handler.Request.Headers.Contains("X-API-Key"));
    }

    [Fact]
    public async Task AnalyzeAsync_ReturnsTheMappedResponse()
    {
        // Arrange
        var (client, _) = Build(
            HttpStatusCode.OK,
            ValidResponse,
            null);

        // Act
        var result = await client.AnalyzeAsync(Request());

        // Assert
        Assert.Equal("EURUSD", result.Symbol);
        Assert.Equal(
            "FifteenMinutes",
            result.Timeframe);
        Assert.Equal(
            "BUY",
            result.FinalDecision.Direction);
        Assert.True(result.RiskAssessment.Approved);
    }

    [Fact]
    public async Task AnalyzeAsync_ThrowsOnANonSuccessStatus()
    {
        // Arrange: a 401 from the Python guard must not be mistaken for a
        // signal; the controller turns it into a 503 for the dashboard.
        var (client, _) = Build(
            HttpStatusCode.Unauthorized,
            """{"detail":"A valid X-API-Key header is required."}""",
            null);

        // Act & Assert
        await Assert.ThrowsAsync<HttpRequestException>(
            () => client.AnalyzeAsync(Request()));
    }

    [Fact]
    public async Task AnalyzeAsync_ThrowsWithTheUpstreamStatusCode()
    {
        // Arrange: the gateway must carry the upstream status so the
        // controller can map a Python 4xx (e.g. an unsupported symbol) to a
        // 400 for the dashboard instead of a blanket 503.
        var (client, _) = Build(
            HttpStatusCode.Unauthorized,
            """{"detail":"A valid X-API-Key header is required."}""",
            null);

        // Act & Assert
        var ex = await Assert.ThrowsAsync<HttpRequestException>(
            () => client.AnalyzeAsync(Request()));

        Assert.Equal(HttpStatusCode.Unauthorized, ex.StatusCode);
    }
}
