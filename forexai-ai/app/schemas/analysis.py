from pydantic import BaseModel, Field, field_validator

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
