using System.Text.Json.Serialization;

namespace ForexAI.Application.Contracts.Analysis;

public sealed record RiskAssessmentDto(
    [property: JsonPropertyName("risk_level")]
    string RiskLevel,

    [property: JsonPropertyName("approved")]
    bool Approved,

    [property: JsonPropertyName("agreement")]
    decimal Agreement,

    [property: JsonPropertyName("reason")]
    string Reason,

    [property: JsonPropertyName("entry_price")]
    decimal? EntryPrice,

    [property: JsonPropertyName("stop_loss")]
    decimal? StopLoss,

    [property: JsonPropertyName("take_profit")]
    decimal? TakeProfit,

    [property: JsonPropertyName("risk_reward")]
    decimal? RiskReward
);