using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace ForexAI.Application.Contracts.Signals;

public sealed record GenerateSignalRequest(
    Guid AnalysisId
);
