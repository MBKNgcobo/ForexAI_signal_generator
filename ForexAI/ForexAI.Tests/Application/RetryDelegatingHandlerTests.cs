using System.Net;
using ForexAI.Infrastructure.ExternalServices;
using Xunit;

namespace ForexAI.Tests.Application;

/// <summary>
/// The gateway retry policy. Without it a client's first request after a
/// free-tier idle period fails on the cold-start edge 503; with it the
/// request survives one or two transient 5xx before the failure is reported.
/// 4xx must never be retried (a client error will not succeed on a retry).
/// </summary>
public class RetryDelegatingHandlerTests
{
    private sealed class _FakeHandler : HttpMessageHandler
    {
        public int Calls { get; private set; }

        public Func<int, HttpResponseMessage> Responder { get; set; } =
            _ => new HttpResponseMessage(HttpStatusCode.OK);

        public Func<int, bool> ThrowOnCall { get; set; } =
            _ => false;

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            Calls++;

            if (ThrowOnCall(Calls))
            {
                throw new HttpRequestException("connection failed");
            }

            return Task.FromResult(Responder(Calls));
        }
    }

    private static HttpClient BuildClient(_FakeHandler inner)
    {
        var handler = new RetryDelegatingHandler
        {
            InnerHandler = inner
        };

        return new HttpClient(handler)
        {
            BaseAddress = new Uri("http://python-ai.example")
        };
    }

    [Fact]
    public async Task RetriesA5xxThenSucceeds()
    {
        var inner = new _FakeHandler();
        inner.Responder = call =>
            call == 1
                ? new HttpResponseMessage(HttpStatusCode.ServiceUnavailable)
                : new HttpResponseMessage(HttpStatusCode.OK);

        var client = BuildClient(inner);

        var response = await client.GetAsync("/analysis");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(2, inner.Calls);
    }

    [Fact]
    public async Task ReturnsTheLast5xxAfterMaxAttempts()
    {
        var inner = new _FakeHandler();
        inner.Responder = _ =>
            new HttpResponseMessage(HttpStatusCode.ServiceUnavailable);

        var client = BuildClient(inner);

        var response = await client.GetAsync("/analysis");

        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        Assert.Equal(3, inner.Calls);
    }

    [Fact]
    public async Task DoesNotRetryA4xx()
    {
        var inner = new _FakeHandler();
        inner.Responder = _ =>
            new HttpResponseMessage(HttpStatusCode.BadRequest);

        var client = BuildClient(inner);

        var response = await client.GetAsync("/analysis");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal(1, inner.Calls);
    }

    [Fact]
    public async Task RetriesAConnectionErrorThenSucceeds()
    {
        var inner = new _FakeHandler();
        inner.ThrowOnCall = call => call == 1;

        var client = BuildClient(inner);

        var response = await client.GetAsync("/analysis");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(2, inner.Calls);
    }

    [Fact]
    public async Task PropagatesAConnectionErrorAfterMaxAttempts()
    {
        var inner = new _FakeHandler();
        inner.ThrowOnCall = _ => true;

        var client = BuildClient(inner);

        await Assert.ThrowsAsync<HttpRequestException>(
            () => client.GetAsync("/analysis"));

        Assert.Equal(3, inner.Calls);
    }
}
