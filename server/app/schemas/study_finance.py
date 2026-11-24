"""User-entered costs, never inferred from token usage or treated as verified billing."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Amount = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]{0,8})(\.[0-9]{1,6})?$")]
Currency = Literal["CNY", "USD", "EUR"]


def amount_units(value: str) -> int:
    whole, _, fraction = value.partition(".")
    return int(whole) * 1_000_000 + int(fraction.ljust(6, "0"))


def amount_text(units: int) -> str:
    sign = "-" if units < 0 else ""
    whole, fraction = divmod(abs(units), 1_000_000)
    return f"{sign}{whole}.{fraction:06d}"


class FinanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BudgetRequest(FinanceInput):
    expected_revision: int = Field(ge=0, strict=True)
    currency: Currency
    limit: Amount | None
    enforcement_enabled: bool = Field(strict=True)
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def limit_required(self) -> "BudgetRequest":
        if self.enforcement_enabled and self.limit is None:
            raise ValueError("A budget amount is required to enable task limits")
        return self


class ExpenseRequest(FinanceInput):
    request_id: str = Field(min_length=1, max_length=128)
    currency: Currency
    amount: Amount
    incurred_on: date
    source_type: Literal["provider_statement", "payment_receipt", "manual_allocation"]
    source_reference: str = Field(min_length=1, max_length=200)
    scope_description: str = Field(min_length=1, max_length=2000)


class VoidExpenseRequest(FinanceInput):
    reason: str = Field(min_length=1, max_length=1000)
