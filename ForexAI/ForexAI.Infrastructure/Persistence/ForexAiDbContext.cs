using ForexAI.Domain.Entities;
using ForexAI.Infrastructure.Identity;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace ForexAI.Infrastructure.Persistence;

public class ForexAiDbContext : IdentityDbContext<ApplicationUser, IdentityRole<Guid>, Guid>
{
    public ForexAiDbContext(
        DbContextOptions<ForexAiDbContext> options)
        : base(options)
    {
    }

    public DbSet<ForexPair> ForexPairs => Set<ForexPair>();

    public DbSet<MarketCandle> MarketCandles => Set<MarketCandle>();

    public DbSet<MarketAnalysis> MarketAnalyses => Set<MarketAnalysis>();

    public DbSet<TradingSignal> TradingSignals => Set<TradingSignal>();

    public DbSet<SignalAuditEvent> SignalAuditEvents => Set<SignalAuditEvent>();

#pragma warning disable CS0114 // Member hides inherited member; missing override keyword
    public DbSet<User> Users => Set<User>();
#pragma warning restore CS0114 // Member hides inherited member; missing override keyword

    protected override void OnModelCreating(
        ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        modelBuilder.Entity<ForexPair>()
            .ToTable("forex_pairs");

        modelBuilder.Entity<MarketCandle>()
            .ToTable("market_candles");

        modelBuilder.Entity<MarketAnalysis>()
            .ToTable("market_analyses");

        modelBuilder.Entity<TradingSignal>()
            .ToTable("trading_signals");

        modelBuilder.ApplyConfigurationsFromAssembly(
            typeof(ForexAiDbContext).Assembly);
    }
}
