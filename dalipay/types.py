"""Type definitions for Dalipay SDK."""

from typing import Literal

# Mobile money network. Collections additionally accept the same set;
# disbursements list them in a different order in the docs but it's the
# same five providers.
Provider = Literal["Tigo", "Airtel", "Halopesa", "Azampesa", "Mpesa"]

CollectionStatus = Literal["processing", "success", "failed"]

DisbursementStatus = Literal["awaiting_approval", "success", "failed", "rejected"]

# Only "TZS" is documented today, but kept as `str` since other currencies
# may be supported later.
Currency = str

WebhookEvent = Literal["collection.success", "collection.failed"]
