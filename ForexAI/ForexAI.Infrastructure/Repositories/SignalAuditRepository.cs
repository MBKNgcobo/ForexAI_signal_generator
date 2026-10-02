using ForexAI.Application.Interfaces;
using ForexAI.Domain.Entities;
using ForexAI.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;

namespace ForexAI.Infrastructure.Repositories;

public sealed class SignalAuditRepository
    : ISignalAuditRepository
{
    private readonly ForexAiDbContext _context;

    public SignalAuditRepository(
        ForexAiDbContext context)
    {
        _context = context;
    }

    public async Task AddAsync(
        SignalAuditEvent auditEvent,
        CancellationToken cancellationToken = default)
    {
        await _context.SignalAuditEvents.AddAsync(
            auditEvent,
            cancellationToken);

        await _context.SaveChangesAsync(
            cancellationToken);
    }

    public async Task<IReadOnlyList<SignalAuditEvent>>
        GetBySignalIdAsync(
            Guid signalId,
            CancellationToken cancellationToken = default)
    {
        return await _context.SignalAuditEvents
            .AsNoTracking()
            .Where(x => x.SignalId == signalId)
            .OrderBy(x => x.CreatedAt)
            .ToListAsync(cancellationToken);
    }
}