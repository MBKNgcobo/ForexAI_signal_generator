using System.Net;
using System.Net.Http;

namespace ForexAI.Infrastructure.ExternalServices;

/// <summary>
/// Bounded retry for the gateway's calls to the hosted Python AI service.
///
/// Render's free tier spins a web service down after ~15 min idle and
/// cold-starts it in ~50 s. While an instance boots, Render's edge answers
/// 503 before the request ever reaches the app, and a single provider 5xx
/// (LLM rate limit, upstream outage) is also often transient. Without a
/// retry a client's first request after a quiet period fails immediately,
/// which is exactly how "analysis failed" surfaces on the dashboard.
///
/// This handler retries only a 5xx response or a connection/timeout error,
/// with a short exponential backoff, and gives up after the final attempt.
/// Caller cancellation is never retried. It deliberately does not retry
/// 4xx (a client error will not succeed on a second attempt).
/// </summary>
public sealed class RetryDelegatingHandler : DelegatingHandler
{
    private const int MaxAttempts = 3;
    private static readonly TimeSpan BaseDelay = TimeSpan.FromMilliseconds(500);

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        for (var attempt = 1; ; attempt++)
        {
            HttpResponseMessage response;

            try
            {
                response = await base.SendAsync(request, cancellationToken);
            }
            catch (Exception ex) when (
                attempt < MaxAttempts &&
                !cancellationToken.IsCancellationRequested &&
                IsRetryableException(ex))
            {
                await DelayAsync(attempt, cancellationToken);
                continue;
            }

            if (attempt == MaxAttempts || !IsRetryableStatusCode(response.StatusCode))
            {
                return response;
            }

            response.Dispose();

            await DelayAsync(attempt, cancellationToken);
        }
    }

    private static bool IsRetryableException(Exception ex)
        => ex is HttpRequestException or TaskCanceledException;

    private static bool IsRetryableStatusCode(HttpStatusCode status)
        => (int)status >= 500;

    private static Task DelayAsync(int attempt, CancellationToken cancellationToken)
    {
        var delay = TimeSpan.FromMilliseconds(
            BaseDelay.TotalMilliseconds * (1 << (attempt - 1)));

        return Task.Delay(delay, cancellationToken);
    }
}
