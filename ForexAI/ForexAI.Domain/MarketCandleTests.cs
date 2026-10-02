using ForexAI.Domain.Entities;
using ForexAI.Domain.Enums;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Xunit;

namespace ForexAI.Tests.Domain;

public class MarketCandleTests
{
    /*
     * The market data is going to be one of the most important inputs to the entire system
     */
    [Fact]
    public void ValidCandle_ShouldBeCreated()
    {
        // Arrange
        var pairId = Guid.NewGuid();

        // Act
        var candle = new MarketCandle(
            pairId,
            DateTimeOffset.UtcNow,
            1.1650m,
            1.1700m,
            1.1600m,
            1.1680m,
            1000m,
            Timeframe.OneHour);

        // Assert
        Assert.Equal(pairId, candle.ForexPairId);
        Assert.Equal(1.1650m, candle.Open);
        Assert.Equal(1.1700m, candle.High);
        Assert.Equal(1.1600m, candle.Low);
        Assert.Equal(1.1680m, candle.Close);
        Assert.Equal(Timeframe.OneHour, candle.Timeframe);
    }

    [Fact]
    public void HighCannotBeLowerThanLow()
    {
        var pairId = Guid.NewGuid();

        Assert.Throws<ArgumentException>(() =>
            new MarketCandle(
                pairId,
                DateTimeOffset.UtcNow,
                1.1650m,
                1.1500m,
                1.1600m,
                1.1620m,
                1000m,
                Timeframe.OneHour));
    }

    [Fact]
    public void OpenMustBeBetweenHighAndLow()
    {
        var pairId = Guid.NewGuid();

        Assert.Throws<ArgumentException>(() =>
            new MarketCandle(
                pairId,
                DateTimeOffset.UtcNow,
                1.1750m,
                1.1700m,
                1.1600m,
                1.1650m,
                1000m,
                Timeframe.OneHour));
    }

    [Fact]
    public void CloseMustBeBetweenHighAndLow()
    {
        var pairId = Guid.NewGuid();

        Assert.Throws<ArgumentException>(() =>
            new MarketCandle(
                pairId,
                DateTimeOffset.UtcNow,
                1.1650m,
                1.1700m,
                1.1600m,
                1.1750m,
                1000m,
                Timeframe.OneHour));
    }

    [Fact]
    public void NegativeVolume_ShouldThrowException()
    {
        var pairId = Guid.NewGuid();

        Assert.Throws<ArgumentException>(() =>
            new MarketCandle(
                pairId,
                DateTimeOffset.UtcNow,
                1.1650m,
                1.1700m,
                1.1600m,
                1.1650m,
                -100m,
                Timeframe.OneHour));
    }
}