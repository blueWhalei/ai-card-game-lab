"""Reproduce a saved cost CSV reconciliation from its original evidence, read-only."""

import argparse
import asyncio
import base64
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import aiosqlite

from app.repositories.billing_reconciliation_repo import BillingReconciliationRepository
from app.schemas.billing_reconciliation import CSV_MAX_BYTES, ReconciliationInput
from app.services.billing_reconciliation_service import BillingReconciliationService
from app.utils.exceptions import AppError


class VerificationError(Exception):
    """A failed reproduction check, with a code safe to print."""


async def reproduce(
    database: Path, study_id: str, record_id: str, csv_path: Path
) -> dict[str, Any]:
    with csv_path.open("rb") as file:
        raw = file.read(CSV_MAX_BYTES + 1)
    if not raw or len(raw) > CSV_MAX_BYTES:
        raise VerificationError("CSV_SIZE")
    file_hash = hashlib.sha256(raw).hexdigest()

    async with aiosqlite.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN")
        record = await BillingReconciliationRepository(db).record(study_id, record_id)
        if record is None:
            raise VerificationError("RECONCILIATION_NOT_FOUND")
        saved = json.loads(record["comparison_json"])
        provenance = saved.get("csv_evidence")
        if provenance is None:
            raise VerificationError("CSV_EVIDENCE_REQUIRED")
        if file_hash != provenance["sha256"]:
            raise VerificationError("CSV_DIGEST_MISMATCH")
        inputs = saved["input"]
        if inputs["attempt_id"] != record["attempt_id"]:
            raise VerificationError("SAVED_COMPARISON_MISMATCH")
        request = ReconciliationInput.model_validate(
            {
                **inputs,
                "source_amount": None,
                "csv": {
                    "filename": provenance["filename"],
                    "content_base64": base64.b64encode(raw).decode("ascii"),
                    **{f"{role}_column": column for role, column in provenance["columns"].items()},
                },
            }
        )
        result = await BillingReconciliationService().calculate(db, study_id, request)
        if result != saved or result["result"] != record["result"]:
            raise VerificationError("SAVED_COMPARISON_MISMATCH")

    return {
        "reproduction": "reproduced",
        "record_id": record_id,
        "study_id": study_id,
        "created_at": record["created_at"],
        "review_action": record["review_action"],
        "review_revision": record["review_revision"],
        "source": {
            "sha256": file_hash,
            "filename": provenance["filename"],
            "parser_version": provenance["parser_version"],
            "columns": provenance["columns"],
            "row_count": provenance["row_count"],
            "first_service_date": provenance["first_service_date"],
            "last_service_date": provenance["last_service_date"],
        },
        "snapshot": {
            "id": result["snapshot"]["id"],
            "revision": result["snapshot"]["revision"],
            "query_start_unix_utc": result["snapshot"]["start_time"],
            "query_end_unix_utc_exclusive": result["snapshot"]["end_time"],
            "saved_at": result["snapshot"]["finished_at"],
            "source_url": result["source_url"],
        },
        "scope": {
            "organization_id": inputs["organization_id"],
            "project_id": inputs["project_id"],
            "currency": inputs["currency"],
            "service_start_utc": inputs["period_start"],
            "service_end_utc_exclusive": inputs["period_end"],
        },
        "comparison": {
            "calculation_version": result["calculation_version"],
            "result": result["result"],
            "reasons": result["reasons"],
            "csv_amount": result["input"]["source_amount"],
            "snapshot_period_amount": result["interface_amount"],
            "snapshot_minus_csv": result["difference"],
            "snapshot_line_count": result["included_line_count"],
        },
        "invoice_verified": False,
        "complete_costs_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path, help="Explicit path to CardLab SQLite")
    parser.add_argument("--study", required=True, help="Study ID")
    parser.add_argument("--record", required=True, help="Saved reconciliation ID")
    parser.add_argument("--csv", required=True, type=Path, help="Original cost export")
    args = parser.parse_args(argv)
    try:
        report = asyncio.run(reproduce(args.db, args.study, args.record, args.csv))
    except VerificationError as exc:
        code = str(exc)
    except AppError as exc:
        code = exc.code
    except (ValueError, KeyError, TypeError, AttributeError):
        code = "INVALID_SAVED_EVIDENCE"
    except (OSError, sqlite3.Error):
        code = "EVIDENCE_READ_FAILED"
    else:
        print(json.dumps(report, indent=2))
        return 0
    print(json.dumps({"reproduction": "failed", "code": code}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
