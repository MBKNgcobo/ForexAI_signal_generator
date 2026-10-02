using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace ForexAI.Application.Contracts.Analysis;

public sealed record FinalDecisionDto(
    string Direction,
    decimal Confidence,
    string Reasoning
);