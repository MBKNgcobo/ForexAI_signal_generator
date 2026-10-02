using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace ForexAI.Domain.Enums;

public enum SignalStatus
{
    Generated,
    UnderReview,
    Accepted,
    Rejected
}