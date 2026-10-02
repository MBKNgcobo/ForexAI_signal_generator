class LLMUnavailableError(RuntimeError):
    """Raised when the LLM provider cannot serve a request after retries.

    Subclasses RuntimeError so existing callers and tests that expect a
    RuntimeError keep working, while the API layer can map it to a 503
    instead of leaking a bare 500 to the client.
    """
