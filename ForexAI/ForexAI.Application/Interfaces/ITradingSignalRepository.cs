using ForexAI.Domain.Entities;
using ForexAI.Domain.Enums;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace ForexAI.Application.Interfaces;

public interface ITradingSignalRepository
{
    Task AddAsync(
        TradingSignal signal,
        CancellationToken cancellationToken = default);

    Task<TradingSignal?> GetByIdAsync(
        Guid id,
        CancellationToken cancellationToken = default);

    Task SaveAsync(
        TradingSignal signal,
        CancellationToken cancellationToken = default);

    Task<IReadOnlyList<TradingSignal>> GetAllAsync(
    CancellationToken cancellationToken = default);

    Task<IReadOnlyList<TradingSignal>> GetByStatusAsync(
        SignalStatus status,
        CancellationToken cancellationToken = default);

    Task<(IReadOnlyList<TradingSignal> Items, int TotalItems)>
GetPagedAsync(int page,int pageSize,
    SignalStatus? status = null,
    CancellationToken cancellationToken = default);
}
