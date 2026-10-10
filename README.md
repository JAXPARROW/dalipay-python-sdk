# Dalipay Python SDK

Official Python SDK for the [Dalipay](https://dalipay.co.tz) Collections & Disbursements API - trigger mobile money checkout prompts (Tigo Pesa, Airtel Money, HaloPesa, AzamPesa) and send payouts, then track status by polling or via webhooks.

Only call this SDK from your backend - never from a browser, mobile app, or any client the public can inspect. If a key pair is exposed, revoke it immediately from your API keys settings and generate a new one.

## Installation

```bash
pip install dalipay
```

## Quick Start

Dalipay is self-hosted per merchant/gateway deployment, so there's no single shared API host - pass your gateway's own base URL.

```python
from dalipay import Dalipay

client = Dalipay(
    public_key="gw_pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    secret_key="gw_sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    base_url="https://your-gateway-domain/api/v1",
)

collection = client.create_collection(
    account_number="0712345678",
    amount=1000,
    external_id="INV-00123",
    customer_name="Asha Mwakasege",
    # provider is optional - see "Provider auto-detection" below
)

print(f"UUID: {collection.uuid}")
print(f"Status: {collection.status}")  # always "processing" right after creation
```

## Health Check

Dalipay doesn't publish a dedicated health-check endpoint, and every `POST` endpoint has real side effects (a USSD prompt, a money movement). `is_healthy()` instead does a read-only, side-effect-free probe: it checks collection status for a randomly generated uuid that's virtually guaranteed not to exist. A `404` proves the base URL is reachable and the key pair was accepted (bad credentials would `401` first); nothing is created and no phone number is contacted.

```python
if not client.is_healthy():
    raise RuntimeError("Cannot reach Dalipay gateway")
```

## Test vs. production

Every API key pair is tied to one environment - the environment is determined entirely by which key pair you send, there's no separate flag.

| Key prefix | Behavior |
|---|---|
| `gw_pk_test_...` / `gw_sk_test_...` | Collections & settlements are simulated instantly - no real USSD prompt, no real money. |
| `gw_pk_production_...` / `gw_sk_production_...` | Real money. Triggers an actual USSD prompt and real settlement. |

Double-check which key pair you're using before testing against `create_collection` with a real phone number - production keys send a live payment prompt.

## Collections

### Create a collection

Triggers a mobile money checkout prompt on the customer's phone. The customer confirms or cancels on their device; the final result arrives asynchronously.

```python
collection = client.create_collection(
    account_number="0712345678",   # Required
    amount=1000,                   # Required
    external_id="INV-00123",       # Required, your own reference, max 30 chars
    provider="Tigo",               # Optional: Tigo, Airtel, Halopesa, Azampesa, Mpesa
                                    #   - if omitted, guessed from account_number's prefix
    currency="TZS",                # Optional, defaults to TZS
    customer_name="Asha Mwakasege",  # Optional
)

print(collection.uuid)       # store this - you'll need it to check status
print(collection.reference)  # human-friendly gateway reference
```

### Check collection status

Poll this to find out whether the customer confirmed or cancelled the prompt. Webhooks are faster for most integrations - use polling as a fallback or an on-demand "refresh".

```python
collection = client.get_collection_status(collection.uuid)
print(collection.status)  # processing, success, or failed
```

Or block until it resolves (or times out) instead of polling by hand:

```python
result = client.wait_for_collection(collection.uuid, timeout=300, interval=3)
print(result.status)  # success, failed, or still "processing" if the timeout elapsed
```

| Status | Meaning |
|---|---|
| `processing` | Awaiting customer response |
| `success` | Payment confirmed & balance credited |
| `failed` | Cancelled, declined, or expired |

A collection can stay `processing` for up to a few minutes. If you need a hard cutoff, treat anything still `processing` after ~5 minutes as likely abandoned, while still honoring a late `success` if it arrives.

There is no automatic retry: a cancelled, declined, or expired prompt is terminal (`failed`). To try again, call `create_collection` again with a fresh `external_id`.

### Provider auto-detection

`provider` is optional on `create_collection` and `create_disbursement` - if you omit it, the SDK guesses it from `account_number`'s prefix using `guess_provider`:

```python
from dalipay import guess_provider

guess_provider("0755660639")  # "Mpesa"
guess_provider("0710000000")  # "Tigo"
guess_provider("0700000000")  # "Tigo"  (070 = Mixx by Yas, added in 0.1.1)
guess_provider("0730000000")  # None - 073/TTCL has no mobile money provider on this API
```

Tanzanian numbers can be **ported** between networks, so a prefix doesn't guarantee the actual carrier - this is a convenience default, not a guarantee. If you already know the provider (e.g. the customer selected their network at checkout), pass it explicitly rather than relying on the guess. If the prefix can't be resolved (unrecognized, or 073/TTCL, which isn't one of the five supported providers), `create_collection`/`create_disbursement` raise `ValueError` and you must pass `provider` yourself.

## Disbursements

Send a payout from your gateway balance to a mobile money account.

```python
disbursement = client.create_disbursement(
    account_number="0712345678",     # Required
    amount=5000,                     # Required, between 1 and 5,000,000
    external_id="PAYOUT-00045",      # Required, your own reference, max 30 chars
    provider="Tigo",                 # Optional: Airtel, Tigo, Azampesa, Halopesa, Mpesa
                                      #   - if omitted, guessed from account_number's prefix
    recipient_name="Juma Hassan",    # Optional
    remarks="Agent commission",      # Optional
)

print(disbursement.reference)
print(disbursement.status)  # "success" in test mode, "awaiting_approval" in production
```

In production, the amount + fee is held from your balance immediately and the request waits for platform admin approval.

### Check disbursement status

```python
disbursement = client.get_disbursement_status(disbursement.reference)
print(disbursement.status)
```

| Status | Meaning |
|---|---|
| `awaiting_approval` | Held, queued for admin review |
| `success` | Sent to recipient |
| `failed` | Send failed, balance refunded |
| `rejected` | Declined by admin, balance refunded |

## Webhooks

If you configure a webhook URL in Settings, the gateway sends a signed POST request to it whenever a collection resolves.

```python
from dalipay import verify_webhook, WebhookVerificationError

# In your webhook endpoint
try:
    payload = verify_webhook(
        body=request.body.decode(),
        signature=request.headers["X-Signature"],
        callback_secret="your_callback_secret",  # from Settings
    )

    if payload.event == "collection.success":
        # Mark the order matching payload.data.external_id as paid
        print(f"Collection {payload.data.reference} succeeded!")
    elif payload.event == "collection.failed":
        print(f"Collection {payload.data.reference} failed")

except WebhookVerificationError as e:
    print(f"Invalid webhook: {e}")
```

Respond with a 2xx status quickly. If your endpoint is slow or unreachable, the gateway logs the delivery attempt but does not currently retry - use status polling as a backstop for critical flows.

### Webhook events

| Event | Description |
|---|---|
| `collection.success` | Collection confirmed and balance credited |
| `collection.failed` | Collection cancelled, declined, or expired |

## Async Support

For async applications (FastAPI, aiohttp, etc.):

```python
from dalipay import AsyncDalipay

async def create_collection():
    async with AsyncDalipay(
        public_key="gw_pk_test_...",
        secret_key="gw_sk_test_...",
        base_url="https://your-gateway-domain/api/v1",
    ) as client:
        collection = await client.create_collection(
            account_number="0712345678",
            amount=1000,
            external_id="INV-00123",
        )
        result = await client.wait_for_collection(collection.uuid)
        return result
```

## Error Handling

```python
from dalipay import (
    Dalipay,
    ValidationError,
    AuthenticationError,
    PaymentRequiredError,
    ForbiddenError,
    NotFoundError,
    MethodNotAllowedError,
    ServerError,
)

try:
    collection = client.create_collection(...)
except ValidationError as e:
    print(f"Invalid request: {e.message}")        # 400
except AuthenticationError:
    print("Invalid API key pair")                  # 401
except PaymentRequiredError as e:
    print(f"Insufficient balance: {e.message}")     # 402
except ForbiddenError:
    print("IP not whitelisted, or KYC required")   # 403
except NotFoundError:
    print("Unknown collection/disbursement")        # 404
except MethodNotAllowedError:
    print("Wrong HTTP verb")                        # 405
except ServerError:
    print("Dalipay server error, try again later")  # 500
```

Every exception carries `.message` (human-readable) and `.code` (HTTP status).

## Supported Providers

`Tigo`, `Airtel`, `Halopesa`, `Azampesa`, `Mpesa`

## License

MIT
