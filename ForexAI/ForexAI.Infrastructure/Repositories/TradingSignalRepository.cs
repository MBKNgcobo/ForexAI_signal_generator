using ForexAI.Application.Interfaces;
using ForexAI.Domain.Entities;
using ForexAI.Domain.Enums;
using ForexAI.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace ForexAI.Infrastructure.Repositories;

public class TradingSignalRepository : ITradingSignalRepository
{
    private readonly ForexAiDbContext _context;

    public TradingSignalRepository(ForexAiDbContext context)
    {
        _context = context;
    }

    public async Task AddAsync(
        TradingSignal signal,
        CancellationToken cancellationToken = default)
    {
        await _context.TradingSignals.AddAsync(
            signal,
            cancellationToken);
    }

    public async Task<TradingSignal?> GetByIdAsync(
        Guid id,
        CancellationToken cancellationToken = default)
    {
        return await _context.TradingSignals
            .FirstOrDefaultAsync(
                x => x.Id == id,
                cancellationToken);
    }

    public async Task SaveAsync(
        TradingSignal signal,
        CancellationToken cancellationToken = default)
    {
        await _context.SaveChangesAsync(cancellationToken);
    }
    public async Task<IReadOnlyList<TradingSignal>> GetAllAsync(
    CancellationToken cancellationToken = default)
    {
        return await _context.TradingSignals
            .AsNoTracking()
            .OrderByDescending(x => x.CreatedAt)
            .ToListAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<TradingSignal>> GetByStatusAsync(
    SignalStatus status,
    CancellationToken cancellationToken = default)
    {
        return await _context.TradingSignals
            .AsNoTracking()
            .Where(x => x.Status == status)
            .OrderByDescending(x => x.CreatedAt)
            .ToListAsync(cancellationToken);
    }

    Task<IReadOnlyList<TradingSignal>> ITradingSignalRepository.GetAllAsync(CancellationToken cancellationToken)
    {
        return GetAllAsync(cancellationToken);
    }
    public async Task<(IReadOnlyList<TradingSignal> Items, int TotalItems)>
    GetPagedAsync(
        int page,
        int pageSize,
        SignalStatus? status = null,
        CancellationToken cancellationToken = default)
    {
        var query = _context.TradingSignals
            .AsNoTracking();

        if (status.HasValue)
        {
            query = query.Where(
                x => x.Status == status.Value);
        }

        var totalItems = await query.CountAsync(
            cancellationToken);

        var items = await query
            .OrderByDescending(x => x.CreatedAt)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync(cancellationToken);

        return (items, totalItems);
    }
}