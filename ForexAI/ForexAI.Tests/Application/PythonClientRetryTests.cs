using System.Net;
using System.Text;
using ForexAI.Application.Contracts.Analysis;
using ForexAI.Application.Contracts.MarketData;
using ForexAI.Domain.Enums;
using ForexAI.Infrastructure.ExternalServices;
using Xunit;

namespace ForexAI.Tests.Application;

/// <summary>
/// The gateway retry policy (implemented in the clients, one fresh
/// HttpRequestMessage per attempt). Without it a client's first request after
/// a free-tier idle period fails on a transient 5xx. A 4xx must never be
/// retried. The single-use HttpRequestMessage restriction means retry logic
/// cannot live in a DelegatingHandler that reuses the message.
/// </summary>
public class PythonClientRetryTests
{
    private sealed class _SequencedHandler : HttpMessageHandler
    {
        private readonly Queue<HttpStatusCode> _statuses;
        private readonly string _body;

        public int Calls { get; private set; }

        public _SequencedHandler(
            IEnumerable<HttpStatusCode> statuses,
            string body)
        {
            _statuses = new Queue<HttpStatusCode>(statuses);
            _body = body;
        }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            Calls++;

            var status = _statuses.Count > 0
                ? _statuses.Dequeue()
                : HttpStatusCode.OK;

            return Task.FromResult(new HttpResponseMessage(status)
            {
                Content = new StringContent(
                    _body,
                    Encoding.UTF8,
                    "application/json")
            });
        }
    }

    private static readonly Guid PairId =
        Guid.Parse("22222222-2222-2222-2222-222222222222");

    private const string ValidAnalysisJson =
        """
        {
          "symbol": "EURUSD",
          "timeframe": "FifteenMinutes",
          "technical_analysis": { "direction": "BUY", "confidence": 0.7, "summary": "s" },
          "fundamental_analysis": { "direction": "BUY", "confidence": 0.6, "summary": "s" },
          "quant_prediction": { "direction": "BUY", "confidence": 0.6, "summary": "s" },
          "risk_assessment": { "approved": true },
          "final_decision": { "direction": "BUY", "confidence": 0.7, "reasoning": "r" }
        }
        """;

    private const string ValidMarketDataJson =
        """
        {
          "symbol": "EURUSD",
          "timeframe": "FifteenMinutes",
          "candles": [
            { "timestamp": "2026-01-01T00:00:00Z", "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.1, "volume": 100 }
          ]
        }
        """;

    private static AnalyzeMarketRequest AnalysisRequest() =>
        new(PairId, "EURUSD", Timeframe.FifteenMinutes, null);

    [Fact]
    public async Task AnalyzeAsync_RetriesATransient5xxThenSucceeds()
    {
        var handler = new _SequencedHandler(
            new[] { HttpStatusCode.ServiceUnavailable, HttpStatusCode.OK },
            ValidAnalysisJson);
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://python-ai.example")
        };
        var service = new PythonAiAnalysisClient(client);

        var result = await service.AnalyzeAsync(AnalysisRequest());

        Assert.NotNull(result);
        Assert.Equal("EURUSD", result.Symbol);
        Assert.Equal(2, handler.Calls);
    }

    [Fact]
    public async Task AnalyzeAsync_DoesNotRetryA4xx()
    {
        var handler = new _SequencedHandler(
            new[] { HttpStatusCode.BadRequest },
            ValidAnalysisJson);
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://python-ai.example")
        };
        var service = new PythonAiAnalysisClient(client);

        var ex = await Assert.ThrowsAsync<HttpRequestException>(
            () => service.AnalyzeAsync(AnalysisRequest()));

        Assert.Equal(HttpStatusCode.BadRequest, ex.StatusCode);
        Assert.Equal(1, handler.Calls);
    }

    [Fact]
    public async Task AnalyzeAsync_GivesUpAfterMaxAttempts()
    {
        var handler = new _SequencedHandler(
            new[]
            {
                HttpStatusCode.ServiceUnavailable,
                HttpStatusCode.ServiceUnavailable,
                HttpStatusCode.ServiceUnavailable
            },
            ValidAnalysisJson);
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://python-ai.example")
        };
        var service = new PythonAiAnalysisClient(client);

        var ex = await Assert.ThrowsAsync<HttpRequestException>(
            () => service.AnalyzeAsync(AnalysisRequest()));

        Assert.Equal(HttpStatusCode.ServiceUnavailable, ex.StatusCode);
        Assert.Equal(3, handler.Calls);
    }

    [Fact]
    public async Task MarketData_RetriesATransient5xxThenSucceeds()
    {
        var handler = new _SequencedHandler(
            new[] { HttpStatusCode.ServiceUnavailable, HttpStatusCode.OK },
            ValidMarketDataJson);
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://python-ai.example")
        };
        var service = new PythonMarketDataClient(client);

        var result = await service.GetMarketDataAsync(
            "EURUSD",
            "FifteenMinutes",
            100);

        Assert.NotNull(result);
        Assert.Equal("EURUSD", result.Symbol);
        Assert.Equal(2, handler.Calls);
    }

    [Fact]
    public async Task MarketData_DoesNotRetryA4xx()
    {
        var handler = new _SequencedHandler(
            new[] { HttpStatusCode.BadRequest },
            ValidMarketDataJson);
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://python-ai.example")
        };
        var service = new PythonMarketDataClient(client);

        var ex = await Assert.ThrowsAsync<HttpRequestException>(
            () => service.GetMarketDataAsync("EURUSD", "FifteenMinutes", 100));

        Assert.Equal(HttpStatusCode.BadRequest, ex.StatusCode);
        Assert.Equal(1, handler.Calls);
    }
}
