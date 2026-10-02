using ForexAI.Domain.Entities;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Xunit;

namespace ForexAI.Tests.Domain;

public class MarketAnalysisTests
{
    [Fact]
    public void ValidMarketAnalysis_ShouldBeCreated()
    {
        var analysis = new MarketAnalysis(
            Guid.NewGuid(),
            "Bullish",
            0.012m,
            "Trending",
            "Strong upward momentum.");

        Assert.Equal("Bullish", analysis.Trend);
        Assert.Equal(0.012m, analysis.Volatility);
        Assert.Equal("Trending", analysis.MarketRegime);
        Assert.Equal(
            "Strong upward momentum.",
            analysis.Summary);
    }

    [Fact]
    public void NegativeVolatility_ShouldThrowException()
    {
        Assert.Throws<ArgumentException>(() =>
            new MarketAnalysis(
                Guid.NewGuid(),
                "Bullish",
                -1m,
                "Trending",
                "Test."));
    }
}
