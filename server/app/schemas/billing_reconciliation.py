"""User-transcribed evidence; neither payment totals nor invoices imply project costs."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.schemas.study_finance import Currency, FinanceInput

SignedCost = Annotated[str, StringConstraints(pattern=r"^-?(0|[1-9][0-9]{0,11})(\.[0-9]{1,18})?$")]
CSV_MAX_BYTES = 512 * 1024
ColumnName = Annotated[str, StringConstraints(min_length=1, max_length=120)]


class ReconciliationCsvFile(FinanceInput):
    content_base64: str = Field(min_length=4, max_length=4 * ((CSV_MAX_BYTES + 2) // 3))


class ReconciliationCsv(ReconciliationCsvFile):
    filename: str = Field(min_length=5, max_length=255, pattern=r"^[^/\\\x00-\x1f]+\.[cC][sS][vV]$")
    amount_column: ColumnName
    date_column: ColumnName
    organization_column: ColumnName | None = None
    project_column: ColumnName | None = None
    currency_column: ColumnName | None = None


class ReconciliationInput(FinanceInput):
    attempt_id: str = Field(min_length=1, max_length=128)
    source_type: Literal[
        "cost_export", "invoice_project_subtotal", "invoice_total", "payment_receipt"
    ]
    source_reference: str = Field(min_length=1, max_length=300)
    organization_id: str = Field(min_length=1, max_length=128)
    project_id: str | None = Field(default=None, min_length=1, max_length=128)
    currency: Currency
    source_amount: SignedCost | None = None
    period_start: date
    period_end: date
    scope_note: str = Field(min_length=1, max_length=2000)
    csv: ReconciliationCsv | None = None

    @model_validator(mode="after")
    def closed_period(self) -> "ReconciliationInput":
        if not 0 < (self.period_end - self.period_start).days <= 366:
            raise ValueError("A positive UTC period of at most 366 days is required")
        if self.period_end > datetime.now(UTC).date():
            raise ValueError("Only completed UTC days can be reconciled")
        if self.csv is None and self.source_amount is None:
            raise ValueError("A manually entered source amount is required")
        if self.csv is not None and (
            self.source_type != "cost_export"
            or self.source_amount is not None
            or not self.project_id
        ):
            raise ValueError("A CSV requires project cost scope and a calculated source amount")
        return self


class SaveReconciliationRequest(ReconciliationInput):
    request_id: str = Field(min_length=1, max_length=128)
    expected_preview_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReconciliationPolicyRequest(FinanceInput):
    expected_revision: int = Field(ge=0, strict=True)
    enabled: bool = Field(strict=True)
    reason: str = Field(min_length=1, max_length=1000)


class ReconciliationReviewRequest(FinanceInput):
    expected_revision: int = Field(ge=0, strict=True)
    action: Literal["resolve", "reopen", "void"]
    reason: str = Field(min_length=1, max_length=2000)
