"""Data models for Dalipay SDK."""

from dataclasses import dataclass
from typing import Optional

from .types import (
    CollectionStatus,
    Currency,
    DisbursementStatus,
    Provider,
    WebhookEvent,
)


@dataclass
class Collection:
    """A collection (mobile money checkout prompt).

    Args:
        uuid: Gateway's internal identifier - use this to poll status
        reference: Human-friendly gateway reference (also shown in the dashboard ledger)
        status: processing, success, or failed
        amount: Amount collected (whole units, e.g. TZS)
        currency: Currency code (defaults to TZS)
        provider: Tigo, Airtel, Halopesa, Azampesa, or Mpesa
        external_id: Your own reference for this payment
        created_at: Creation timestamp (ISO 8601), present on status checks
        updated_at: Last update timestamp (ISO 8601), present on status checks

    Example:
        >>> collection = client.create_collection(
        ...     account_number="0712345678",
        ...     amount=1000,
        ...     provider="Tigo",
        ...     external_id="INV-00123",
        ... )
        >>> print(collection.uuid, collection.status)
    """
    uuid: str
    reference: str
    status: CollectionStatus
    amount: float
    currency: Currency
    provider: Provider
    external_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Collection":
        """Create Collection from API response `data` dict."""
        return cls(
            uuid=data.get("uuid", ""),
            reference=data.get("reference", ""),
            status=data.get("status", "processing"),
            amount=data.get("amount", 0),
            currency=data.get("currency", "TZS"),
            provider=data.get("provider", ""),
            external_id=data.get("external_id", ""),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class Disbursement:
    """A disbursement (payout to a mobile money account).

    Args:
        uuid: Gateway's internal identifier
        reference: Human-friendly gateway reference - use this to poll status
        status: awaiting_approval, success, failed, or rejected
        amount: Payout amount (between 1 and 5,000,000)
        provider: Airtel, Tigo, Azampesa, Halopesa, or Mpesa
        external_id: Your own reference for this payout
        recipient_name: Name on the receiving account, if provided
        remarks: Free-text note, if provided
        currency: Currency code, if returned by the API
        created_at: Creation timestamp (ISO 8601), if returned
        updated_at: Last update timestamp (ISO 8601), if returned

    Example:
        >>> disbursement = client.create_disbursement(
        ...     account_number="0712345678",
        ...     amount=5000,
        ...     provider="Tigo",
        ...     external_id="PAYOUT-00045",
        ... )
        >>> print(disbursement.reference, disbursement.status)
    """
    uuid: str
    reference: str
    status: DisbursementStatus
    amount: float
    provider: Provider
    external_id: str
    recipient_name: Optional[str] = None
    remarks: Optional[str] = None
    currency: Optional[Currency] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Disbursement":
        """Create Disbursement from API response `data` dict."""
        return cls(
            uuid=data.get("uuid", ""),
            reference=data.get("reference", ""),
            status=data.get("status", "awaiting_approval"),
            amount=data.get("amount", 0),
            provider=data.get("provider", ""),
            external_id=data.get("external_id", ""),
            recipient_name=data.get("recipient_name"),
            remarks=data.get("remarks"),
            currency=data.get("currency"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class CollectionWebhookData:
    """The `data` object inside a collection webhook payload.

    Args:
        reference: Gateway reference
        uuid: Gateway's internal identifier
        status: success or failed
        amount: Amount collected
        currency: Currency code
        external_id: Your own reference for this payment
    """
    reference: str
    uuid: str
    status: CollectionStatus
    amount: float
    currency: Currency
    external_id: str

    @classmethod
    def from_dict(cls, data: dict) -> "CollectionWebhookData":
        """Create CollectionWebhookData from webhook `data` dict."""
        return cls(
            reference=data.get("reference", ""),
            uuid=data.get("uuid", ""),
            status=data.get("status", "failed"),
            amount=data.get("amount", 0),
            currency=data.get("currency", "TZS"),
            external_id=data.get("external_id", ""),
        )


@dataclass
class WebhookPayload:
    """Webhook event payload sent to your configured Webhook URL.

    Args:
        event: collection.success or collection.failed
        data: The collection details for this event

    Example:
        >>> payload = verify_webhook(body, signature, callback_secret)
        >>> if payload.event == "collection.success":
        ...     print(f"Collection {payload.data.reference} succeeded!")
        ...     # Reconcile against payload.data.external_id
    """
    event: WebhookEvent
    data: CollectionWebhookData

    @classmethod
    def from_dict(cls, data: dict) -> "WebhookPayload":
        """Create WebhookPayload from webhook JSON data."""
        return cls(
            event=data.get("event", ""),
            data=CollectionWebhookData.from_dict(data.get("data", {})),
        )
