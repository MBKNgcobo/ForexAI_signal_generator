using ForexAI.Domain.Entities;

namespace ForexAI.Application.Interfaces;

public interface ISignalAuditRepository
{
    Task AddAsync(
        SignalAuditEvent auditEvent,
        CancellationToken cancellationToken = default);

    Task<IReadOnlyList<SignalAuditEvent>> GetBySignalIdAsync(
        Guid signalId,
        CancellationToken cancellationToken = default);
}