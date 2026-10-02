using ForexAI.Application.Contracts.Signals;
using ForexAI.Application.Interfaces;

namespace ForexAI.Application.Services;

public sealed class SignalAuditService
{
    private readonly ISignalAuditRepository _repository;

    public SignalAuditService(
        ISignalAuditRepository repository)
    {
        _repository = repository;
    }

    public async Task<IReadOnlyList<SignalAuditEventDto>>
        GetBySignalIdAsync(
            Guid signalId,
            CancellationToken cancellationToken = default)
    {
        if (signalId == Guid.Empty)
        {
            throw new ArgumentException(
                "Signal ID is required.",
                nameof(signalId));
        }

        var events =
            await _repository.GetBySignalIdAsync(
                signalId,
                cancellationToken);

        return events
            .Select(Map)
            .ToList();
    }

    private static SignalAuditEventDto Map(
        ForexAI.Domain.Entities.SignalAuditEvent auditEvent)
    {
        return new SignalAuditEventDto(
            auditEvent.Id,
            auditEvent.SignalId,
            auditEvent.EventType,
            auditEvent.Reason,
            auditEvent.CreatedAt);
    }
}