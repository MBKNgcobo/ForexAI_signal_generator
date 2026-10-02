using System.Text.Json.Serialization;

namespace ForexAI.Application.Contracts.Signals;

public sealed record SignalHistoryDto(
    [property: JsonPropertyName("signal_id")]
    Guid SignalId,

    [property: JsonPropertyName("direction")]
    string Direction,

    [property: JsonPropertyName("confidence")]
    decimal Confidence,

    [property: JsonPropertyName("entry_price")]
    decimal EntryPrice,

    [property: JsonPropertyName("stop_loss")]
    decimal StopLoss,

    [property: JsonPropertyName("take_profit")]
    decimal TakeProfit,

    [property: JsonPropertyName("risk_reward")]
    decimal RiskReward,

    [property: JsonPropertyName("timeframe")]
    string Timeframe,

    [property: JsonPropertyName("status")]
    string Status,

    [property: JsonPropertyName("reasoning")]
    string Reasoning,

    [property: JsonPropertyName("created_at")]
    DateTimeOffset CreatedAt
);