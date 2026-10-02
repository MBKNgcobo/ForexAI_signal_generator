using ForexAI.Application.Contracts.MarketData;

namespace ForexAI.Application.Services;

public sealed class TimeframeService
{
    public IReadOnlyList<TimeframeDto> GetAll()
    {
        return
        [
            new TimeframeDto("OneMinute", "1 Minute"),
            new TimeframeDto("FiveMinutes", "5 Minutes"),
            new TimeframeDto("FifteenMinutes", "15 Minutes"),
            new TimeframeDto("OneHour", "1 Hour"),
            new TimeframeDto("FourHours", "4 Hours"),
            new TimeframeDto("OneDay", "1 Day")
        ];
    }
}