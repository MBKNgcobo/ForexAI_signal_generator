using ForexAI.Application.Contracts.Signals;
using ForexAI.Application.Interfaces;
using ForexAI.Domain.Enums;

namespace ForexAI.Application.Services;

public sealed class SignalHistoryService
{
    private readonly ITradingSignalRepository _repository;

    public SignalHistoryService(
        ITradingSignalRepository repository)
    {
        _repository = repository;
    }

    public async Task<IReadOnlyList<SignalHistoryDto>> GetAllAsync(
        CancellationToken cancellationToken = default)
    {
        var signals =
            await _repository.GetAllAsync(
                cancellationToken);

        return signals
            .Select(Map)
            .ToList();
    }

    public async Task<IReadOnlyList<SignalHistoryDto>> GetByStatusAsync(
        SignalStatus status,
        CancellationToken cancellationToken = default)
    {
        var signals =
            await _repository.GetByStatusAsync(
                status,
                cancellationToken);

        return signals
            .Select(Map)
            .ToList();
    }

    private static SignalHistoryDto Map(
        ForexAI.Domain.Entities.TradingSignal signal)
    {
        return new SignalHistoryDto(
            signal.Id,
            signal.Direction.ToString(),
            signal.Confidence,
            signal.EntryPrice,
            signal.StopLoss,
            signal.TakeProfit,
            signal.RiskReward,
            signal.Timeframe.ToString(),
            signal.Status.ToString(),
            signal.Reasoning,
            signal.CreatedAt);
    }
    public async Task<PagedSignalHistoryResult> GetPagedAsync(
    SignalHistoryQuery query,
    CancellationToken cancellationToken = default)
    {
        if (query.Page < 1)
        {
            throw new ArgumentException(
                "Page must be greater than zero.");
        }

        if (query.PageSize < 1 || query.PageSize > 100)
        {
            throw new ArgumentException(
                "Page size must be between 1 and 100.");
        }

        var result =
            await _repository.GetPagedAsync(
                query.Page,
                query.PageSize,
                query.Status,
                cancellationToken);

        var items = result.Items
            .Select(Map)
            .ToList();

        var totalPages =
            (int)Math.Ceiling(
                result.TotalItems /
                (double)query.PageSize);

        return new PagedSignalHistoryResult(
            items,
            query.Page,
            query.PageSize,
            result.TotalItems,
            totalPages);
    }

    public async Task<SignalHistoryDto?> GetByIdAsync(
    Guid id,
    CancellationToken cancellationToken = default)
    {
        var signal =
            await _repository.GetByIdAsync(
                id,
                cancellationToken);

        return signal is null
            ? null
            : Map(signal);
    }
}