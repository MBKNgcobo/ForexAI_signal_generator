using ForexAI.Application.Contracts.Analysis;
using ForexAI.Application.Services;
using Microsoft.AspNetCore.Mvc;

namespace ForexAI.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class AnalysisController : ControllerBase
{
    private readonly AnalyzeMarketService _analysisService;
    private readonly SignalGenerationService _signalGenerationService;
    public AnalysisController(
    AnalyzeMarketService analysisService,
    SignalGenerationService signalGenerationService)
    {
        _analysisService = analysisService;
        _signalGenerationService = signalGenerationService;
    }

    [HttpGet("health")]
    public IActionResult Health()
    {
        return Ok(new
        {
            Status = "ForexAI API is running"
        });
    }

    [HttpPost]
    public async Task<IActionResult> Analyze(
     [FromBody] AnalyzeMarketRequest request,
     CancellationToken cancellationToken)
    {
        try
        {
            var result = await _analysisService.ExecuteWithSignalAsync(
                request,
                cancellationToken);

            return Ok(result);
        }
        catch (InvalidOperationException ex)
        {
            return BadRequest(new { message = ex.Message });
        }
        catch (UnauthorizedAccessException ex)
        {
            return Unauthorized(new { message = ex.Message });
        }
        catch (HttpRequestException ex)
        {
            // A 4xx from the Python service is a client error (e.g. an
            // unsupported symbol) and must reach the dashboard as a 400,
            // not be conflated with a service outage. Only 5xx / connection
            // failures (which include a free-tier cold start) are 503.
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
            // The Python service did not respond before the call timed out
            // (a cold start that outran an attempt, or a hung LLM). Re-throw
            // when the *caller* cancelled so we do not try to write to a
            // disconnected client; otherwise surface a 503.
            if (cancellationToken.IsCancellationRequested)
            {
                throw;
            }

            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                new
                {
                    message =
                        "The AI analysis timed out. Please retry shortly."
                });
        }
    }
}