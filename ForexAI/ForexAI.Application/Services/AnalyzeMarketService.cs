using ForexAI.Application.Contracts.Analysis;
using ForexAI.Application.Interfaces;

namespace ForexAI.Application.Services;

public sealed class AnalyzeMarketService
{
    private readonly IAiAnalysisClient _aiClient;
    private readonly SignalGenerationService _signalGenerationService;
    public AnalyzeMarketService(
    IAiAnalysisClient aiClient,
    SignalGenerationService signalGenerationService)
    {
        _aiClient = aiClient;
        _signalGenerationService = signalGenerationService;
    }

    public async Task<AnalyzeMarketResult> ExecuteAsync(
        AnalyzeMarketRequest request,
        CancellationToken cancellationToken = default)
    {
        if (request.ForexPairId == Guid.Empty)
        {
            throw new ArgumentException(
                "Forex pair ID is required.",
                nameof(request));
        }

        if (string.IsNullOrWhiteSpace(request.Symbol))
        {
            throw new ArgumentException(
                "Symbol is required.",
                nameof(request));
        }

        var aiResult = await _aiClient.AnalyzeAsync(
            request,
            cancellationToken);

        return new AnalyzeMarketResult(
            aiResult.Symbol,
            aiResult.Timeframe,
            aiResult.TechnicalAnalysis,
            aiResult.FundamentalAnalysis,
            aiResult.QuantPrediction,
            aiResult.RiskAssessment,
            aiResult.FinalDecision);
    }
    public async Task<AnalysisWithSignalResult>
    ExecuteWithSignalAsync(
        AnalyzeMarketRequest request,
        CancellationToken cancellationToken = default)
    {
        var aiResult = await _aiClient.AnalyzeAsync(
            request,
            cancellationToken);

        var analysis = new AnalyzeMarketResult(
            aiResult.Symbol,
            aiResult.Timeframe,
            aiResult.TechnicalAnalysis,
            aiResult.FundamentalAnalysis,
            aiResult.QuantPrediction,
            aiResult.RiskAssessment,
            aiResult.FinalDecision);

        if (!aiResult.RiskAssessment.Approved)
        {
            return new AnalysisWithSignalResult(
                analysis,
                null);
        }

        if (aiResult.FinalDecision.Direction is
            "HOLD" or "NO_TRADE")
        {
            return new AnalysisWithSignalResult(
                analysis,
                null);
        }

        var signal =
            await _signalGenerationService.GenerateAsync(
                request,
                aiResult,
                cancellationToken);

        return new AnalysisWithSignalResult(
            analysis,
            SignalGenerationService.ToResult(signal));
    }
}