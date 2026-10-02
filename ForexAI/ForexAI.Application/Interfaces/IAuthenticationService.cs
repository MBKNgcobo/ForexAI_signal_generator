using ForexAI.Application.Contracts.Authentication;

namespace ForexAI.Application.Interfaces;

public interface IAuthenticationService
{
    Task<AuthenticationResponse> RegisterAsync(
        RegisterRequest request,
        CancellationToken cancellationToken = default);

    Task<AuthenticationResponse> LoginAsync(
        LoginRequest request,
        CancellationToken cancellationToken = default);
}