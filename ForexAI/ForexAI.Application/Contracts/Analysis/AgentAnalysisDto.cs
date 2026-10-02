namespace ForexAI.Application.Contracts.Analysis;

public sealed record AgentAnalysisDto(
    string Direction,
    decimal Confidence,
    string Summary
);