using ForexAI.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace ForexAI.Infrastructure.Persistence.Configurations;

public sealed class SignalAuditEventConfiguration
    : IEntityTypeConfiguration<SignalAuditEvent>
{
    public void Configure(
        EntityTypeBuilder<SignalAuditEvent> builder)
    {
        builder.ToTable("signal_audit_events");

        builder.HasKey(x => x.Id);

        builder.Property(x => x.EventType)
            .HasMaxLength(100)
            .IsRequired();

        builder.Property(x => x.Reason)
            .HasMaxLength(1000);

        builder.Property(x => x.CreatedAt)
            .IsRequired();

        builder.HasIndex(x => x.SignalId);

        builder.HasIndex(x => x.CreatedAt);
    }
}