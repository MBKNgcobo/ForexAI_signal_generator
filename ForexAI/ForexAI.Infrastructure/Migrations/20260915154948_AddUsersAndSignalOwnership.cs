using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace ForexAI.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class AddUsersAndSignalOwnership : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<Guid>(
                name: "UserId",
                table: "trading_signals",
                type: "uuid",
                nullable: false,
                defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

            migrationBuilder.CreateTable(
                name: "users",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    Email = table.Column<string>(type: "character varying(320)", maxLength: 320, nullable: false),
                    DisplayName = table.Column<string>(type: "character varying(150)", maxLength: 150, nullable: false),
                    CreatedAt = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_users", x => x.Id);
                });
            migrationBuilder.InsertData(
                table: "users",
                columns: new[] { "Id", "Email", "DisplayName", "CreatedAt" },
                values: new object[]
                {
                    Guid.Parse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                    "dev@forexai.local",
                    "ForexAI Development User",
                    DateTimeOffset.UtcNow
                });

            migrationBuilder.CreateIndex(
                name: "IX_trading_signals_UserId",
                table: "trading_signals",
                column: "UserId");

            migrationBuilder.CreateIndex(
                name: "IX_users_Email",
                table: "users",
                column: "Email",
                unique: true);

            migrationBuilder.Sql("""
                UPDATE trading_signals
                SET "UserId" = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM users
                    WHERE users."Id" = trading_signals."UserId"
                );
                """);

            migrationBuilder.AddForeignKey(
                name: "FK_trading_signals_users_UserId",
                table: "trading_signals",
                column: "UserId",
                principalTable: "users",
                principalColumn: "Id",
                onDelete: ReferentialAction.Restrict);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_trading_signals_users_UserId",
                table: "trading_signals");

            migrationBuilder.DropTable(
                name: "users");

            migrationBuilder.DropIndex(
                name: "IX_trading_signals_UserId",
                table: "trading_signals");

            migrationBuilder.DropColumn(
                name: "UserId",
                table: "trading_signals");
        }
    }
}
