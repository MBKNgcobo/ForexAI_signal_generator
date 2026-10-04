from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class EconomicObservation:
    source: str
    country_code: str | None
    currency: str
    indicator_code: str
    indicator_name: str
    period: str
    observation_date: date | None
    value: float | None
    unit: str | None
    content: str
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def record_id(self) -> str:
        country = self.country_code or "GLOBAL"

        return (
            f"{self.source}:"
            f"{country}:"
            f"{self.indicator_code}:"
            f"{self.period}"
        )