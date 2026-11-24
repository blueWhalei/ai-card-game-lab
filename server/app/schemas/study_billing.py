"""Supplier project scope is independent of manual research expense attribution."""

from datetime import UTC, date, datetime

from pydantic import Field, model_validator

from app.schemas.study_finance import Amount, FinanceInput


class BillingConfigRequest(FinanceInput):
    expected_revision: int = Field(ge=0, strict=True)
    project_id: str = Field(pattern=r"^proj_[a-zA-Z0-9_-]{1,120}$")
    start_date: date
    limit: Amount | None
    enforcement_enabled: bool = Field(strict=True)
    max_age_hours: int = Field(ge=1, le=24, strict=True)
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def valid_scope(self) -> "BillingConfigRequest":
        days = (datetime.now(UTC).date() - self.start_date).days
        if days < 0 or (self.enforcement_enabled and days > 365):
            raise ValueError("Start date must be within the preceding 365 UTC days")
        if self.enforcement_enabled and self.limit is None:
            raise ValueError("An enabled supplier limit requires an amount")
        return self


class BillingSyncRequest(FinanceInput):
    expected_revision: int = Field(ge=1, strict=True)


class BillingScheduleRequest(FinanceInput):
    expected_revision: int = Field(ge=0, strict=True)
    expected_config_revision: int = Field(ge=1, strict=True)
    enabled: bool = Field(strict=True)
    interval_minutes: int = Field(ge=15, le=720, strict=True)
    reason: str = Field(min_length=1, max_length=1000)
