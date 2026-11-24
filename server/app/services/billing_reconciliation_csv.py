"""Read project cost CSVs selected by the user without storing their original contents."""

import base64
import binascii
import csv
import hashlib
import io
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from typing import Any

from pydantic import TypeAdapter

from app.schemas.billing_reconciliation import CSV_MAX_BYTES, ReconciliationInput, SignedCost
from app.utils.exceptions import AppError

MAX_ROWS = 10000
MAX_COLUMNS = 128
signed_cost = TypeAdapter[SignedCost](SignedCost)
DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
UTC_MIDNIGHT = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2})[T ]00:00:00(?:\.0{1,6})?(?:Z|\+00:00)")


def invalid(code: str = "RECONCILIATION_CSV_INVALID") -> AppError:
    return AppError("Could not use the cost CSV for reconciliation", code, 422)


def read_csv(content: str) -> tuple[bytes, list[str], Iterator[list[str]]]:
    try:
        raw = base64.b64decode(content, validate=True)
        if not raw or len(raw) > CSV_MAX_BYTES or b"\0" in raw:
            raise invalid()
        rows = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        header = [name.strip() for name in next(rows, [])]
        if (
            not 2 <= len(header) <= MAX_COLUMNS
            or any(not name or len(name) > 120 or not name.isprintable() for name in header)
            or len(set(header)) != len(header)
        ):
            raise invalid()
        return raw, header, rows
    except (binascii.Error, UnicodeError, csv.Error):
        raise invalid() from None


def service_day(value: str) -> date:
    if DAY.fullmatch(value):
        return date.fromisoformat(value)
    if match := UTC_MIDNIGHT.fullmatch(value):
        return date.fromisoformat(match[1])
    if re.fullmatch(r"[0-9]{9,10}", value):
        seconds = int(value)
        if seconds % 86400 == 0:
            return datetime.fromtimestamp(seconds, UTC).date()
    raise ValueError("Expected a UTC service date or midnight timestamp")


def csv_evidence(body: ReconciliationInput) -> tuple[str, dict[str, Any]]:
    source = body.csv
    assert source is not None
    raw, header, rows = read_csv(source.content_base64)
    columns = {
        "amount": source.amount_column,
        "date": source.date_column,
        "organization": source.organization_column,
        "project": source.project_column,
        "currency": source.currency_column,
    }
    mapped = [name for name in columns.values() if name is not None]
    if len(set(mapped)) != len(mapped) or any(name not in header for name in mapped):
        raise invalid("RECONCILIATION_CSV_COLUMNS")
    checks = [
        (header.index(name), expected)
        for name, expected in (
            (source.organization_column, body.organization_id),
            (source.project_column, body.project_id),
        )
        if name is not None
    ]
    currency_index = header.index(source.currency_column) if source.currency_column else None
    amount_index = header.index(source.amount_column)
    date_index = header.index(source.date_column)
    dates: set[date] = set()
    total = Decimal(0)
    count = 0
    try:
        with localcontext() as context:
            context.prec = 60
            for row in rows:
                if not row:
                    continue
                count += 1
                if count > MAX_ROWS or len(row) != len(header):
                    raise invalid()
                day = service_day(row[date_index].strip())
                if (
                    not body.period_start <= day < body.period_end
                    or any(row[index].strip() != expected for index, expected in checks)
                    or (
                        currency_index is not None
                        and row[currency_index].strip().upper() != body.currency
                    )
                ):
                    raise invalid("RECONCILIATION_CSV_SCOPE")
                dates.add(day)
                total += Decimal(signed_cost.validate_python(row[amount_index].strip()))
        if not count:
            raise invalid()
        amount = signed_cost.validate_python(format(total, "f"))
    except (ValueError, OverflowError, OSError, csv.Error):
        raise invalid() from None
    return amount, {
        "filename": source.filename,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "parser_version": "project-cost-csv-v1",
        "columns": columns,
        "row_count": count,
        "first_service_date": min(dates).isoformat(),
        "last_service_date": max(dates).isoformat(),
    }
