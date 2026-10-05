using ForexAI.Application.Services;
using Microsoft.AspNetCore.Mvc;

namespace ForexAI.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class MarketDataController : ControllerBase
{
    private readonly MarketDataService _marketDataService;

    public MarketDataController(
        MarketDataService marketDataService)
    {
        _marketDataService = marketDataService;
    }

    [HttpGet("{symbol}")]
    public async Task<IActionResult> GetMarketData(
        string symbol,
        [FromQuery] string timeframe,
        [FromQuery] int limit = 100,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var result =
                await _marketDataService.ExecuteAsync(
                    symbol,
                    timeframe,
                    limit,
                    cancellationToken);

            return Ok(result);
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new { message = ex.Message });
        }
        catch (HttpRequestException ex)
        {
            // A 4xx from the Python service is a client error; only 5xx /
            // connection failures (incl. a free-tier cold start) are 503.
            if (ex.StatusCode is not null &&
                (int)ex.StatusCode >= 400 &&
                (int)ex.StatusCode < 500)
            {
                return BadRequest(new { message = ex.Message });
            }

            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                new { message = ex.Message });
        }
        catch (TaskCanceledException)
        {
            if (cancellationToken.IsCancellationRequested)
            {
                throw;
            }

            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                new
                {
                    message =
                        "The market-data request timed out. Please retry shortly."
                });
        }
    }
}