using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using ForexAI.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace ForexAI.Infrastructure.Persistence.Configurations;

public class TradingSignalConfiguration
    : IEntityTypeConfiguration<TradingSignal>
{
    public void Configure(
        EntityTypeBuilder<TradingSignal> builder)
    {
        builder.ToTable("trading_signals");

        builder.HasKey(x => x.Id);

        builder.Property(x => x.Confidence)
            .HasPrecision(5, 4)
            .IsRequired();

        builder.Property(x => x.EntryPrice)
            .HasPrecision(18, 8)
            .IsRequired();

        builder.Property(x => x.StopLoss)
            .HasPrecision(18, 8)
            .IsRequired();

        builder.Property(x => x.TakeProfit)
            .HasPrecision(18, 8)
            .IsRequired();

        builder.Property(x => x.RiskReward)
            .HasPrecision(10, 4)
            .IsRequired();

        builder.Property(x => x.Reasoning)
            .HasMaxLength(5000)
            .IsRequired();

        builder.Property(x => x.Direction)
            .HasConversion<string>()
            .HasMaxLength(20)
            .IsRequired();

        builder.Property(x => x.Status)
            .HasConversion<string>()
            .HasMaxLength(20)
            .IsRequired();

        builder.Property(x => x.Timeframe)
            .HasConversion<string>()
            .HasMaxLength(20)
            .IsRequired();

        builder.HasIndex(x => new
        {
            x.ForexPairId,
            x.CreatedAt
        });

        builder.HasIndex(x => x.UserId);

        builder.HasOne<User>()
            .WithMany()
            .HasForeignKey(x => x.UserId)
            .OnDelete(DeleteBehavior.Restrict);
    }
}