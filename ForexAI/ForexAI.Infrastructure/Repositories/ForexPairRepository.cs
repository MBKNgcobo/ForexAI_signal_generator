using ForexAI.Application.Interfaces;
using ForexAI.Domain.Entities;
using ForexAI.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;

namespace ForexAI.Infrastructure.Repositories;

public sealed class ForexPairRepository : IForexPairRepository
{
    private readonly ForexAiDbContext _context;

    public ForexPairRepository(ForexAiDbContext context)
    {
        _context = context;
    }

    public async Task<IReadOnlyList<ForexPair>> GetAllAsync(
        CancellationToken cancellationToken = default)
    {
        return await _context.ForexPairs
            .AsNoTracking()
            .OrderBy(x => x.Symbol)
            .ToListAsync(cancellationToken);
    }

    public async Task<ForexPair?> GetByIdAsync(
        Guid id,
        CancellationToken cancellationToken = default)
    {
        return await _context.ForexPairs
            .AsNoTracking()
            .FirstOrDefaultAsync(
                x => x.Id == id,
                cancellationToken);
    }
}
