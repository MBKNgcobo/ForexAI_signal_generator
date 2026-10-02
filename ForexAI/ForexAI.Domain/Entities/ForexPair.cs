using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace ForexAI.Domain.Entities;

public class ForexPair
{
    public Guid Id { get; private set; }

    public string Symbol { get; private set; }

    public string BaseCurrency { get; private set; }

    public string QuoteCurrency { get; private set; }

    public bool IsActive { get; private set; }

    private ForexPair()
    {
        // Required by some persistence frameworks later.
        Symbol = string.Empty;
        BaseCurrency = string.Empty;
        QuoteCurrency = string.Empty;
    }

    public ForexPair(
        string symbol,
        string baseCurrency,
        string quoteCurrency)
    {
        if (string.IsNullOrWhiteSpace(symbol))
            throw new ArgumentException(
                "Symbol is required.",
                nameof(symbol));

        if (string.IsNullOrWhiteSpace(baseCurrency))
            throw new ArgumentException(
                "Base currency is required.",
                nameof(baseCurrency));

        if (string.IsNullOrWhiteSpace(quoteCurrency))
            throw new ArgumentException(
                "Quote currency is required.",
                nameof(quoteCurrency));

        Id = Guid.NewGuid();
        Symbol = symbol.ToUpperInvariant();
        BaseCurrency = baseCurrency.ToUpperInvariant();
        QuoteCurrency = quoteCurrency.ToUpperInvariant();
        IsActive = true;
    }

    public void Deactivate()
    {
        IsActive = false;
    }

    public void Activate()
    {
        IsActive = true;
    }
}
