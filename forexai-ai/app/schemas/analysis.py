from pydantic import BaseModel, Field, field_validator

from app.schemas.ai_response import AiAnalysisResponse
from app.schemas.market import Timeframe


class AnalyzeMarketRequest(BaseModel):

    #: Reserved by the existing (C#) client contract. The AI service does not
    #: consume it yet - the graph works purely from ``symbol``/``timeframe``.
    #: Marked deprecated so it can be removed in a future major version
    #: without silently confusing integrators.
    forex_pair_id: str = Field(
        ...,
        deprecated=True,
        description=(
            "Accepted for backwards compatibility but currently unused by "
            "the analysis graph."
        ),
    )

    symbol: str
    timeframe: str

    #: Optional push delivery (P4). Set by the C# gateway so a hosted
    #: analysis can reach a local execution bridge without the caller
    #: polling. Ignored on batch *items* - the batch level
    #: ``webhook_url`` is the one that fires.
    webhook_url: str | None = Field(
        default=None,
        description="Optional HTTP(S) URL to POST the response to.",
    )

    @field_validator("symbol")
    @classmethod
    def _normalise_symbol(cls, value: str) -> str:
        """Trim, uppercase and enforce a six-letter currency pair."""

        symbol = value.strip().upper()

        if len(symbol) != 6 or not symbol.isascii() or not symbol.isalpha():
            raise ValueError(
                "symbol must be a six-letter currency pair such as EURUSD"
            )

        return symbol

    @field_validator("timeframe")
    @classmethod
    def _validate_timeframe(cls, value: str) -> str:
        """Reject unknown timeframes at the boundary (HTTP 422).

        Previously an unknown value only failed later inside the provider,
        which surfaced as a 500 after paid LLM work had already been done.
        """

        return Timeframe(value.strip()).value


class BatchAnalyzeMarketRequest(BaseModel):
    """One call, N pairs: the dashboard watchlist use-case.

    ``webhook_url`` is optional push delivery (P4): after the batch is
    mapped, the response is POSTed to the URL. Failures are logged, never
    raised; the allowlist in ``app/config.py`` guards against SSRF.
    """

    requests: list[AnalyzeMarketRequest] = Field(
        min_length=1,
        max_length=50,
        description="Pairs to analyse; hard cap re-checked in the route.",
    )

    webhook_url: str | None = Field(
        default=None,
        description="Optional HTTPS URL to POST the batch response to.",
    )


class BatchItemError(BaseModel):
    index: int
    status: int
    detail: str


class BatchAnalysisResponse(BaseModel):
    """Per-item results; one bad pair never fails the whole batch."""

    results: list[AiAnalysisResponse] = Field(default_factory=list)
    errors: list[BatchItemError] = Field(default_factory=list)
