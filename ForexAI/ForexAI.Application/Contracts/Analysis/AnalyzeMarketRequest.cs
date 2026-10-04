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
    Timeframe Timeframe,

    /// <summary>
    /// Optional HTTP(S) push target (P4). When set, the Python service
    /// POSTs the finished analysis to this URL, which is how a hosted
    /// signal generator reaches a local MT5 execution bridge without the
    /// dashboard polling. Delivery is best-effort and SSRF-guarded by the
    /// Python service's WEBHOOK_ALLOWLIST.
    /// </summary>
    [property: JsonPropertyName("webhook_url")]
    [property: JsonIgnore(
        Condition = JsonIgnoreCondition.WhenWritingNull)]
    string? WebhookUrl = null
);
