namespace ForexAI.Application.Contracts.Signals;

public sealed record PagedSignalHistoryResult(
    IReadOnlyList<SignalHistoryDto> Items,
    int Page,
    int PageSize,
    int TotalItems,
    int TotalPages
);