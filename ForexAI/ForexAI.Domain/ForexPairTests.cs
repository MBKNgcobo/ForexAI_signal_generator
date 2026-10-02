using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Xunit;
using ForexAI.Domain.Entities;

namespace ForexAI.Tests.Domain;

public class ForexPairTests
{
    /*
     We are testing the data validation and behavior of the ForexPair entity.
     The tests ensure that the entity is created correctly, handles invalid input, and manages its active state as expected.
     */
    [Fact]
    public void ValidForexPair_ShouldBeCreated()
    {
        // Arrange & Act
        var pair = new ForexPair(
            "EURUSD",
            "EUR",
            "USD");

        // Assert
        Assert.Equal("EURUSD", pair.Symbol);
        Assert.Equal("EUR", pair.BaseCurrency);
        Assert.Equal("USD", pair.QuoteCurrency);
        Assert.True(pair.IsActive);
    }

    [Fact]
    public void Symbol_ShouldBeStoredAsUppercase()
    {
        // Arrange & Act
        var pair = new ForexPair(
            "eurusd",
            "eur",
            "usd");

        // Assert
        Assert.Equal("EURUSD", pair.Symbol);
        Assert.Equal("EUR", pair.BaseCurrency);
        Assert.Equal("USD", pair.QuoteCurrency);
    }

    [Fact]
    public void EmptySymbol_ShouldThrowException()
    {
        Assert.Throws<ArgumentException>(() =>
            new ForexPair("", "EUR", "USD"));
    }

    [Fact]
    public void ForexPair_ShouldBeDeactivated()
    {
        // Arrange
        var pair = new ForexPair(
            "EURUSD",
            "EUR",
            "USD");

        // Act
        pair.Deactivate();

        // Assert
        Assert.False(pair.IsActive);
    }

    [Fact]
    public void ForexPair_ShouldBeReactivated()
    {
        // Arrange
        var pair = new ForexPair(
            "EURUSD",
            "EUR",
            "USD");

        pair.Deactivate();

        // Act
        pair.Activate();

        // Assert
        Assert.True(pair.IsActive);
    }
}
