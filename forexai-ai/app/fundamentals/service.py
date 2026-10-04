import logging
import os
from datetime import date

from app.fundamentals.clients.business_quant_client import (
    BusinessQuantClient,
)
from app.fundamentals.clients.sotw_client import (
    SOTWClient,
)
from app.fundamentals.clients.world_bank_client import (
    WorldBankClient,
)
from app.fundamentals.currency_map import (
    country_for_currency,
    split_forex_symbol,
)
from app.fundamentals.models import (
    EconomicObservation,
)
from app.fundamentals.normalization import (
    normalize_business_quant,
    normalize_world_bank,
)
from app.fundamentals.rag_store import (
    FundamentalRAGStore,
)


logger = logging.getLogger(__name__)


WORLD_BANK_INDICATORS = {
    "NY.GDP.MKTP.KD.ZG": (
        "GDP growth",
        "%",
    ),
    "FP.CPI.TOTL.ZG": (
        "Inflation, consumer prices",
        "%",
    ),
    "SL.UEM.TOTL.ZS": (
        "Unemployment",
        "%",
    ),
    "BN.CAB.XOKA.GD.ZS": (
        "Current account balance",
        "% of GDP",
    ),
}


SOTW_SERIES = {
    "BIS.CBPOL.D": (
        "Central bank policy rate",
        "%",
    ),
    "IMF.CPI.YOY.M": (
        "Consumer price inflation",
        "% y/y",
    ),
}


BUSINESS_QUANT_CODES = [
    "USCPI.YOY",
    "USUNEMP",
    "USGDP.QOQ",
    "USPAYROLL",
    "USFFR",
]


class FundamentalRAGService:
    def __init__(self) -> None:
        self.store = FundamentalRAGStore()

        self.sotw = SOTWClient(
            api_key=os.getenv(
                "SOTW_API_KEY"
            )
        )

        self.world_bank = WorldBankClient()

        self.business_quant = None

        business_quant_key = os.getenv(
            "BUSINESS_QUANT_API_KEY"
        )

        if business_quant_key:
            self.business_quant = (
                BusinessQuantClient(
                    api_key=business_quant_key
                )
            )

        self.store.initialize()

    async def _refresh_world_bank(
        self,
        currency: str,
    ) -> None:
        country = country_for_currency(
            currency
        )

        scope = f"WORLD_BANK:{country}"

        if self.store.is_fresh(
            scope,
            max_age_hours=24,
        ):
            return

        refresh_succeeded = True

        for (
            indicator_code,
            (
                indicator_name,
                unit,
            ),
        ) in WORLD_BANK_INDICATORS.items():

            try:
                payload = (
                    await self.world_bank
                    .get_indicator(
                        country=country,
                        indicator=indicator_code,
                    )
                )

                observations = (
                    normalize_world_bank(
                        payload=payload,
                        country=country,
                        currency=currency,
                        indicator_code=indicator_code,
                        indicator_name=indicator_name,
                        unit=unit,
                    )
                )

                self.store.upsert_documents(
                    observations
                )

            except Exception as exc:
                refresh_succeeded = False

                logger.warning(
                    "World Bank indicator refresh failed: "
                    "%s / %s: %s",
                    country,
                    indicator_code,
                    exc,
                )

        if refresh_succeeded:
            self.store.mark_fresh(scope)

    async def _refresh_sotw(
        self,
        currency: str,
    ) -> None:
        country = country_for_currency(
            currency
        )

        scope = f"SOTW:{country}"

        if self.store.is_fresh(
            scope,
            max_age_hours=6,
        ):
            return

        refresh_succeeded = True

        for (
            series_id,
            (
                indicator_name,
                unit,
            ),
        ) in SOTW_SERIES.items():

            try:
                payload = (
                    await self.sotw.get_series(
                        series_id=series_id,
                        country=country,
                        from_date=date(
                            2025,
                            1,
                            1,
                        ),
                    )
                )

                series_data = payload.get(
                    "data",
                    [],
                )

                observations: list[
                    EconomicObservation
                ] = []

                for row in series_data:
                    value = row.get("value")
                    period = row.get("period")

                    if (
                        value is None
                        or period is None
                    ):
                        continue

                    try:
                        observation_date = (
                            date.fromisoformat(
                                period[:10]
                            )
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        observation_date = None

                    observations.append(
                        EconomicObservation(
                            source="SOTW",
                            country_code=country,
                            currency=currency,
                            indicator_code=series_id,
                            indicator_name=indicator_name,
                            period=period,
                            observation_date=observation_date,
                            value=float(value),
                            unit=unit,
                            content=(
                                "Source: Statistics of the World. "
                                f"Country: {country}. "
                                f"Currency: {currency}. "
                                f"Indicator: {indicator_name}. "
                                f"Period: {period}. "
                                f"Value: {value} {unit}."
                            ),
                            metadata={
                                "source": (
                                    "Statistics of the World"
                                ),
                                "series_id": series_id,
                                "license": (
                                    payload
                                    .get("series", {})
                                    .get("licence")
                                ),
                            },
                        )
                    )

                self.store.upsert_documents(
                    observations
                )

            except Exception as exc:
                refresh_succeeded = False

                logger.warning(
                    "SOTW series refresh failed: "
                    "%s / %s: %s",
                    country,
                    series_id,
                    exc,
                )

        if refresh_succeeded:
            self.store.mark_fresh(scope)

    async def _refresh_business_quant(
        self,
    ) -> None:
        if not self.business_quant:
            return

        scope = "BUSINESS_QUANT:USA"

        if self.store.is_fresh(
            scope,
            max_age_hours=12,
        ):
            return

        try:
            payload = (
                await self.business_quant
                .get_economic_data(
                    codes=BUSINESS_QUANT_CODES,
                    period="5y",
                )
            )

            observations = (
                normalize_business_quant(
                    payload
                )
            )

            self.store.upsert_documents(
                observations
            )

            self.store.mark_fresh(
                scope
            )

        except Exception as exc:
            logger.warning(
                "Business Quant refresh failed: %s",
                exc,
            )

    async def retrieve(
        self,
        symbol: str,
        limit: int = 16,
    ) -> list[dict]:
        base_currency, quote_currency = (
            split_forex_symbol(symbol)
        )

        currencies = [
            base_currency,
            quote_currency,
        ]

        # --------------------------------------------------
        # WORLD BANK
        # --------------------------------------------------
        #
        # World Bank is supplemental evidence.
        # If one country or indicator fails, continue
        # using the existing database evidence.
        #
        for currency in currencies:
            try:
                await self._refresh_world_bank(
                    currency
                )

            except Exception as exc:
                logger.warning(
                    "World Bank refresh failed for %s: %s",
                    currency,
                    exc,
                )

        # --------------------------------------------------
        # STATISTICS OF THE WORLD
        # --------------------------------------------------
        #
        # SOTW provides high-frequency central-bank
        # policy-rate and inflation data.
        #
        for currency in currencies:
            try:
                await self._refresh_sotw(
                    currency
                )

            except Exception as exc:
                logger.warning(
                    "SOTW refresh failed for %s: %s",
                    currency,
                    exc,
                )

        # --------------------------------------------------
        # BUSINESS QUANT
        # --------------------------------------------------
        #
        # Business Quant currently provides USD
        # economic indicators.
        #
        if "USD" in currencies:
            try:
                await self._refresh_business_quant()

            except Exception as exc:
                logger.warning(
                    "Business Quant refresh failed: %s",
                    exc,
                )

        # --------------------------------------------------
        # FUNDAMENTAL RETRIEVAL QUERY
        # --------------------------------------------------
        #
        # rag_store.py converts this to OR-based search.
        #
        query = (
            "GDP growth "
            "inflation "
            "unemployment "
            "policy rate "
            "interest rate "
            "payroll "
            "current account"
        )

        return self.store.retrieve(
            currencies=currencies,
            query=query,
            limit=limit,
        )