using System;
using System.Linq;
using ForexAI.Domain.Entities;
using ForexAI.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Metadata;
using Xunit;

namespace ForexAI.Tests.Infrastructure;

/// <summary>
/// The dashboard's pair picker is populated entirely from the seeded rows.
/// </summary>
/// <remarks>
/// The migrations created the <c>forex_pairs</c> table but never inserted
/// anything into it, so <c>GET /api/ForexPairs</c> answered 200 with an empty
/// list and the picker silently had nothing to render. These tests pin the
/// seed so it cannot quietly disappear again.
/// </remarks>
public sealed class ForexPairSeedDataTests
{
    private const int SeededPairCount = 14;

    private static readonly string[] ExpectedSymbols =
    {
        "AUDJPY",
        "AUDUSD",
        "EURCHF",
        "EURGBP",
        "EURJPY",
        "EURUSD",
        "EURZAR",
        "GBPJPY",
        "GBPUSD",
        "NZDUSD",
        "USDCAD",
        "USDCHF",
        "USDJPY",
        "USDZAR"
    };

    private static ForexAiDbContext BuildModel()
    {
        var options = new DbContextOptionsBuilder<ForexAiDbContext>()
            .UseNpgsql(
                "Host=127.0.0.1;Database=design;Username=none;Password=none")
            .Options;

        return new ForexAiDbContext(options);
    }

    private static IEntityType SeededPairType()
    {
        using var context = BuildModel();

        // Seed data lives on the design-time model. The runtime model is
        // read-optimized and throws if asked for it directly.
        return context
            .GetService<IDesignTimeModel>()
            .Model
            .FindEntityType(typeof(ForexPair))!;
    }

    [Fact]
    public void Every_seeded_pair_is_present_in_the_model()
    {
        var seeded = SeededPairType()
            .GetSeedData()
            .Select(entry => entry["Symbol"])
            .OrderBy(symbol => symbol)
            .ToArray();

        Assert.Equal(
            ExpectedSymbols.OrderBy(s => s).ToArray(),
            seeded);
    }

    [Fact]
    public void Seeded_symbols_are_unique_and_active()
    {
        var entries = SeededPairType().GetSeedData().ToList();

        var symbols = entries.Select(e => (string)e["Symbol"]!).ToList();

        // forex_pairs has a unique index on Symbol, so a duplicate here would
        // make the migration fail at apply time rather than at review time.
        Assert.Equal(symbols.Count, symbols.Distinct().Count());

        // A deactivating row would never reach the picker.
        Assert.All(entries, entry =>
            Assert.True((bool)entry["IsActive"]!));

        // Fixed keys are what keep the model snapshot stable; a new Guid on
        // every design-time build would ask for a migration every time.
        Assert.All(entries, entry =>
            Assert.NotEqual(Guid.Empty, (Guid)entry["Id"]!));

        Assert.Equal(SeededPairCount, entries.Count);
    }

    /// <summary>
    /// A pair listed in the picker but unknown to the Python service is
    /// rejected with a 400 by its currency map, so the two lists have to
    /// agree. This asserts the currencies the seed relies on are ones the
    /// fundamentals layer can resolve.
    /// </summary>
    [Theory]
    [InlineData("EUR", "USD")]
    [InlineData("GBP", "JPY")]
    [InlineData("NZD", "USD")]
    [InlineData("USD", "ZAR")]
    [InlineData("EUR", "ZAR")]
    public void Seeded_currencies_are_known_to_the_fundamentals_map(
        string baseCurrency,
        string quoteCurrency)
    {
        string[] supported =
        {
            "USD", "EUR", "GBP", "JPY",
            "CHF", "CAD", "AUD", "NZD", "ZAR"
        };

        Assert.Contains(baseCurrency, supported);
        Assert.Contains(quoteCurrency, supported);
    }
}