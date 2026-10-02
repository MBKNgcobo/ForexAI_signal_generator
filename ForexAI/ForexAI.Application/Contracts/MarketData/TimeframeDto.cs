using System.Text.Json.Serialization;

namespace ForexAI.Application.Contracts.MarketData;

public sealed record TimeframeDto(
    [property: JsonPropertyName("value")]
    string Value,

    [property: JsonPropertyName("label")]
    string Label
);