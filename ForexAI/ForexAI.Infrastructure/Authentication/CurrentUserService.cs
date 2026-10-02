using System.Security.Claims;
using ForexAI.Application.Interfaces;
using Microsoft.AspNetCore.Http;

namespace ForexAI.Infrastructure.Authentication;

public sealed class CurrentUserService : ICurrentUserService
{
    private readonly IHttpContextAccessor _httpContextAccessor;

    public CurrentUserService(
        IHttpContextAccessor httpContextAccessor)
    {
        _httpContextAccessor = httpContextAccessor;
    }

    public bool IsAuthenticated =>
        _httpContextAccessor
            .HttpContext?
            .User
            .Identity?
            .IsAuthenticated
        ?? false;

    public Guid UserId
    {
        get
        {
            var value =
                _httpContextAccessor
                    .HttpContext?
                    .User
                    .FindFirst(ClaimTypes.NameIdentifier)
                    ?.Value;

            return Guid.TryParse(
                value,
                out var userId)
                ? userId
                : Guid.Empty;
        }
    }
}