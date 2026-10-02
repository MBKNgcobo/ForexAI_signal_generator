using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace ForexAI.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class AddSignalAuditEvents : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "signal_audit_events",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    SignalId = table.Column<Guid>(type: "uuid", nullable: false),
                    EventType = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
                    Reason = table.Column<string>(type: "character varying(1000)", maxLength: 1000, nullable: true),
                    CreatedAt = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_signal_audit_events", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_signal_audit_events_CreatedAt",
                table: "signal_audit_events",
                column: "CreatedAt");

            migrationBuilder.CreateIndex(
                name: "IX_signal_audit_events_SignalId",
                table: "signal_audit_events",
                column: "SignalId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "signal_audit_events");
        }
    }
}
