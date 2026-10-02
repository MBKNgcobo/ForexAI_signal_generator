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
            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                new { message = ex.Message });
        }
    }
}