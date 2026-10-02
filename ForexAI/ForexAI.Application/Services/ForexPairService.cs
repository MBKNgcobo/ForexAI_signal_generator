using ForexAI.Application.Contracts.ForexPairs;
using ForexAI.Application.Interfaces;

namespace ForexAI.Application.Services;

public sealed class ForexPairService
{
    private readonly IForexPairRepository _repository;

    public ForexPairService(IForexPairRepository repository)
    {
        _repository = repository;
    }

    public async Task<IReadOnlyList<ForexPairDto>> GetAllAsync(
        CancellationToken cancellationToken = default)
    {
        var pairs = await _repository.GetAllAsync(
            cancellationToken);

        return pairs
            .Select(pair =>
                new ForexPairDto(
                    pair.Id,
                    pair.Symbol))
            .ToList();
    }
}