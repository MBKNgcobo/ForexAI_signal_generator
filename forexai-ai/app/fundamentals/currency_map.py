CURRENCY_TO_COUNTRY = {
    "USD": "USA",
    "EUR": "EMU",
    "GBP": "GBR",
    "JPY": "JPN",
    "CHF": "CHE",
    "CAD": "CAN",
    "AUD": "AUS",
    "NZD": "NZL",
    "ZAR": "ZAF",
}


def split_forex_symbol(
    symbol: str,
) -> tuple[str, str]:
    normalized = symbol.upper().strip()

    if len(normalized) != 6:
        raise ValueError(
            f"Unsupported forex symbol: {symbol}"
        )

    base = normalized[:3]
    quote = normalized[3:]

    if (
        base not in CURRENCY_TO_COUNTRY
        or quote not in CURRENCY_TO_COUNTRY
    ):
        raise ValueError(
            f"Unsupported currency pair: {symbol}"
        )

    return base, quote


def country_for_currency(
    currency: str,
) -> str:
    try:
        return CURRENCY_TO_COUNTRY[
            currency.upper()
        ]
    except KeyError as exc:
        raise ValueError(
            f"No country mapping for currency: {currency}"
        ) from exc