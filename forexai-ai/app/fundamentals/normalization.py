from datetime import date

from app.fundamentals.models import (
    EconomicObservation,
)


def normalize_world_bank(
    payload: dict,
    country: str,
    currency: str,
    indicator_code: str,
    indicator_name: str,
    unit: str,
) -> list[EconomicObservation]:
    observations: list[EconomicObservation] = []

    for row in payload.get("data", []):
        value = row.get("value")

        if value is None:
            continue

        year = row.get("date")

        try:
            observation_date = date(
                int(year),
                12,
                31,
            )
        except (
            TypeError,
            ValueError,
        ):
            observation_date = None

        content = (
            f"Source: World Bank. "
            f"Country: {country}. "
            f"Currency: {currency}. "
            f"Indicator: {indicator_name}. "
            f"Period: {year}. "
            f"Value: {value} {unit}."
        )

        observations.append(
            EconomicObservation(
                source="WORLD_BANK",
                country_code=country,
                currency=currency,
                indicator_code=indicator_code,
                indicator_name=indicator_name,
                period=str(year),
                observation_date=observation_date,
                value=float(value),
                unit=unit,
                content=content,
                metadata={
                    "source_url": (
                        "https://api.worldbank.org/v2"
                    ),
                    "frequency": "annual",
                },
            )
        )

    return observations


def normalize_business_quant(
    payload: dict,
) -> list[EconomicObservation]:
    metadata_by_code = {
        row.get("code"): row
        for row in payload.get("metadata", [])
    }

    observations: list[EconomicObservation] = []

    for row in payload.get("data", []):
        code = row.get("code")
        value = row.get("value")
        raw_date = row.get("date")

        if (
            code is None
            or value is None
            or raw_date is None
        ):
            continue

        descriptor = metadata_by_code.get(
            code,
            {},
        )

        indicator_name = descriptor.get(
            "name",
            code,
        )

        unit = descriptor.get(
            "display_unit"
        )

        try:
            observation_date = date.fromisoformat(
                raw_date
            )
        except (
            TypeError,
            ValueError,
        ):
            observation_date = None

        content = (
            f"Source: Business Quant. "
            f"Country: United States. "
            f"Currency: USD. "
            f"Indicator: {indicator_name}. "
            f"Code: {code}. "
            f"Date: {raw_date}. "
            f"Value: {value} "
            f"{unit or ''}."
        )

        observations.append(
            EconomicObservation(
                source="BUSINESS_QUANT",
                country_code="USA",
                currency="USD",
                indicator_code=code,
                indicator_name=indicator_name,
                period=raw_date,
                observation_date=observation_date,
                value=float(value),
                unit=unit,
                content=content,
                metadata={
                    "category": descriptor.get(
                        "category"
                    ),
                    "frequency": descriptor.get(
                        "freq_long"
                    ),
                    "direction": descriptor.get(
                        "direction"
                    ),
                },
            )
        )

    return observations