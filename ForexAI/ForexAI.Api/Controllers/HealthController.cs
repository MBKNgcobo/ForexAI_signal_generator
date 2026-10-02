using ForexAI.Infrastructure.Persistence;

using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace ForexAI.Api.Controllers;

[ApiController]
[Route("health")]
public sealed class HealthController : ControllerBase
{
    private readonly ForexAiDbContext _db;
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IConfiguration _configuration;

    public HealthController(
        ForexAiDbContext db,
        IHttpClientFactory httpClientFactory,
        IConfiguration configuration)
    {
        _db = db;
        _httpClientFactory = httpClientFactory;
        _configuration = configuration;
    }

    [HttpGet]
    public IActionResult Get()
    {
        return Ok(new
        {
            status = "healthy",
            service = "ForexAI.Api",
            timestamp = DateTimeOffset.UtcNow
        });
    }

    [HttpGet("ready")]
    public async Task<IActionResult> Ready(
        CancellationToken cancellationToken)
    {
        var databaseHealthy = false;
        var pythonAiHealthy = false;

        // ----------------------------------------------------
        // PostgreSQL readiness
        // ----------------------------------------------------

        try
        {
            databaseHealthy =
                await _db.Database.CanConnectAsync(
                    cancellationToken);
        }
        catch
        {
            databaseHealthy = false;
        }

        // ----------------------------------------------------
        // Python AI readiness
        // ----------------------------------------------------

        try
        {
            var pythonBaseUrl =
                _configuration["PythonApi:BaseUrl"];

            if (!string.IsNullOrWhiteSpace(pythonBaseUrl))
            {
                using var client =
                    _httpClientFactory.CreateClient();

                client.Timeout =
                    TimeSpan.FromSeconds(3);

                var healthUrl =
                    new Uri(
                        new Uri(pythonBaseUrl),
                        "/health");

                using var response =
                    await client.GetAsync(
                        healthUrl,
                        cancellationToken);

                pythonAiHealthy =
                    response.IsSuccessStatusCode;
            }
        }
        catch
        {
            pythonAiHealthy = false;
        }

        var ready =
            databaseHealthy &&
            pythonAiHealthy;

        var result = new
        {
            status = ready
                ? "ready"
                : "not_ready",

            service = "ForexAI.Api",

            dependencies = new
            {
                database = databaseHealthy
                    ? "healthy"
                    : "unhealthy",

                python_ai = pythonAiHealthy
                    ? "healthy"
                    : "unhealthy"
            },

            timestamp = DateTimeOffset.UtcNow
        };

        if (!ready)
        {
            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                result);
        }

        return Ok(result);
    }
}