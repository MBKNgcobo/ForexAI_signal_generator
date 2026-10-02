namespace ForexAI.Application.Contracts.Authentication;

public sealed record RegisterRequest(
    string Email,
    string DisplayName,
    string Password
);