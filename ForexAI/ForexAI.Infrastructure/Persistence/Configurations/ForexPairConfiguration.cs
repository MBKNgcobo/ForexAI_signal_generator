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
    }
}
