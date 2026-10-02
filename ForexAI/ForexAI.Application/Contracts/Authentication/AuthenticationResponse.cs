using System.Text.Json.Serialization;

namespace ForexAI.Application.Contracts.Authentication;

public sealed record AuthenticationResponse(
    [property: JsonPropertyName("user_id")]
    Guid UserId,

    [property: JsonPropertyName("email")]
    string Email,

    [property: JsonPropertyName("display_name")]
    string DisplayName,

    [property: JsonPropertyName("token")]
    string Token
);