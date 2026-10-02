namespace ForexAI.Domain.Entities;

public sealed class SignalAuditEvent
{
    private SignalAuditEvent()
    {
    }

    public SignalAuditEvent(
        Guid signalId,
        string eventType,
        string? reason = null)
    {
        if (signalId == Guid.Empty)
        {
            throw new ArgumentException(
                "Signal ID is required.",
                nameof(signalId));
        }

        if (string.IsNullOrWhiteSpace(eventType))
        {
            throw new ArgumentException(
                "Event type is required.",
                nameof(eventType));
        }

        SignalId = signalId;
        EventType = eventType;
        Reason = reason;
        CreatedAt = DateTimeOffset.UtcNow;
    }

    public Guid Id { get; private set; }

    public Guid SignalId { get; private set; }

    public string EventType { get; private set; } = string.Empty;

    public string? Reason { get; private set; }

    public DateTimeOffset CreatedAt { get; private set; }
}