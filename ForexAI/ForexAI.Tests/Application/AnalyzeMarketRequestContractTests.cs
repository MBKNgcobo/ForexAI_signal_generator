using System.Text.Json;
using ForexAI.Application.Contracts.Analysis;
using ForexAI.Domain.Enums;
using Xunit;

namespace ForexAI.Tests.Application;

/// <summary>
/// The wire contract between the C# gateway and the Python analysis
/// service. These are not internal refactor guards: a rename here silently
/// breaks the hosted signal generator, and the <c>webhook_url</c> field is
/// what lets a hosted analysis reach a local MT5 execution bridge.
/// </summary>
public class AnalyzeMarketRequestContractTests
{
    private static readonly Guid PairId =
        Guid.Parse("11111111-1111-1111-1111-111111111111");

    /// <summary>
    /// Matches what HttpClient.PostAsJsonAsync uses by default, so the
    /// assertions reflect the bytes that actually go over the wire.
    /// </summary>
    private static readonly JsonSerializerOptions WireOptions =
        new(JsonSerializerDefaults.Web);

    private static string Serialize(AnalyzeMarketRequest request) =>
        JsonSerializer.Serialize(request, WireOptions);

    [Fact]
    public void Serialize_WithoutWebhook_OmitsTheProperty()
    {
        // Arrange
        var request = new AnalyzeMarketRequest(
            PairId,
            "EURUSD",
            Timeframe.FifteenMinutes);

        // Act
        using var json = JsonDocument.Parse(Serialize(request));

        // Assert: an absent field, not an explicit null.
        Assert.False(
            json.RootElement.TryGetProperty(
                "webhook_url",
                out _));
    }

    [Fact]
    public void Serialize_WithWebhook_UsesTheSnakeCaseName()
    {
        // Arrange
        var request = new AnalyzeMarketRequest(
            PairId,
            "EURUSD",
            Timeframe.FifteenMinutes,
            "https://tunnel.trycloudflare.com/signal?token=abc");

        // Act
        using var json = JsonDocument.Parse(Serialize(request));

        // Assert
        Assert.Equal(
            "https://tunnel.trycloudflare.com/signal?token=abc",
            json.RootElement.GetProperty("webhook_url").GetString());
    }

    [Fact]
    public void Serialize_UsesTheFieldNamesPythonExpects()
    {
        // Arrange
        var request = new AnalyzeMarketRequest(
            PairId,
            "EURUSD",
            Timeframe.OneHour);

        // Act
        using var json = JsonDocument.Parse(Serialize(request));

        // Assert
        Assert.Equal(
            PairId.ToString(),
            json.RootElement.GetProperty("forex_pair_id").GetString());

        Assert.Equal(
            "EURUSD",
            json.RootElement.GetProperty("symbol").GetString());
    }

    [Fact]
    public void Serialize_WritesTimeframeAsItsStringName()
    {
        // Arrange: the Python schema validates timeframe against
        // "OneMinute".."OneDay", never an integer.
        var request = new AnalyzeMarketRequest(
            PairId,
            "GBPUSD",
            Timeframe.FourHours);

        // Act
        using var json = JsonDocument.Parse(Serialize(request));

        // Assert
        Assert.Equal(
            "FourHours",
            json.RootElement.GetProperty("timeframe").GetString());
    }

    [Fact]
    public void Deserialize_ReadsAPayloadProducedByAnyClient()
    {
        // Arrange: exactly the shape the dashboard/API sends.
        const string json =
            """
            {
              "forex_pair_id": "11111111-1111-1111-1111-111111111111",
              "symbol": "EURUSD",
              "timeframe": "FifteenMinutes",
              "webhook_url": "https://hooks.example.com/signal"
            }
            """;

        // Act
        var request = JsonSerializer.Deserialize<AnalyzeMarketRequest>(
            json,
            WireOptions);

        // Assert
        Assert.NotNull(request);
        Assert.Equal("EURUSD", request.Symbol);
        Assert.Equal(
            Timeframe.FifteenMinutes,
            request.Timeframe);
        Assert.Equal(
            "https://hooks.example.com/signal",
            request.WebhookUrl);
    }

    [Fact]
    public void Deserialize_AcceptsAPayloadWithoutAWebhook()
    {
        // Arrange: backwards compatibility - the dashboard does not send one.
        const string json =
            """
            {
              "forex_pair_id": "11111111-1111-1111-1111-111111111111",
              "symbol": "EURUSD",
              "timeframe": "FifteenMinutes"
            }
            """;

        // Act
        var request = JsonSerializer.Deserialize<AnalyzeMarketRequest>(
            json,
            WireOptions);

        // Assert
        Assert.NotNull(request);
        Assert.Null(request.WebhookUrl);
    }
}
