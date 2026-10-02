using ForexAI.Application.Contracts.Analysis;
using ForexAI.Application.Interfaces;
using ForexAI.Domain.Entities;
using ForexAI.Domain.Enums;

namespace ForexAI.Application.Services;

public sealed class SignalGenerationService
{
    private readonly ITradingSignalRepository _signalRepository;
    private readonly ICurrentUserService _currentUserService;
    private static readonly Guid GuestUserId = Guid.Parse("00000000-0000-0000-0000-000000000001");
    public SignalGenerationService(
        ITradingSignalRepository signalRepository,
        ICurrentUserService currentUserService)
    {
        _signalRepository = signalRepository;
        _currentUserService = currentUserService;
    }

    public async Task<TradingSignal> GenerateAsync(
        AnalyzeMarketRequest request,
        AiAnalysisResponse aiResult,
        CancellationToken cancellationToken = default)
    {
        var userId = (_currentUserService.IsAuthenticated && _currentUserService.UserId != Guid.Empty)
        ? _currentUserService.UserId
        : GuestUserId;
        // ---------------------------------------------------------
        // 1. Validate authentication
        // ---------------------------------------------------------

        if (!_currentUserService.IsAuthenticated)
        {
            throw new UnauthorizedAccessException(
                "Authentication is required to generate a trading signal.");
        }


        if (userId == Guid.Empty)
        {
            throw new UnauthorizedAccessException(
                "Authenticated user ID is missing.");
        }

        // ---------------------------------------------------------
        // 2. Validate risk approval
        // ---------------------------------------------------------

        if (!aiResult.RiskAssessment.Approved)
        {
            throw new InvalidOperationException(
                "A trading signal cannot be generated because risk assessment rejected the setup.");
        }

        // ---------------------------------------------------------
        // 3. Validate trading levels
        // ---------------------------------------------------------

        if (aiResult.RiskAssessment.EntryPrice is null)
        {
            throw new InvalidOperationException(
                "Entry price is required for signal generation.");
        }

        if (aiResult.RiskAssessment.StopLoss is null)
        {
            throw new InvalidOperationException(
                "Stop loss is required for signal generation.");
        }

        if (aiResult.RiskAssessment.TakeProfit is null)
        {
            throw new InvalidOperationException(
                "Take profit is required for signal generation.");
        }

        if (aiResult.RiskAssessment.RiskReward is null)
        {
            throw new InvalidOperationException(
                "Risk/reward is required for signal generation.");
        }

        // ---------------------------------------------------------
        // 4. Convert AI direction to Domain enum
        // ---------------------------------------------------------

        var direction = ParseDirection(
            aiResult.FinalDecision.Direction);

        if (direction is SignalDirection.Hold
            or SignalDirection.NoTrade)
        {
            throw new InvalidOperationException(
                "A trading signal cannot be generated for HOLD or NO_TRADE.");
        }

        // ---------------------------------------------------------
        // 5. Create the domain TradingSignal
        // ---------------------------------------------------------

        var signal = new TradingSignal(
            userId,
            request.ForexPairId,
            direction,
            aiResult.FinalDecision.Confidence,
            aiResult.RiskAssessment.EntryPrice.Value,
            aiResult.RiskAssessment.StopLoss.Value,
            aiResult.RiskAssessment.TakeProfit.Value,
            aiResult.RiskAssessment.RiskReward.Value,
            request.Timeframe,
            BuildReasoning(aiResult));

        // ---------------------------------------------------------
        // 6. Move signal into review
        // ---------------------------------------------------------

        signal.SubmitForReview();

        // ---------------------------------------------------------
        // 7. Persist signal
        // ---------------------------------------------------------

        await _signalRepository.AddAsync(
            signal,
            cancellationToken);

        await _signalRepository.SaveAsync(
            signal,
            cancellationToken);

        // ---------------------------------------------------------
        // 8. Return generated signal
        // ---------------------------------------------------------

        return signal;
    }

    private static SignalDirection ParseDirection(
        string direction)
    {
        return direction.ToUpperInvariant() switch
        {
            "BUY" => SignalDirection.Buy,
            "SELL" => SignalDirection.Sell,
            "HOLD" => SignalDirection.Hold,
            "NO_TRADE" => SignalDirection.NoTrade,

            _ => throw new InvalidOperationException(
                $"Unsupported final direction: {direction}")
        };
    }

    private static string BuildReasoning(
        AiAnalysisResponse aiResult)
    {
        return
            $"Final decision: {aiResult.FinalDecision.Direction}. " +
            $"Confidence: {aiResult.FinalDecision.Confidence:F2}. " +
            $"Technical: {aiResult.TechnicalAnalysis.Summary}. " +
            $"Fundamental: {aiResult.FundamentalAnalysis.Summary}. " +
            $"Quant: {aiResult.QuantPrediction.Summary}. " +
            $"Risk: {aiResult.RiskAssessment.Reason}";
    }

    public static SignalResult ToResult(
        TradingSignal signal)
    {
        return new SignalResult(
            signal.Id,
            signal.Direction,
            signal.Confidence,
            signal.EntryPrice,
            signal.StopLoss,
            signal.TakeProfit,
            signal.RiskReward,
            signal.Timeframe,
            signal.Status,
            signal.Reasoning);
    }
}