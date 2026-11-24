"""Validate supplier scope and exact returned amounts without real credentials/network."""

import json
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest

from app.config import Settings
from app.services.openai_costs import ENDPOINT, OpenAICostsClient, exact_total
from app.utils.exceptions import AppError

REAL_CLIENT = httpx.AsyncClient


def page(start=100, end=200, amount=0.1000001, **changes):
    result = {
        "object": "page",
        "data": [
            {
                "object": "bucket",
                "start_time": start,
                "end_time": end,
                "results": [
                    {
                        "object": "organization.costs.result",
                        "project_id": "proj_test",
                        "line_item": "input_tokens",
                        "amount": {"value": amount, "currency": "usd"},
                    }
                ],
            }
        ],
        "has_more": False,
        "next_page": None,
    }
    result.update(changes)
    return result


async def fetch(handler, start=100, end=300):
    settings = Settings(
        _env_file=None,
        openai_api_key="model-key-must-not-be-used",
        openai_base_url="https://unused.invalid",
        openai_billing_admin_key="admin-test",
        openai_billing_organization_id="org-test",
    )
    with patch(
        "app.services.openai_costs.httpx.AsyncClient",
        side_effect=lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw),
    ):
        return await OpenAICostsClient(settings).fetch("proj_test", start, end)


async def test_pagination_scope_headers_and_exact_negative_adjustment():
    requests = []

    def handler(request):
        requests.append(request)
        assert str(request.url).startswith(ENDPOINT)
        assert request.headers["Authorization"] == "Bearer admin-test"
        assert request.headers["OpenAI-Organization"] == "org-test"
        assert request.url.params.get_list("project_ids[]") == ["proj_test"]
        assert request.url.params.get_list("group_by[]") == ["project_id", "line_item"]
        assert request.url.params["end_time"] == "300"
        if len(requests) == 1:
            return httpx.Response(200, json=page(has_more=True, next_page="next"))
        assert request.url.params["page"] == "next"
        return httpx.Response(200, json=page(200, 300, -0.00000001))

    items = await fetch(handler)
    assert len(requests) == 2
    assert items[0]["amount"] == "0.1000001"
    assert exact_total(items) == "0.10000009"


@pytest.mark.parametrize(
    "change",
    [
        "project",
        "currency",
        "bool",
        "null",
        "string",
        "duplicate_bucket",
        "range",
        "pagination",
        "cursor",
        "nan",
    ],
)
async def test_invalid_scope_or_amount_never_becomes_zero(change):
    data = page()
    row = data["data"][0]["results"][0]
    if change == "project":
        row["project_id"] = None
    if change == "currency":
        row["amount"]["currency"] = "cny"
    if change == "bool":
        row["amount"]["value"] = True
    if change == "null":
        row["amount"]["value"] = None
    if change == "string":
        row["amount"]["value"] = "0.1"
    if change == "nan":
        row["amount"]["value"] = float("nan")
    if change == "duplicate_bucket":
        data["data"].append(data["data"][0])
    if change == "range":
        data["data"][0]["end_time"] = 400
    if change == "pagination":
        del data["has_more"]
    if change == "cursor":
        data.update(has_more=True, next_page=None)
    with pytest.raises(AppError) as error:
        await fetch(lambda _: httpx.Response(200, content=json.dumps(data)))
    assert error.value.code == "BILLING_RESPONSE"


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "BILLING_AUTH"),
        (403, "BILLING_AUTH"),
        (429, "BILLING_RATE_LIMIT"),
        (500, "BILLING_REMOTE"),
        (302, "BILLING_REMOTE"),
    ],
)
async def test_remote_errors_are_sanitized_and_redirects_not_followed(status, code):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status, text="secret-provider-body", headers={"Location": "https://other.invalid"}
        )

    with pytest.raises(AppError) as error:
        await fetch(handler)
    assert error.value.code == code and "secret" not in str(error.value)
    assert len(requests) == 1


async def test_network_failure_after_first_page_discards_result():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=page(has_more=True, next_page="next"))
        raise httpx.ReadTimeout("sensitive diagnostic", request=request)

    with pytest.raises(AppError) as error:
        await fetch(handler)
    assert error.value.code == "BILLING_NETWORK"


async def test_empty_complete_page_and_high_precision():
    assert await fetch(lambda _: httpx.Response(200, json=page(data=[]))) == []
    assert (
        exact_total([{"amount": "0.000000000000000001"}, {"amount": "-0.000000000000000001"}])
        == "0.000000000000000000"
    )
    assert Decimal(exact_total([])) == 0
