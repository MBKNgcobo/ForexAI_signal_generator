using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

using ForexAI.Domain.Enums;

namespace ForexAI.Domain.Entities;

public class TradingSignal
{
    public Guid Id { get; private set; }
    public Guid UserId { get; private set; }
    public Guid ForexPairId { get; private set; }
    public DateTimeOffset CreatedAt { get; private set; }
    public SignalDirection Direction { get; private set; }
    public decimal Confidence { get; private set; }
    public decimal EntryPrice { get; private set; }
    public decimal StopLoss { get; private set; }
    public decimal TakeProfit { get; private set; }
    public decimal RiskReward { get; private set; }
    public Timeframe Timeframe { get; private set; }
    public SignalStatus Status { get; private set; }
    public string Reasoning { get; private set; }

    private TradingSignal()
    {
        Reasoning = string.Empty;
    }

    public TradingSignal(
        Guid userId,
        Guid forexPairId,
        SignalDirection direction,
        decimal confidence,
        decimal entryPrice,
        decimal stopLoss,
        decimal takeProfit,
        decimal riskReward,
        Timeframe timeframe,
        string reasoning,
        DateTimeOffset? createdAt = null)
    {
        if (userId == Guid.Empty)
            throw new ArgumentException("User ID is required.", nameof(userId));

        if (forexPairId == Guid.Empty)
            throw new ArgumentException("Forex pair ID is required.", nameof(forexPairId));

        if (confidence < 0 || confidence > 1)
            throw new ArgumentException("Confidence must be between 0 and 1.", nameof(confidence));

        if (entryPrice <= 0)
            throw new ArgumentException("Entry price must be greater than zero.", nameof(entryPrice));

        if (stopLoss <= 0)
            throw new ArgumentException("Stop loss must be greater than zero.", nameof(stopLoss));

        if (takeProfit <= 0)
            throw new ArgumentException("Take profit must be greater than zero.", nameof(takeProfit));

        if (riskReward <= 0)
            throw new ArgumentException("Risk reward must be greater than zero.", nameof(riskReward));

        if (string.IsNullOrWhiteSpace(reasoning))
            throw new ArgumentException("Reasoning is required.", nameof(reasoning));

        // Validate trading direction logic invariants 
        if (direction == SignalDirection.Buy)
        {
            if (stopLoss >= entryPrice)
                throw new ArgumentException("For a Buy signal, Stop Loss must be below Entry Price.", nameof(stopLoss));
            if (takeProfit <= entryPrice)
                throw new ArgumentException("For a Buy signal, Take Profit must be above Entry Price.", nameof(takeProfit));
        }
        else if (direction == SignalDirection.Sell)
        {
            if (stopLoss <= entryPrice)
                throw new ArgumentException("For a Sell signal, Stop Loss must be above Entry Price.", nameof(stopLoss));
            if (takeProfit >= entryPrice)
                throw new ArgumentException("For a Sell signal, Take Profit must be below Entry Price.", nameof(takeProfit));
        }

        Id = Guid.NewGuid();
        UserId = userId;
        ForexPairId = forexPairId;
        CreatedAt = createdAt ?? DateTimeOffset.UtcNow;
        Direction = direction;
        Confidence = confidence;
        EntryPrice = entryPrice;
        StopLoss = stopLoss;
        TakeProfit = takeProfit;
        RiskReward = riskReward;
        Timeframe = timeframe;
        Reasoning = reasoning;
        Status = SignalStatus.Generated;
    }

    public void SubmitForReview()
    {
        if (Status != SignalStatus.Generated)
            throw new InvalidOperationException("Only generated signals can be submitted for review.");

        Status = SignalStatus.UnderReview;
    }

    public void Accept()
    {
        if (Status != SignalStatus.UnderReview)
            throw new InvalidOperationException("Only signals under review can be accepted.");

        Status = SignalStatus.Accepted;
    }

    public void Reject()
    {
        if (Status != SignalStatus.UnderReview)
            throw new InvalidOperationException("Only signals under review can be rejected.");

        Status = SignalStatus.Rejected;
    }

}
