using ForexAI.Application.Services;
using Microsoft.AspNetCore.Mvc;

namespace ForexAI.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class ForexPairsController : ControllerBase
{
    private readonly ForexPairService _forexPairService;

    public ForexPairsController(
        ForexPairService forexPairService)
    {
        _forexPairService = forexPairService;
    }

    [HttpGet]
    public async Task<IActionResult> GetAll(
        CancellationToken cancellationToken)
    {
        var result =
            await _forexPairService.GetAllAsync(
                cancellationToken);

        return Ok(result);
    }
}