using ForexAI.Application.Contracts.Authentication;
using ForexAI.Application.Interfaces;
using ForexAI.Domain.Entities;
using ForexAI.Infrastructure.Identity;
using ForexAI.Infrastructure.Persistence;
using Microsoft.AspNetCore.Identity;

namespace ForexAI.Infrastructure.Authentication;

public sealed class AuthenticationService : IAuthenticationService
{
    private readonly UserManager<ApplicationUser> _userManager;
    private readonly JwtTokenService _jwtTokenService;
    private readonly ForexAiDbContext _dbContext;

    public AuthenticationService(
        UserManager<ApplicationUser> userManager,
        JwtTokenService jwtTokenService,
        ForexAiDbContext dbContext)
    {
        _userManager = userManager;
        _jwtTokenService = jwtTokenService;
        _dbContext = dbContext;
    }

    public async Task<AuthenticationResponse> RegisterAsync(
        RegisterRequest request,
        CancellationToken cancellationToken = default)
    {
        var existingUser = await _userManager.FindByEmailAsync(request.Email);

        if (existingUser is not null)
        {
            throw new InvalidOperationException(
                "A user with this email already exists.");
        }

        var domainUser = new User(
            request.Email,
            request.DisplayName);

        var identityUser = new ApplicationUser
        {
            Id = Guid.NewGuid(),
            UserName = request.Email,
            Email = request.Email,
            DomainUserId = domainUser.Id
        };

        var result = await _userManager.CreateAsync(
            identityUser,
            request.Password);

        if (!result.Succeeded)
        {
            var errors = string.Join(
                "; ",
                result.Errors.Select(e => e.Description));

            throw new InvalidOperationException(errors);
        }

        _dbContext.Users.Add(domainUser);

        await _dbContext.SaveChangesAsync(cancellationToken);

        var token = _jwtTokenService.GenerateToken(
            identityUser,
            domainUser);

        return new AuthenticationResponse(
            domainUser.Id,
            domainUser.Email,
            domainUser.DisplayName,
            token);
    }

    public async Task<AuthenticationResponse> LoginAsync(
        LoginRequest request,
        CancellationToken cancellationToken = default)
    {
        var identityUser = await _userManager.FindByEmailAsync(request.Email);

        if (identityUser is null)
        {
            throw new InvalidOperationException(
                "Invalid email or password.");
        }

        var passwordValid = await _userManager.CheckPasswordAsync(
            identityUser,
            request.Password);

        if (!passwordValid)
        {
            throw new InvalidOperationException(
                "Invalid email or password.");
        }

        var domainUser = await _dbContext.Users
            .FindAsync(
                new object[] { identityUser.DomainUserId },
                cancellationToken);

        if (domainUser is null)
        {
            throw new InvalidOperationException(
                "User profile could not be found.");
        }

        var token = _jwtTokenService.GenerateToken(
            identityUser,
            domainUser);

        return new AuthenticationResponse(
            domainUser.Id,
            domainUser.Email,
            domainUser.DisplayName,
            token);
    }
}