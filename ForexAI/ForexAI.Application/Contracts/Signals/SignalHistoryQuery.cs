using ForexAI.Domain.Enums;

namespace ForexAI.Application.Contracts.Signals;

public sealed record SignalHistoryQuery(
    int Page = 1,
    int PageSize = 10,
    SignalStatus? Status = null
);