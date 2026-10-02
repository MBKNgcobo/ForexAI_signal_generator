using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using System.Security.Claims;
using System.Text.Encodings.Web;

namespace ForexAI.Infrastructure.Authentication;

public sealed class DevelopmentAuthenticationHandler
    : AuthenticationHandler<AuthenticationSchemeOptions>
{
    private readonly Guid _userId;

    public DevelopmentAuthenticationHandler(
        IOptionsMonitor<AuthenticationSchemeOptions> options,
        ILoggerFactory logger,
        UrlEncoder encoder,
        ISystemClock clock,
        IConfiguration configuration)
        : base(options, logger, encoder, clock)
    {
        _userId = configuration.GetValue<Guid>(
            "DevelopmentUser:UserId");
    }

    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (_userId == Guid.Empty)
        {
            return Task.FromResult(
                AuthenticateResult.Fail(
                    "Development user ID is not configured."));
        }

        var claims = new[]
        {
            new Claim(
                ClaimTypes.NameIdentifier,
                _userId.ToString()),

            new Claim(
                ClaimTypes.Name,
                "Development User")
        };

        var identity = new ClaimsIdentity(
            claims,
            "Development");

        var principal = new ClaimsPrincipal(identity);

        var ticket = new AuthenticationTicket(
            principal,
            "Development");

        return Task.FromResult(
            AuthenticateResult.Success(ticket));
    }
}