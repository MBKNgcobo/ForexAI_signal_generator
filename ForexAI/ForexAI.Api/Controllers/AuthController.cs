using ForexAI.Application.Contracts.Authentication;
using ForexAI.Application.Interfaces;
using Microsoft.AspNetCore.Mvc;

namespace ForexAI.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class AuthController : ControllerBase
{
    private readonly IAuthenticationService _authenticationService;

    public AuthController(
        IAuthenticationService authenticationService)
    {
        _authenticationService =
            authenticationService;
    }

    [HttpPost("register")]
    public async Task<IActionResult> Register(
        RegisterRequest request,
        CancellationToken cancellationToken)
    {
        try
        {
            var result =
                await _authenticationService.RegisterAsync(
                    request,
                    cancellationToken);

            return Ok(result);
        }
        catch (InvalidOperationException ex)
        {
            return BadRequest(new
            {
                message = ex.Message
            });
        }
    }

    [HttpPost("login")]
    public async Task<IActionResult> Login(
        LoginRequest request,
        CancellationToken cancellationToken)
    {
        try
        {
            var result =
                await _authenticationService.LoginAsync(
                    request,
                    cancellationToken);

            return Ok(result);
        }
        catch (InvalidOperationException)
        {
            return Unauthorized(new
            {
                message = "Invalid email or password."
            });
        }
    }
}