using ForexAI.Domain.Enums;
using Microsoft.AspNetCore.Mvc;

namespace ForexAI.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class TimeframesController : ControllerBase
{
    [HttpGet]
    public IActionResult GetAll()
    {
        var timeframes = Enum
            .GetValues<Timeframe>()
            .Select(timeframe => new
            {
                value = timeframe.ToString(),
                label = FormatTimeframe(timeframe)
            })
            .ToList();

        return Ok(timeframes);
    }

    private static string FormatTimeframe(
        Timeframe timeframe)
    {
        return timeframe switch
        {
            Timeframe.OneMinute => "1 Minute",
            Timeframe.FiveMinutes => "5 Minutes",
            Timeframe.FifteenMinutes => "15 Minutes",
            Timeframe.OneHour => "1 Hour",
            Timeframe.FourHours => "4 Hours",
            Timeframe.OneDay => "1 Day",

            _ => timeframe.ToString()
        };
    }
}