using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using ForexAI.Domain.Enums;
using System.Text.Json.Serialization;

namespace ForexAI.Application.Contracts.Analysis;

public sealed record AnalyzeMarketRequest(
    [property: JsonPropertyName("forex_pair_id")]
    Guid ForexPairId,

    [property: JsonPropertyName("symbol")]
    string Symbol,

    [property: JsonPropertyName("timeframe")]
    [property: JsonConverter(
        typeof(JsonStringEnumConverter))]
    Timeframe Timeframe
);
