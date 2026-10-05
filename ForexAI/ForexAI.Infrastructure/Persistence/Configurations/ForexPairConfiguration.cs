using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using ForexAI.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace ForexAI.Infrastructure.Persistence.Configurations;

public class ForexPairConfiguration
    : IEntityTypeConfiguration<ForexPair>
{
    public void Configure(
        EntityTypeBuilder<ForexPair> builder)
    {
        builder.ToTable("forex_pairs");

        builder.HasKey(x => x.Id);

        builder.Property(x => x.Symbol)
            .HasMaxLength(20)
            .IsRequired();

        builder.Property(x => x.BaseCurrency)
            .HasMaxLength(3)
            .IsRequired();

        builder.Property(x => x.QuoteCurrency)
            .HasMaxLength(3)
            .IsRequired();

        builder.Property(x => x.IsActive)
            .IsRequired();

        builder.HasIndex(x => x.Symbol)
            .IsUnique();

        SeedPairs(builder);
    }

    /// <summary>
    /// The tradable pairs offered by the dashboard's pair picker.
    /// </summary>
    /// <remarks>
    /// Migrations build the schema but never inserted data, so
    /// <c>GET /api/ForexPairs</c> answered 200 with an empty list and the
    /// picker silently had nothing to show. Seeding here makes the list
    /// version-controlled and idempotent: EF replays these rows in Up and
    /// removes them in Down.
    ///
    /// The values are written as anonymous types because
    /// <see cref="ForexPair"/> exposes private setters. Constructing it
    /// directly is not an option either - its constructor calls
    /// Guid.NewGuid(), which would produce a fresh key on every model
    /// comparison and ask for a new migration every time. Fixed Ids keep
    /// the snapshot stable.
    ///
    /// Every symbol here must also be accepted by the Python service's
    /// currency map (forexai-ai/app/fundamentals/currency_map.py): an
    /// unknown currency is rejected with a 400 at the analysis endpoint,
    /// so a pair listed here but missing there would fail on selection.
    /// </remarks>
    private static void SeedPairs(
        EntityTypeBuilder<ForexPair> builder)
    {
        builder.HasData(
            Seed("a1b2c3d4-0001-4000-8000-000000000001", "AUDUSD", "AUD", "USD"),
            Seed("a1b2c3d4-0001-4000-8000-000000000002", "AUDJPY", "AUD", "JPY"),
            Seed("a1b2c3d4-0001-4000-8000-000000000003", "EURGBP", "EUR", "GBP"),
            Seed("a1b2c3d4-0001-4000-8000-000000000004", "EURJPY", "EUR", "JPY"),
            Seed("a1b2c3d4-0001-4000-8000-000000000005", "EURUSD", "EUR", "USD"),
            Seed("a1b2c3d4-0001-4000-8000-000000000006", "EURZAR", "EUR", "ZAR"),
            Seed("a1b2c3d4-0001-4000-8000-000000000007", "GBPJPY", "GBP", "JPY"),
            Seed("a1b2c3d4-0001-4000-8000-000000000008", "GBPUSD", "GBP", "USD"),
            Seed("a1b2c3d4-0001-4000-8000-000000000009", "NZDUSD", "NZD", "USD"),
            Seed("a1b2c3d4-0001-4000-8000-00000000000a", "USDCAD", "USD", "CAD"),
            Seed("a1b2c3d4-0001-4000-8000-00000000000b", "USDCHF", "USD", "CHF"),
            Seed("a1b2c3d4-0001-4000-8000-00000000000c", "USDJPY", "USD", "JPY"),
            Seed("a1b2c3d4-0001-4000-8000-00000000000d", "USDZAR", "USD", "ZAR"),
            Seed("a1b2c3d4-0001-4000-8000-00000000000e", "EURCHF", "EUR", "CHF")
        );
    }

    private static object Seed(
        string id,
        string symbol,
        string baseCurrency,
        string quoteCurrency) =>
        new
        {
            Id = Guid.Parse(id),
            Symbol = symbol,
            BaseCurrency = baseCurrency,
            QuoteCurrency = quoteCurrency,
            IsActive = true
        };
}
