using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

using ForexAI.Application.Contracts.Analysis;

namespace ForexAI.Application.Interfaces;

public interface IAiAnalysisClient
{
    Task<AiAnalysisResponse> AnalyzeAsync(
        AnalyzeMarketRequest request,
        CancellationToken cancellationToken = default);
}
