using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Hosting;
using Xunit;

namespace ForexAI.Tests.Api;

/// <summary>
/// Hosts the real application and exercises its HTTP surface.
/// </summary>
/// <remarks>
/// These exist because of a deploy failure that no unit test could see:
/// a duplicate <c>MapGet("/health")</c> in Program.cs collided with the
/// existing <c>HealthController</c>, so Kestrel threw
/// <c>AmbiguousMatchException</c>, <c>/health</c> returned 500, and Render
/// restarted the service in a loop until the deploy timed out. An ambiguous
/// route only reveals itself when something actually routes a request, so
/// the assertion has to be made over HTTP.
/// </remarks>
public sealed class HealthEndpointTests
    : IClassFixture<ApiWebApplicationFactory>
{
    private readonly HttpClient _client;

    public HealthEndpointTests(
        ApiWebApplicationFactory factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task Health_ReturnsOk_AndIsNotAmbiguous()
    {
        // Act
        var response = await _client.GetAsync("/health");

        // Assert
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var body = await response.Content.ReadAsStringAsync();

        Assert.DoesNotContain("AmbiguousMatchException", body);
    }

    [Fact]
    public async Task Health_ReportsItselfHealthy()
    {
        // Act
        var response = await _client.GetAsync("/health");

        // Assert
        var body =
            await response.Content.ReadFromJsonAsync<
                HealthResponse>();

        Assert.NotNull(body);
        Assert.Equal("healthy", body!.Status);
        Assert.Equal("ForexAI.Api", body.Service);
    }

    [Fact]
    public async Task Health_DoesNotRequireAuthentication()
    {
        // Arrange: an orchestrator cannot present a JWT, so this route must
        // stay anonymous. The client sends no Authorization header.

        // Act
        var response = await _client.GetAsync("/health");

        // Assert
        Assert.NotEqual(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.NotEqual(
            HttpStatusCode.Found,
            response.StatusCode);
    }

    [Fact]
    public async Task Ready_ReturnsServiceUnavailable_WhenTheDatabaseIsUnreachable()
    {
        // Arrange: the factory points at a database that does not exist.

        // Act
        var response = await _client.GetAsync("/health/ready");

        // Assert: 503 is the contract ("not ready"), not a 500. A 500 here
        // would mean the endpoint itself is broken.
        Assert.Equal(
            HttpStatusCode.ServiceUnavailable,
            response.StatusCode);

        var body = await response.Content.ReadAsStringAsync();

        Assert.Contains("not_ready", body);
    }

    private sealed record HealthResponse(
        string Status,
        string Service,
        DateTimeOffset Timestamp);
}

/// <summary>
/// Boots the API with configuration that satisfies startup validation
/// without needing any real dependency.
/// </summary>
/// <remarks>
/// The values are injected as environment variables rather than through
/// <c>ConfigureAppConfiguration</c>. With minimal hosting, WebApplicationFactory
/// resolves the generated entry point directly (<c>HostFactoryResolver</c>),
/// and configuration callbacks registered on the web host builder run too
/// late - the app has already read its JWT settings and thrown. Environment
/// variables are read by the default configuration source, so they are in
/// place before <c>Program.&lt;Main&gt;$</c> starts.
/// </remarks>
public sealed class ApiWebApplicationFactory
    : WebApplicationFactory<Program>
{
    public ApiWebApplicationFactory()
    {
        Set("ASPNETCORE_ENVIRONMENT", Environments.Production);

        // Startup validation requires a >= 32 byte signing key.
        Set("Jwt__Issuer", "ForexAI");
        Set("Jwt__Audience", "ForexAI.Client");
        Set(
            "Jwt__Key",
            "test-signing-key-that-is-at-least-32-bytes");

        // Syntactically valid but unreachable: nothing opens a connection
        // during these tests, and /health/ready is expected to report the
        // database as unhealthy.
        Set(
            "ConnectionStrings__ForexAiDatabase",
            "Host=127.0.0.1;Port=1;Database=none;" +
            "Username=none;Password=none");

        Set(
            "Cors__AllowedOrigins__0",
            "https://forexai-dashboard.onrender.com");
    }

    private static void Set(string name, string value) =>
        Environment.SetEnvironmentVariable(name, value);
}
