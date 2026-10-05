using System.Net.Http;

namespace ForexAI.Infrastructure.ExternalServices;

/// <summary>
/// Shared retry policy for the gateway's calls to the hosted Python AI
/// service.
///
/// Render's free tier spins a web service down after ~15 min idle and
/// cold-starts it in ~50 s. While an instance boots, the edge can answer a
/// 5xx before the request reaches the app, and a single provider 5xx (LLM
/// rate limit, upstream outage) is often transient. Without a bounded retry a
/// client's first request after a quiet period fails - which is exactly how
/// "analysis failed" surfaces on the dashboard.
///
/// The retry lives in the *client* methods (each attempt issues a fresh
/// HttpRequestMessage) rather than in a DelegatingHandler, because an
/// HttpRequestMessage can only be sent once; reusing it across retries throws
/// InvalidOperationException (confirmed on the current runtime: "The request
/// message was already sent."). Only a 5xx response or a connection error is
/// retried; a 4xx, a request timeout and caller cancellation are never
/// retried.
/// </summary>
internal static class GatewayRetry
{
    internal const int MaxAttempts = 3;

    internal static TimeSpan Backoff(int attempt)
        => TimeSpan.FromMilliseconds(500 * (1 << (attempt - 1)));

    internal static bool IsRetryable(Exception ex)
        => ex switch
        {
            // A caller-supplied operation is cancelled when the browser goes
            // away; that is not a reason to retry.
            OperationCanceledException => false,
            // Connection / DNS / TLS failures carry no HTTP status code.
            HttpRequestException hre => hre.StatusCode is null,
            _ => false,
        };
}
