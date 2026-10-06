using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

#pragma warning disable CA1814 // Prefer jagged arrays over multidimensional

namespace ForexAI.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class SeedForexPairs : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // Idempotent seed: databases that already contain some of these
            // pairs (installed before this migration existed) keep their
            // existing rows - including the original primary keys - while
            // empty databases get the full list. ON CONFLICT DO NOTHING
            // without a target covers both the primary key and the unique
            // index on "Symbol". A plain InsertData here made every
            // already-installed database fail with 23505 on first boot.
            migrationBuilder.Sql("""
                INSERT INTO forex_pairs ("Id", "BaseCurrency", "IsActive", "QuoteCurrency", "Symbol")
                VALUES
                    ('a1b2c3d4-0001-4000-8000-000000000001', 'AUD', TRUE, 'USD', 'AUDUSD'),
                    ('a1b2c3d4-0001-4000-8000-000000000002', 'AUD', TRUE, 'JPY', 'AUDJPY'),
                    ('a1b2c3d4-0001-4000-8000-000000000003', 'EUR', TRUE, 'GBP', 'EURGBP'),
                    ('a1b2c3d4-0001-4000-8000-000000000004', 'EUR', TRUE, 'JPY', 'EURJPY'),
                    ('a1b2c3d4-0001-4000-8000-000000000005', 'EUR', TRUE, 'USD', 'EURUSD'),
                    ('a1b2c3d4-0001-4000-8000-000000000006', 'EUR', TRUE, 'ZAR', 'EURZAR'),
                    ('a1b2c3d4-0001-4000-8000-000000000007', 'GBP', TRUE, 'JPY', 'GBPJPY'),
                    ('a1b2c3d4-0001-4000-8000-000000000008', 'GBP', TRUE, 'USD', 'GBPUSD'),
                    ('a1b2c3d4-0001-4000-8000-000000000009', 'NZD', TRUE, 'USD', 'NZDUSD'),
                    ('a1b2c3d4-0001-4000-8000-00000000000a', 'USD', TRUE, 'CAD', 'USDCAD'),
                    ('a1b2c3d4-0001-4000-8000-00000000000b', 'USD', TRUE, 'CHF', 'USDCHF'),
                    ('a1b2c3d4-0001-4000-8000-00000000000c', 'USD', TRUE, 'JPY', 'USDJPY'),
                    ('a1b2c3d4-0001-4000-8000-00000000000d', 'USD', TRUE, 'ZAR', 'USDZAR'),
                    ('a1b2c3d4-0001-4000-8000-00000000000e', 'EUR', TRUE, 'CHF', 'EURCHF')
                ON CONFLICT DO NOTHING;
                """);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-000000000001"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-000000000002"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-000000000003"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-000000000004"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-000000000005"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-000000000006"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-000000000007"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-000000000008"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-000000000009"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-00000000000a"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-00000000000b"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-00000000000c"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-00000000000d"));

            migrationBuilder.DeleteData(
                table: "forex_pairs",
                keyColumn: "Id",
                keyValue: new Guid("a1b2c3d4-0001-4000-8000-00000000000e"));
        }
    }
}
