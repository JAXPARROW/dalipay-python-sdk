"""
Dalipay - Python SDK for the Dalipay Collections & Disbursements API.

Trigger mobile money checkout prompts (Tigo Pesa, Airtel Money, HaloPesa,
AzamPesa) and send payouts, then track status by polling or via webhooks.

Usage:
    >>> from dalipay import Dalipay
    >>> client = Dalipay(
    ...     public_key="gw_pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ...     secret_key="gw_sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ...     base_url="https://your-gateway-domain/api/v1",
    ... )
    >>> collection = client.create_collection(
    ...     account_number="0712345678",
    ...     amount=1000,
    ...     provider="Tigo",
    ...     external_id="INV-00123",
    ... )
    >>> print(collection.uuid)
"""

from .client import AsyncDalipay, Dalipay
from .exceptions import (
    AuthenticationError,
    DalipayError,
    ForbiddenError,
    MethodNotAllowedError,
    NotFoundError,
    PaymentRequiredError,
    ServerError,
    ValidationError,
    WebhookVerificationError,
)
from .models import Collection, CollectionWebhookData, Disbursement, WebhookPayload
from .types import CollectionStatus, Currency, DisbursementStatus, Provider, WebhookEvent
from .utils import guess_provider, normalize_msisdn
from .webhooks import WebhookHandler, verify_webhook

__version__ = "0.1.0"
__all__ = [
    # Clients
    "Dalipay",
    "AsyncDalipay",
    # Models
    "Collection",
    "Disbursement",
    "WebhookPayload",
    "CollectionWebhookData",
    # Types
    "Provider",
    "CollectionStatus",
    "DisbursementStatus",
    "Currency",
    "WebhookEvent",
    # Utils
    "guess_provider",
    "normalize_msisdn",
    # Webhooks
    "WebhookHandler",
    "verify_webhook",
    # Exceptions
    "DalipayError",
    "ValidationError",
    "AuthenticationError",
    "PaymentRequiredError",
    "ForbiddenError",
    "NotFoundError",
    "MethodNotAllowedError",
    "ServerError",
    "WebhookVerificationError",
]
