"""Response/webhook fields the models must keep (failure_reason was dropped before 0.1.2)."""

import httpx
import respx

from dalipay import Dalipay, WebhookHandler

BASE = "https://gateway.test/api/v1"

# Shapes below are real production responses, Oct 2026.
FAILED_STATUS = {
    "success": True,
    "data": {
        "amount": 1000,
        "created_at": "2026-10-25T14:11:47+03:00",
        "currency": "TZS",
        "external_id": "HU6G5AXUWP8P",
        "failure_reason": "Failed-Insuffient Balance",
        "provider": "Mpesa",
        "reference": "col_EOqvQMuT7gs_Dvz4aoNSvQ",
        "selcom_reference": None,
        "status": "failed",
        "updated_at": "2026-10-25T14:12:05+03:00",
        "uuid": "27de8eb7-aee3-4bf9-937c-72c2f3df220d",
    },
}


@respx.mock
def test_collection_status_keeps_failure_reason() -> None:
    uuid = FAILED_STATUS["data"]["uuid"]
    respx.get(f"{BASE}/collections/{uuid}/status").mock(
        return_value=httpx.Response(200, json=FAILED_STATUS)
    )
    with Dalipay(public_key="pk", secret_key="sk", base_url=BASE) as client:
        collection = client.get_collection_status(uuid)

    assert collection.status == "failed"
    assert collection.failure_reason == "Failed-Insuffient Balance"
    assert collection.selcom_reference is None
    assert collection.raw == FAILED_STATUS["data"]


@respx.mock
def test_collection_status_success_has_no_failure_reason() -> None:
    data = dict(FAILED_STATUS["data"], status="success", failure_reason=None)
    respx.get(f"{BASE}/collections/{data['uuid']}/status").mock(
        return_value=httpx.Response(200, json={"success": True, "data": data})
    )
    with Dalipay(public_key="pk", secret_key="sk", base_url=BASE) as client:
        collection = client.get_collection_status(data["uuid"])

    assert collection.status == "success"
    assert collection.failure_reason is None


def test_webhook_with_failure_reason() -> None:
    payload = WebhookHandler("secret").parse({
        "data": {
            "amount": 500,
            "currency": "TZS",
            "external_id": "ABC123",
            "failure_reason": "The balance of customer is not enough for the payment9009",
            "reference": "col_x",
            "status": "failed",
            "uuid": "u-1",
        },
        "event": "collection.failed",
    })
    assert payload.data.failure_reason == (
        "The balance of customer is not enough for the payment9009"
    )
    assert payload.data.selcom_reference is None


def test_webhook_without_failure_reason() -> None:
    data = {
        "reference": "col_x",
        "uuid": "u-1",
        "status": "failed",
        "amount": 1000,
        "currency": "TZS",
        "external_id": "ABC123",
        "selcom_reference": "SEL-1",
    }
    payload = WebhookHandler("secret").parse({"event": "collection.failed", "data": data})
    assert payload.data.failure_reason is None
    assert payload.data.selcom_reference == "SEL-1"
    assert payload.data.raw == data


@respx.mock
def test_disbursement_keeps_raw() -> None:
    data = {
        "uuid": "d-1",
        "reference": "dsb_x",
        "status": "failed",
        "amount": 5000,
        "provider": "Tigo",
        "external_id": "PAYOUT-1",
        "some_new_field": "kept",
    }
    respx.get(f"{BASE}/disbursements/dsb_x/status").mock(
        return_value=httpx.Response(200, json={"success": True, "data": data})
    )
    with Dalipay(public_key="pk", secret_key="sk", base_url=BASE) as client:
        disbursement = client.get_disbursement_status("dsb_x")

    assert disbursement.raw["some_new_field"] == "kept"
