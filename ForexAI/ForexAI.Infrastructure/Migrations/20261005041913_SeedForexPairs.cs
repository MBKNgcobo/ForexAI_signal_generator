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
            migrationBuilder.InsertData(
                table: "forex_pairs",
                columns: new[] { "Id", "BaseCurrency", "IsActive", "QuoteCurrency", "Symbol" },
                values: new object[,]
                {
                    { new Guid("a1b2c3d4-0001-4000-8000-000000000001"), "AUD", true, "USD", "AUDUSD" },
                    { new Guid("a1b2c3d4-0001-4000-8000-000000000002"), "AUD", true, "JPY", "AUDJPY" },
                    { new Guid("a1b2c3d4-0001-4000-8000-000000000003"), "EUR", true, "GBP", "EURGBP" },
                    { new Guid("a1b2c3d4-0001-4000-8000-000000000004"), "EUR", true, "JPY", "EURJPY" },
                    { new Guid("a1b2c3d4-0001-4000-8000-000000000005"), "EUR", true, "USD", "EURUSD" },
                    { new Guid("a1b2c3d4-0001-4000-8000-000000000006"), "EUR", true, "ZAR", "EURZAR" },
                    { new Guid("a1b2c3d4-0001-4000-8000-000000000007"), "GBP", true, "JPY", "GBPJPY" },
                    { new Guid("a1b2c3d4-0001-4000-8000-000000000008"), "GBP", true, "USD", "GBPUSD" },
                    { new Guid("a1b2c3d4-0001-4000-8000-000000000009"), "NZD", true, "USD", "NZDUSD" },
                    { new Guid("a1b2c3d4-0001-4000-8000-00000000000a"), "USD", true, "CAD", "USDCAD" },
                    { new Guid("a1b2c3d4-0001-4000-8000-00000000000b"), "USD", true, "CHF", "USDCHF" },
                    { new Guid("a1b2c3d4-0001-4000-8000-00000000000c"), "USD", true, "JPY", "USDJPY" },
                    { new Guid("a1b2c3d4-0001-4000-8000-00000000000d"), "USD", true, "ZAR", "USDZAR" },
                    { new Guid("a1b2c3d4-0001-4000-8000-00000000000e"), "EUR", true, "CHF", "EURCHF" }
                });
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
