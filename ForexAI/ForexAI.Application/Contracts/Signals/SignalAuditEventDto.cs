using System.Text.Json.Serialization;

namespace ForexAI.Application.Contracts.Signals;

public sealed record SignalAuditEventDto(
    [property: JsonPropertyName("id")]
    Guid Id,

    [property: JsonPropertyName("signal_id")]
    Guid SignalId,

    [property: JsonPropertyName("event_type")]
    string EventType,

    [property: JsonPropertyName("reason")]
    string? Reason,

    [property: JsonPropertyName("created_at")]
    DateTimeOffset CreatedAt
);