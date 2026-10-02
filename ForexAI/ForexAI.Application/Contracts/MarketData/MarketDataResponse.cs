using System.Text.Json.Serialization;

namespace ForexAI.Application.Contracts.MarketData;

public sealed record MarketCandleDto(
    [property: JsonPropertyName("timestamp")]
    DateTimeOffset Timestamp,

    [property: JsonPropertyName("open")]
    decimal Open,

    [property: JsonPropertyName("high")]
    decimal High,

    [property: JsonPropertyName("low")]
    decimal Low,

    [property: JsonPropertyName("close")]
    decimal Close,

    [property: JsonPropertyName("volume")]
    decimal Volume
);

public sealed record MarketDataResponse(
    [property: JsonPropertyName("symbol")]
    string Symbol,

    [property: JsonPropertyName("timeframe")]
    string Timeframe,

    [property: JsonPropertyName("candles")]
    IReadOnlyList<MarketCandleDto> Candles
);