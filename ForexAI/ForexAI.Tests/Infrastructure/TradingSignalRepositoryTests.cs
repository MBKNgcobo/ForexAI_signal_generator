using ForexAI.Domain.Entities;
using ForexAI.Domain.Enums;
using ForexAI.Infrastructure.Persistence;
using ForexAI.Infrastructure.Repositories;
using Microsoft.EntityFrameworkCore;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Xunit;

namespace ForexAI.Tests.Infrastructure;

public class TradingSignalRepositoryTests
{
    // No credentials are stored in source control. The repository tests
    // need a running PostgreSQL; point TEST_CONNECTION_STRING at it, e.g.
    //   Host=localhost;Port=5434;Database=forexai_test;Username=postgres;Password=<password>
    private static readonly string ConnectionString =
        Environment.GetEnvironmentVariable("TEST_CONNECTION_STRING")
        ?? "Host=localhost;Port=5434;Database=forexai_test;Username=postgres;Password=";

    [Fact]
    public async Task AddAndRetrieveSignal_ShouldWork()
    {
        // Arrange
        var options = new DbContextOptionsBuilder<ForexAiDbContext>()
            .UseNpgsql(ConnectionString)
            .Options;

        await using var context = new ForexAiDbContext(options);

        await context.Database.EnsureDeletedAsync();
        await context.Database.EnsureCreatedAsync();

        var repository = new TradingSignalRepository(context);

        var signal = new TradingSignal(
            Guid.NewGuid(),
            SignalDirection.Buy,
            0.80m,
            1.1650m,
            1.1600m,
            1.1750m,
            2.0m,
            Timeframe.FourHours,
            "Integration test signal.");

        // Act
        await repository.AddAsync(signal);
        await repository.SaveAsync(signal);

        var result = await repository.GetByIdAsync(signal.Id);

        // Assert
        Assert.NotNull(result);
        Assert.Equal(signal.Id, result.Id);
        Assert.Equal(
            SignalDirection.Buy,
            result.Direction);
        Assert.Equal(
            0.80m,
            result.Confidence);
    }
}
