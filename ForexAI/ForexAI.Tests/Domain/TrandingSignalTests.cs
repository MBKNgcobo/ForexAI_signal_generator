using ForexAI.Domain.Entities;
using ForexAI.Domain.Enums;
using Xunit;

namespace ForexAI.Tests.Domain;

public class TradingSignalTests
{
    private static readonly Guid TestUserId =
        Guid.Parse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");

    private static readonly Guid TestForexPairId =
        Guid.Parse("11111111-1111-1111-1111-111111111111");

    [Fact]
    public void NewSignal_ShouldHaveGeneratedStatus()
    {
        // Arrange
        var pairId = TestForexPairId;

        // Act
        var signal = new TradingSignal(
            TestUserId,
            pairId,
            SignalDirection.Buy,
            0.85m,
            1.1000m,
            1.0950m,
            1.1100m,
            2.0m,
            Timeframe.FifteenMinutes,
            "Test reasoning");

        // Assert
        Assert.Equal(
            SignalStatus.Generated,
            signal.Status);
    }

    private static TradingSignal CreateValidSignal()
    {
        return new TradingSignal(
            TestUserId,
            TestForexPairId,
            SignalDirection.Buy,
            0.80m,
            1.1650m,
            1.1600m,
            1.1750m,
            2.0m,
            Timeframe.FourHours,
            "Bullish momentum with positive technical confirmation.");
    }

    [Fact]
    public void GeneratedSignal_ShouldMoveToUnderReview()
    {
        // Arrange
        var signal = CreateValidSignal();

        // Act
        signal.SubmitForReview();

        // Assert
        Assert.Equal(
            SignalStatus.UnderReview,
            signal.Status);
    }

    [Fact]
    public void UnderReviewSignal_ShouldBeAccepted()
    {
        // Arrange
        var signal = CreateValidSignal();
        signal.SubmitForReview();

        // Act
        signal.Accept();

        // Assert
        Assert.Equal(
            SignalStatus.Accepted,
            signal.Status);
    }

    [Fact]
    public void UnderReviewSignal_ShouldBeRejected()
    {
        // Arrange
        var signal = CreateValidSignal();
        signal.SubmitForReview();

        // Act
        signal.Reject();

        // Assert
        Assert.Equal(
            SignalStatus.Rejected,
            signal.Status);
    }

    [Fact]
    public void GeneratedSignal_ShouldNotBeAcceptedDirectly()
    {
        // Arrange
        var signal = CreateValidSignal();

        // Act & Assert
        Assert.Throws<InvalidOperationException>(
            () => signal.Accept());
    }

    [Fact]
    public void GeneratedSignal_ShouldNotBeRejectedDirectly()
    {
        // Arrange
        var signal = CreateValidSignal();

        // Act & Assert
        Assert.Throws<InvalidOperationException>(
            () => signal.Reject());
    }

    [Fact]
    public void ConfidenceAboveOne_ShouldThrowException()
    {
        Assert.Throws<ArgumentException>(() =>
            new TradingSignal(
                TestUserId,
                TestForexPairId,
                SignalDirection.Buy,
                1.5m,
                1.1650m,
                1.1600m,
                1.1750m,
                2.0m,
                Timeframe.FourHours,
                "Test reasoning."));
    }

    [Fact]
    public void NegativeConfidence_ShouldThrowException()
    {
        Assert.Throws<ArgumentException>(() =>
            new TradingSignal(
                TestUserId,
                TestForexPairId,
                SignalDirection.Buy,
                -0.1m,
                1.1650m,
                1.1600m,
                1.1750m,
                2.0m,
                Timeframe.FourHours,
                "Test reasoning."));
    }

    [Fact]
    public void ZeroEntryPrice_ShouldThrowException()
    {
        Assert.Throws<ArgumentException>(() =>
            new TradingSignal(
                TestUserId,
                TestForexPairId,
                SignalDirection.Buy,
                0.80m,
                0m,
                1.1600m,
                1.1750m,
                2.0m,
                Timeframe.FourHours,
                "Test reasoning."));
    }

    [Fact]
    public void MissingReasoning_ShouldThrowException()
    {
        Assert.Throws<ArgumentException>(() =>
            new TradingSignal(
                TestUserId,
                TestForexPairId,
                SignalDirection.Buy,
                0.80m,
                1.1650m,
                1.1600m,
                1.1750m,
                2.0m,
                Timeframe.FourHours,
                ""));
    }
}