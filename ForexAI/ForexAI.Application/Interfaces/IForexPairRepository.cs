using ForexAI.Domain.Entities;

namespace ForexAI.Application.Interfaces;

public interface IForexPairRepository
{
    Task<IReadOnlyList<ForexPair>> GetAllAsync(
        CancellationToken cancellationToken = default);

    Task<ForexPair?> GetByIdAsync(
        Guid id,
        CancellationToken cancellationToken = default);
}