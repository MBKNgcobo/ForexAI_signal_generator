using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using ForexAI.Domain.Enums;

namespace ForexAI.Application.Contracts.Analysis;

public sealed record SignalResult(
    Guid SignalId,
    SignalDirection Direction,
    decimal Confidence,
    decimal EntryPrice,
    decimal StopLoss,
    decimal TakeProfit,
    decimal RiskReward,
    Timeframe Timeframe,
    SignalStatus Status,
    string Reasoning
);
