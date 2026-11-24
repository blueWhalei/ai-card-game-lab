"""Read and validate the official project-scoped Costs API, without cost estimation."""

import asyncio
import json
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

import httpx

from app.config import Settings
from app.utils.exceptions import AppError

ENDPOINT = "https://api.openai.com/v1/organization/costs"


def billing_error(code: str, status: int = 502) -> AppError:
    # Never persist or expose remote bodies, headers, credentials or exception messages.
    return AppError("Supplier cost synchronization could not be completed", code, status)


def exact_total(items: list[dict[str, Any]]) -> str:
    with localcontext() as context:
        context.prec = 60
        return format(sum((Decimal(row["amount"]) for row in items), Decimal(0)), "f")


class OpenAICostsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self, project_id: str, start: int, end: int) -> list[dict[str, Any]]:
        if not 0 < end - start <= 366 * 86400:
            raise billing_error("BILLING_PERIOD", 409)
        headers = {
            "Authorization": "Bearer " + self.settings.openai_billing_admin_key.get_secret_value(),
            "OpenAI-Organization": self.settings.openai_billing_organization_id,
        }
        params: list[tuple[str, str]] = [
            ("start_time", str(start)),
            ("end_time", str(end)),
            ("bucket_width", "1d"),
            ("project_ids[]", project_id),
            ("group_by[]", "project_id"),
            ("group_by[]", "line_item"),
            ("limit", "180"),
        ]
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        previous_end = start
        try:
            async with (
                asyncio.timeout(120),
                httpx.AsyncClient(timeout=30, follow_redirects=False, trust_env=False) as client,
            ):
                for _ in range(20):
                    response = await client.get(
                        ENDPOINT, headers=headers, params=httpx.QueryParams(tuple(params))
                    )
                    if response.status_code in (401, 403):
                        raise billing_error("BILLING_AUTH")
                    if response.status_code == 429:
                        raise billing_error("BILLING_RATE_LIMIT")
                    if response.status_code != 200:
                        raise billing_error("BILLING_REMOTE")
                    if len(response.content) > 8_000_000:
                        raise ValueError("Response too large")
                    payload = json.loads(response.content, parse_float=Decimal)
                    if payload.get("object") != "page" or not isinstance(payload.get("data"), list):
                        raise ValueError("Invalid page")
                    for bucket in payload["data"]:
                        left, right = bucket["start_time"], bucket["end_time"]
                        if (
                            bucket.get("object") != "bucket"
                            or type(left) is not int
                            or type(right) is not int
                            or not previous_end <= left < right <= end
                            or not isinstance(bucket["results"], list)
                        ):
                            raise ValueError("Invalid or overlapping bucket")
                        previous_end = right
                        for row in bucket["results"]:
                            amount = row["amount"]
                            if (
                                row.get("object") != "organization.costs.result"
                                or row.get("project_id") != project_id
                                or amount["currency"] != "usd"
                                or type(amount["value"]) not in (int, Decimal)
                            ):
                                raise ValueError("Unexpected cost scope")
                            value = Decimal(amount["value"])
                            exponent = value.as_tuple().exponent
                            if (
                                not value.is_finite()
                                or abs(value) > 10**12
                                or not isinstance(exponent, int)
                                or exponent < -18
                            ):
                                raise ValueError("Invalid cost amount")
                            line_item = row.get("line_item")
                            if line_item is not None and (
                                not isinstance(line_item, str) or len(line_item) > 1000
                            ):
                                raise ValueError("Invalid line item")
                            items.append(
                                {
                                    "start_time": left,
                                    "end_time": right,
                                    "amount": format(value, "f"),
                                    "currency": "USD",
                                    "project_id": project_id,
                                    "line_item": line_item,
                                }
                            )
                            if len(items) > 10000:
                                raise ValueError("Too many cost lines")
                    if type(payload.get("has_more")) is not bool:
                        raise ValueError("Missing pagination flag")
                    cursor = payload.get("next_page")
                    if not payload["has_more"]:
                        if cursor is not None:
                            raise ValueError("Inconsistent pagination")
                        return items
                    if (
                        not isinstance(cursor, str)
                        or not cursor
                        or cursor in seen
                        or len(cursor) > 2000
                    ):
                        raise ValueError("Invalid pagination cursor")
                    seen.add(cursor)
                    params = [(key, value) for key, value in params if key != "page"] + [
                        ("page", cursor)
                    ]
                raise ValueError("Too many pages")
        except (httpx.HTTPError, TimeoutError):
            raise billing_error("BILLING_NETWORK") from None
        except (ValueError, KeyError, TypeError, AttributeError, InvalidOperation):
            raise billing_error("BILLING_RESPONSE") from None
