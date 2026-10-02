using System.Text.Json.Serialization;

namespace ForexAI.Application.Contracts.ForexPairs;

public sealed record ForexPairDto(
    [property: JsonPropertyName("id")]
    Guid Id,

    [property: JsonPropertyName("symbol")]
    string Symbol
);