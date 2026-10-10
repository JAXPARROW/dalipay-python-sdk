"""Prefix -> provider mapping and the provider sent in request bodies."""

import json

import httpx
import pytest
import respx

from dalipay import Dalipay, guess_provider, normalize_msisdn

BASE = "https://gateway.test/api/v1"


@pytest.mark.parametrize(
    ("number", "provider"),
    [
        # Unmapped before 0.1.1 -> ValueError before any request was sent.
        ("0632123456", "Halopesa"),
        ("0662123456", "Airtel"),
        ("0703048170", "Tigo"),
        ("0722123456", "Mpesa"),
        # 077 (Zantel, now Yas) was sent as Azampesa before 0.1.1.
        ("0772123456", "Tigo"),
        # Existing mappings unchanged.
        ("0612123456", "Halopesa"),
        ("0622123456", "Halopesa"),
        ("0652123456", "Tigo"),
        ("0672123456", "Tigo"),
        ("0712123456", "Tigo"),
        ("0682123456", "Airtel"),
        ("0692123456", "Airtel"),
        ("0782123456", "Airtel"),
        ("0742123456", "Mpesa"),
        ("0755660639", "Mpesa"),
        ("0762123456", "Mpesa"),
        ("0792123456", "Mpesa"),
    ],
)
def test_guess_provider(number: str, provider: str) -> None:
    assert guess_provider(number) == provider


@pytest.mark.parametrize("fmt", ["0703048170", "255703048170", "+255 703 048 170", "703048170"])
def test_guess_provider_any_format(fmt: str) -> None:
    assert normalize_msisdn(fmt) == "0703048170"
    assert guess_provider(fmt) == "Tigo"


@pytest.mark.parametrize("number", ["0732123456", "0812345678", "12345", ""])
def test_unmapped_or_invalid_returns_none(number: str) -> None:
    # 073 (TTCL) has no Dalipay provider; garbage isn't a number at all.
    assert guess_provider(number) is None


def _client() -> Dalipay:
    return Dalipay(public_key="gw_pk_test_x", secret_key="gw_sk_test_x", base_url=BASE)


def _created(provider: str) -> httpx.Response:
    return httpx.Response(
        201,
        json={
            "success": True,
            "message": "Checkout request sent to customer (test mode - simulated)",
            "data": {
                "uuid": "c4497523-a565-4766-a03d-441b045dc1e8",
                "reference": "col_vg5mOoA4QIJoxJK9MfhTLQ",
                "status": "processing",
                "amount": 500,
                "currency": "TZS",
                "provider": provider,
                "external_id": "INV-1",
            },
        },
    )


@respx.mock
def test_create_collection_sends_guessed_provider() -> None:
    route = respx.post(f"{BASE}/collections").mock(return_value=_created("Tigo"))
    with _client() as dp:
        dp.create_collection(account_number="255703048170", amount=500, external_id="INV-1")
    body = json.loads(route.calls.last.request.content)
    assert body["provider"] == "Tigo"
    assert body["account_number"] == "255703048170"
    assert body["external_id"] == "INV-1"


@respx.mock
def test_explicit_provider_wins_over_guess() -> None:
    route = respx.post(f"{BASE}/collections").mock(return_value=_created("Tigo"))
    with _client() as dp:
        dp.create_collection(
            account_number="0772123456", amount=500, external_id="INV-2", provider="Tigo"
        )
    assert json.loads(route.calls.last.request.content)["provider"] == "Tigo"


def test_ttcl_without_provider_raises_before_sending() -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(f"{BASE}/collections")
        with _client() as dp, pytest.raises(ValueError, match="provider"):
            dp.create_collection(account_number="0732123456", amount=500, external_id="INV-3")
        assert not route.called
