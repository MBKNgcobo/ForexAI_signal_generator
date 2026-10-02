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
        var result =
            await _marketDataService.ExecuteAsync(
                symbol,
                timeframe,
                limit,
                cancellationToken);

        return Ok(result);
    }
}