using ForexAI.Application.Contracts.Analysis;
using ForexAI.Application.Interfaces;

namespace ForexAI.Api.Services;

public sealed class FakeAiAnalysisClient : IAiAnalysisClient
{
    public Task<AiAnalysisResponse> AnalyzeAsync(
        AnalyzeMarketRequest request,
        CancellationToken cancellationToken = default)
    {
        var response = new AiAnalysisResponse(
            request.Symbol,
            request.Timeframe.ToString(),

            new AgentAnalysisDto(
                Direction: "BUY",
                Confidence: 0.80m,
                Summary: "Technical conditions are bullish."
            ),

            new AgentAnalysisDto(
                Direction: "BUY",
                Confidence: 0.65m,
                Summary: "Fundamental conditions are moderately bullish."
            ),

            new AgentAnalysisDto(
                Direction: "BUY",
                Confidence: 0.75m,
                Summary: "Quantitative model indicates upward movement."
            ),

            new RiskAssessmentDto(
                RiskLevel: "LOW",
                Approved: true,
                Agreement: 1.0m,
                Reason: "All specialist agents are aligned.",
                EntryPrice: 1.1650m,
                StopLoss: 1.1600m,
                TakeProfit: 1.1750m,
                RiskReward: 2.0m
            ),

            new FinalDecisionDto(
                Direction: "BUY",
                Confidence: 0.73m,
                Reasoning: "The specialist agents are aligned and risk is approved."
            )
        );

        return Task.FromResult(response);
    }
}