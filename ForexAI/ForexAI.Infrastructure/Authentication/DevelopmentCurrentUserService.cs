using ForexAI.Application.Interfaces;

namespace ForexAI.Infrastructure.Authentication;

public sealed class DevelopmentCurrentUserService : ICurrentUserService
{
    private readonly Guid _userId;

    public DevelopmentCurrentUserService(Guid userId)
    {
        _userId = userId;
    }

    public Guid UserId => _userId;

    public bool IsAuthenticated => true;
}