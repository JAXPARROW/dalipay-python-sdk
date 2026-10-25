# Dalipay Integration Reference

This is the complete, self-contained integration reference for the Dalipay
Collections & Disbursements platform: the Python SDK (`pip install dalipay`)
and the underlying raw HTTP API it wraps. It covers every public method,
type, error, and endpoint. No other documentation should be needed to
integrate — either with the Python SDK, or by calling the raw HTTP API
directly from another language/system.

- Package: `dalipay` on PyPI — https://pypi.org/project/dalipay/
- Source: https://github.com/JAXPARROW/dalipay-python-sdk
- SDK version covered by this document: `0.1.0`
- Python: `>=3.10`. Single runtime dependency: `httpx>=0.24.0`.

---

## Table of contents

1. [Core concepts](#1-core-concepts)
2. [Authentication](#2-authentication)
3. [Installation & client setup](#3-installation--client-setup)
4. [Collections](#4-collections)
5. [Disbursements](#5-disbursements)
6. [Webhooks](#6-webhooks)
7. [Provider detection & phone normalization](#7-provider-detection--phone-normalization)
8. [Health check](#8-health-check)
9. [Errors](#9-errors)
10. [Data types reference](#10-data-types-reference)
11. [Raw HTTP API reference](#11-raw-http-api-reference)
12. [End-to-end example (Flask + webhook)](#12-end-to-end-example-flask--webhook)
13. [Integration rules / gotchas](#13-integration-rules--gotchas)

---

## 1. Core concepts

- **Self-hosted, per-merchant.** There is no single shared Dalipay API host.
  Each merchant/gateway deployment has its own base URL, e.g.
  `https://your-gateway-domain/api/v1`. You must always supply it — the SDK
  has no default and raises `ValueError` if `base_url` is falsy.
- **Two products:**
  - **Collections** — trigger a mobile money checkout (USSD) prompt on a
    customer's phone to *collect* money. Resolves asynchronously (customer
    confirms/cancels on their device).
  - **Disbursements** — send a payout *from* your gateway balance to a
    mobile money account.
- **Two environments, one flag: the key pair.** There is no separate
  test/live switch. Which environment you hit is determined entirely by
  which key pair (`X-Public-Key` / `X-Secret-Key`) you send:
  | Key prefix | Environment | Behavior |
  |---|---|---|
  | `gw_pk_test_...` / `gw_sk_test_...` | Test | Collections & disbursements are simulated instantly. No real USSD prompt, no real money. |
  | `gw_pk_production_...` / `gw_sk_production_...` | Production | Real money. Triggers an actual USSD prompt on the customer's phone and a real settlement. |
- **Backend only.** Never call this API/SDK from a browser, mobile app, or
  any client the public can inspect — both keys are effectively bearer
  credentials. If a key pair is exposed, revoke it and generate a new one
  immediately.
- **Two ways to learn the outcome of a collection:** poll `GET
  /collections/{uuid}/status`, or configure a webhook (§6). Webhooks are
  faster; polling is the reliable fallback (no webhook retries are sent by
  the gateway if your endpoint is down).
- **Idempotency is on you.** `external_id` is *your* reference, not a
  dedupe key enforced by a single retry — a cancelled/declined/expired
  collection is terminal (`failed`); to try again, call
  `create_collection` again with a **fresh** `external_id`.

---

## 2. Authentication

Every request must carry both headers plus a JSON content type:

```
X-Public-Key: gw_pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
X-Secret-Key: gw_sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Content-Type: application/json
```

The Python SDK sets these three headers once, on the underlying
`httpx.Client`/`httpx.AsyncClient`, when you construct `Dalipay(...)` /
`AsyncDalipay(...)` — every request made through the client automatically
carries them. You never set headers per-call.

Missing or invalid keys → HTTP `401` → SDK raises `AuthenticationError`.

---

## 3. Installation & client setup

```bash
pip install dalipay
```

### Sync client

```python
from dalipay import Dalipay

client = Dalipay(
    public_key="gw_pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",  # required
    secret_key="gw_sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",  # required
    base_url="https://your-gateway-domain/api/v1",  # required, your gateway's own URL
    timeout=30.0,  # optional, seconds, default 30.0
)
# ... use client ...
client.close()  # or use as a context manager, see below
```

Context manager form (recommended — closes the underlying HTTP connection
pool automatically):

```python
with Dalipay(public_key, secret_key, base_url) as client:
    collection = client.create_collection(...)
```

### Async client

Identical API surface, `async`/`await`, for FastAPI/aiohttp/etc.:

```python
from dalipay import AsyncDalipay

async with AsyncDalipay(public_key, secret_key, base_url) as client:
    collection = await client.create_collection(
        account_number="0712345678",
        amount=1000,
        external_id="INV-00123",
    )
    result = await client.wait_for_collection(collection.uuid)
```

`AsyncDalipay` has the exact same method names, arguments, return types,
and exceptions as `Dalipay` — every method below is just prefixed with
`await` and uses `async with` / `await client.close()` instead of the sync
equivalents.

### Constructor errors

Both constructors raise `ValueError("base_url is required, e.g.
https://your-gateway-domain/api/v1")` if `base_url` is empty/`None`.

---

## 4. Collections

### 4.1 `create_collection` — trigger a checkout prompt

Triggers a mobile money checkout (USSD) prompt on the customer's phone.
The customer confirms or cancels on their device; the result arrives
asynchronously.

```python
collection = client.create_collection(
    account_number: str,             # required — customer's MSISDN, e.g. "0712345678"
    amount: float,                   # required — whole units, e.g. TZS
    external_id: str,                # required — your unique reference, max 30 chars
    provider: str | None = None,     # optional — "Tigo" | "Airtel" | "Halopesa" | "Azampesa" | "Mpesa"
                                      #   if omitted, guessed from account_number (see §7)
    currency: str = "TZS",           # optional — only "TZS" is documented today
    customer_name: str | None = None,  # optional — for your records/receipts
) -> Collection
```

Raises `ValueError` if `provider` is omitted and can't be guessed from
`account_number` (e.g. a 073/TTCL number — see §7). Raises the
`DalipayError` subclasses in §9 for API-level failures.

```python
collection = client.create_collection(
    account_number="0712345678",
    amount=1000,
    external_id="INV-00123",
    provider="Tigo",
    customer_name="Asha Mwakasege",
)
print(collection.uuid)       # store this — needed to poll status
print(collection.reference)  # human-friendly gateway reference (dashboard ledger)
print(collection.status)     # always "processing" immediately after creation
```

HTTP equivalent: `POST {base_url}/collections`.

### 4.2 `get_collection_status` — poll for the result

```python
collection = client.get_collection_status(uuid: str) -> Collection
```

```python
collection = client.get_collection_status(collection.uuid)
if collection.status == "success":
    ...  # fulfill order
```

HTTP equivalent: `GET {base_url}/collections/{uuid}/status`.

| `status` | Meaning |
|---|---|
| `processing` | Awaiting customer response |
| `success` | Payment confirmed & your balance credited |
| `failed` | Cancelled, declined, or expired — terminal, no auto-retry |

A collection can stay `processing` for a few minutes. There's no fixed
resolution window from the gateway (~5 minutes is a rule of thumb) — if
you need a hard cutoff, treat anything still `processing` after ~5 minutes
as likely abandoned, while still honoring a late `success` if it arrives.

### 4.3 `wait_for_collection` — block until resolved

Convenience wrapper that polls `get_collection_status` on an interval
until the status leaves `"processing"` or a timeout elapses. It does
**not** raise on timeout — check the returned status yourself.

```python
result = client.wait_for_collection(
    uuid: str,
    timeout: float = 300.0,   # give up polling after this many seconds
    interval: float = 3.0,    # seconds between polls
) -> Collection
```

```python
result = client.wait_for_collection(collection.uuid, timeout=300, interval=3)
if result.status == "success":
    print("Paid!")
elif result.status == "failed":
    print("Cancelled, declined, or expired")
else:
    print("Still processing after the timeout")  # status == "processing"
```

(Implementation note: uses `time.monotonic()`/`time.sleep()` in the sync
client and `asyncio.sleep()` in the async client — it blocks synchronously
or awaits, it does not spawn a background task.)

---

## 5. Disbursements

### 5.1 `create_disbursement` — send a payout

Sends a payout from your gateway balance to a mobile money account.

```python
disbursement = client.create_disbursement(
    account_number: str,               # required — recipient's MSISDN
    amount: float,                     # required — between 1 and 5,000,000
    external_id: str,                  # required — your unique reference, max 30 chars
    provider: str | None = None,       # optional — guessed from account_number if omitted (see §7)
    recipient_name: str | None = None, # optional — name on the receiving account
    remarks: str | None = None,        # optional — free-text note
) -> Disbursement
```

Raises `ValueError` under the same condition as `create_collection` if
`provider` can't be resolved. Raises `DalipayError` subclasses per §9.

```python
disbursement = client.create_disbursement(
    account_number="0712345678",
    amount=5000,
    external_id="PAYOUT-00045",
    provider="Tigo",
    recipient_name="Juma Hassan",
    remarks="Agent commission",
)
print(disbursement.reference, disbursement.status)
```

HTTP equivalent: `POST {base_url}/disbursements`.

**In production**, the amount + fee is held from your balance immediately
and the request waits for platform admin approval
(`status == "awaiting_approval"`). **In test mode** it's simulated
instantly (`status == "success"`).

### 5.2 `get_disbursement_status`

```python
disbursement = client.get_disbursement_status(reference: str) -> Disbursement
```

HTTP equivalent: `GET {base_url}/disbursements/{reference}/status`.
Note: disbursements are looked up by **`reference`**, not `uuid` (unlike
collections, which use `uuid`).

| `status` | Meaning |
|---|---|
| `awaiting_approval` | Held, queued for admin review (production only) |
| `success` | Sent to recipient |
| `failed` | Send failed, balance refunded |
| `rejected` | Declined by admin, balance refunded |

There is no `wait_for_disbursement` helper — poll `get_disbursement_status`
manually if you need to wait (production disbursements can sit in
`awaiting_approval` indefinitely pending a human, so blocking with a fixed
timeout the way `wait_for_collection` does isn't appropriate here).

---

## 6. Webhooks

If a webhook URL is configured in the merchant's Settings, the gateway
sends a signed `POST` to it whenever a **collection** resolves (there is
no webhook for disbursements — poll those). This is faster than polling
and is the recommended primary signal; keep polling as a backstop.

### 6.1 Setup

1. In merchant Settings, set the Webhook URL — an HTTPS endpoint on your
   server that accepts `POST`.
2. Note the **callback secret** shown alongside it — used to verify the
   `X-Signature` header on every delivery.

### 6.2 Payload shape

```json
{
  "event": "collection.success",
  "data": {
    "reference": "col_vg5mOoA4QIJoxJK9MfhTLQ",
    "uuid": "c4497523-a565-4766-a03d-441b045dc1e8",
    "status": "success",
    "amount": 1000,
    "currency": "TZS",
    "external_id": "INV-00123"
  }
}
```

A failed collection sends `"event": "collection.failed"` with
`"data.status": "failed"`. Deliveries may also carry `"selcom_reference"`,
and some failed ones carry `"failure_reason"`. **Not every failed delivery
includes `failure_reason`** - when it's missing, call
`get_collection_status(data.uuid)`; the status API always returns it for a
failed collection.

| Event | Meaning |
|---|---|
| `collection.success` | Collection confirmed and balance credited |
| `collection.failed` | Collection cancelled, declined, or expired |

### 6.3 Verifying the signature (`X-Signature` header)

Every delivery's `X-Signature` header is `hex(HMAC-SHA256(raw_body,
callback_secret))`. **Always verify before trusting the payload** — use a
constant-time comparison (the SDK uses `hmac.compare_digest`; do the
equivalent in any other language, e.g. PHP's `hash_equals`).

**Using the SDK — `WebhookHandler` class:**

```python
from dalipay import WebhookHandler, WebhookVerificationError

handler = WebhookHandler("your_callback_secret")  # from Settings

# In your webhook endpoint:
try:
    payload = handler.verify_and_parse(
        body=request.body.decode(),          # raw request body, MUST be unparsed/unmodified
        signature=request.headers["X-Signature"],
    )
    if payload.event == "collection.success":
        # Reconcile payload.data.external_id against your own records
        print(f"Collection {payload.data.reference} succeeded!")
    elif payload.event == "collection.failed":
        print(f"Collection {payload.data.reference} failed")
except WebhookVerificationError as e:
    # Respond 401 and do NOT process the payload
    print(f"Invalid webhook: {e}")
```

`WebhookHandler` methods:

| Method | Signature | Behavior |
|---|---|---|
| `compute_signature` | `(body: str) -> str` | Returns the hex HMAC-SHA256 the gateway would have sent for this body. |
| `verify_signature` | `(body: str, signature: str) -> bool` | Returns `True`, or raises `WebhookVerificationError("Invalid signature")`. |
| `parse` | `(data: dict) -> WebhookPayload` | Parses an already-verified/parsed JSON dict — no signature check. |
| `verify_and_parse` | `(body: str, signature: str) -> WebhookPayload` | Verifies, then `json.loads`s the body, then parses. **This is the one method you need for the standard flow.** |

**Using the SDK — one-liner function** (equivalent to
`WebhookHandler(secret).verify_and_parse(...)`):

```python
from dalipay import verify_webhook, WebhookVerificationError

payload = verify_webhook(
    body=request.body.decode(),
    signature=request.headers["X-Signature"],
    callback_secret="your_callback_secret",
)
```

**Raw HMAC verification, any language (PHP example):**

```php
$rawBody = file_get_contents('php://input');
$signature = $_SERVER['HTTP_X_SIGNATURE'] ?? '';
$callbackSecret = 'your-callback-secret-from-settings';

$expected = hash_hmac('sha256', $rawBody, $callbackSecret);

if (!hash_equals($expected, $signature)) {
    http_response_code(401);
    exit('Invalid signature');
}

$event = json_decode($rawBody, true);
if ($event['event'] === 'collection.success') {
    // Mark the order matching $event['data']['external_id'] as paid.
}

http_response_code(200);
echo json_encode(['received' => true]);
```

### 6.4 Delivery guarantees

Respond with a `2xx` quickly (ideally under a few seconds). **The gateway
does not currently retry** if your endpoint is slow, errors, or is
unreachable — it just logs the failed delivery attempt. Treat status
polling (§4.2) as the backstop for anything critical, don't rely on
webhooks alone.

---

## 7. Provider detection & phone normalization

`provider` is optional on `create_collection`/`create_disbursement`. If
omitted, the SDK guesses it from `account_number`'s prefix. Tanzanian
numbers can be **ported** between networks, so this is a best-effort
default, not a guarantee — if you already know the actual provider (e.g.
the customer picked their network at checkout), pass it explicitly.

```python
from dalipay import guess_provider, normalize_msisdn

normalize_msisdn("+255712345678")  # -> "0712345678"
normalize_msisdn("255712345678")   # -> "0712345678"
normalize_msisdn("712345678")      # -> "0712345678"
normalize_msisdn("0712345678")     # -> "0712345678"
normalize_msisdn("not a phone")    # -> None

guess_provider("0755660639")  # -> "Mpesa"
guess_provider("0710000000")  # -> "Tigo"
guess_provider("0730000000")  # -> None (073/TTCL — see below)
```

`normalize_msisdn(phone_number) -> Optional[str]`: strips all non-digit
characters, then:
- if it starts with `"255"` and is 12 digits total → converts to
  `"0" + remaining 9 digits`
- elif it's exactly 9 digits → prepends `"0"`
- Result must end up exactly 10 digits starting with `"0"`, else returns
  `None`.

`guess_provider(phone_number) -> Optional[Provider]`: normalizes, then
looks up the first 3 digits of the normalized number in this table:

| Prefix | Provider |
|---|---|
| `072`, `074`, `075`, `076`, `079` | `Mpesa` |
| `066`, `068`, `069`, `078` | `Airtel` |
| `065`, `067`, `070`, `071`, `077` | `Tigo` (Mixx by Yas) |
| `061`, `062`, `063` | `Halopesa` |
| `073` (TTCL) | **not mapped** — returns `None` |

**073/TTCL has no mobile money provider on this API.** The Dalipay API
only accepts `Tigo`, `Airtel`, `Halopesa`, `Azampesa`, or `Mpesa` as
`provider` — there is no valid guess for TTCL numbers, and there's no
provider value you can pass that will actually route to TTCL. If a
`073` number reaches your code, you cannot process it via this API at all
(not just "must pass provider manually" — there's genuinely no supported
provider for it).

If `provider` is omitted and the guess fails for any reason (unrecognized
prefix, invalid number, or 073), `create_collection`/`create_disbursement`
raise:

```python
ValueError(
    f"Could not determine provider from account_number {account_number!r}; "
    "pass provider explicitly (Tigo, Airtel, Halopesa, Azampesa, or Mpesa)."
)
```

---

## 8. Health check

There's no dedicated health-check endpoint on the gateway, and every
documented `POST` endpoint has a real side effect (a USSD prompt, a money
movement) — so a naive "ping the API" isn't safe. `is_healthy()` instead
does a **read-only, side-effect-free** probe: `GET
/collections/{random-uuid}/status` with a freshly generated UUID that is
virtually guaranteed not to exist.

```python
if not client.is_healthy():
    raise RuntimeError("Cannot reach Dalipay gateway")
```

```python
is_healthy() -> bool
```

Logic:
- Network error (DNS failure, connection refused, timeout) → `False`.
- HTTP `401` (key pair rejected) → `False`.
- Any other HTTP status (including the expected `404` for the nonexistent
  uuid) → `True`, i.e. `status_code < 500` and not `401` counts as
  healthy.

No collection/disbursement is created and no phone number is contacted by
this call.

---

## 9. Errors

Every API response has the shape `{"success": bool, "message": str,
"data"?: {...}}`. When `success` is falsy, the SDK maps the HTTP status
code to one of these exceptions, all importable from `dalipay`:

| Exception | HTTP code | Meaning |
|---|---|---|
| `ValidationError` | 400 | Missing/invalid field, malformed JSON, `external_id` too long, invalid phone number, unsupported provider, amount out of range, etc. |
| `AuthenticationError` | 401 | Missing or invalid `X-Public-Key` / `X-Secret-Key`. |
| `PaymentRequiredError` | 402 | Insufficient balance for a disbursement/settlement. |
| `ForbiddenError` | 403 | Request IP not in your IP whitelist, or KYC required for a production settlement. |
| `NotFoundError` | 404 | Unknown collection/disbursement uuid/reference for this merchant. |
| `MethodNotAllowedError` | 405 | Wrong HTTP verb for the endpoint. |
| `ServerError` | 500+ | Unexpected internal error — safe to retry, contact support if it persists. |
| `DalipayError` | anything else | Base class for all of the above; also the fallback for unmapped status codes. |
| `WebhookVerificationError` | n/a | Webhook `X-Signature` didn't match (see §6.3). Not tied to an HTTP status — this is raised locally by `WebhookHandler`, not returned by the API. |

`DalipayError` (and therefore every subclass) carries:
- `.message: str` — human-readable message from the API's `message` field
  (or, if the response body wasn't valid JSON, the raw response text).
- `.code: int` — the HTTP status code (`0` for `WebhookVerificationError`,
  which isn't tied to an HTTP response).

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
    DalipayError,  # catch-all base class
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
except DalipayError as e:
    print(f"Other Dalipay error: {e.message} ({e.code})")
```

Known validation messages you may see in `.message` (from the raw API):
- `"external_id is required"` / `"external_id must be 30 characters or fewer"`
- `"amount must be between 1 and 5,000,000"` (disbursements)
- `"provider must be one of: Airtel, Tigo, Azampesa, Halopesa, Mpesa"`
- `"account_number must be a valid Tanzanian phone number"`
- `"Insufficient balance"`
- `"Production settlements require KYC verification. Please complete KYC first."`

---

## 10. Data types reference

All importable from `dalipay`. All are plain `@dataclass`es with a
`.from_dict(dict) -> T` classmethod used internally by the SDK — you
normally receive these already constructed as return values, you don't
build them yourself.

### `Collection`

Returned by `create_collection`, `get_collection_status`,
`wait_for_collection`.

| Field | Type | Notes |
|---|---|---|
| `uuid` | `str` | Gateway's internal identifier — use to poll status. |
| `reference` | `str` | Human-friendly gateway reference (dashboard ledger). |
| `status` | `"processing" \| "success" \| "failed"` | |
| `amount` | `float` | Whole units, e.g. TZS. |
| `currency` | `str` | Defaults `"TZS"`. |
| `provider` | `str` | `"Tigo" \| "Airtel" \| "Halopesa" \| "Azampesa" \| "Mpesa"` |
| `external_id` | `str` | Your reference. |
| `created_at` | `str \| None` | ISO 8601, present on status checks. |
| `updated_at` | `str \| None` | ISO 8601, present on status checks. |
| `failure_reason` | `str \| None` | Why it failed, in the network's own words (e.g. `"Failed-Insuffient Balance"`). Status checks only; `None` unless `status == "failed"`. |
| `selcom_reference` | `str \| None` | Upstream aggregator reference, if any. |
| `raw` | `dict` | Full `data` dict as received. |

### `Disbursement`

Returned by `create_disbursement`, `get_disbursement_status`.

| Field | Type | Notes |
|---|---|---|
| `uuid` | `str` | Gateway's internal identifier. |
| `reference` | `str` | Use this (not `uuid`) to poll status. |
| `status` | `"awaiting_approval" \| "success" \| "failed" \| "rejected"` | |
| `amount` | `float` | Between 1 and 5,000,000. |
| `provider` | `str` | |
| `external_id` | `str` | Your reference. |
| `recipient_name` | `str \| None` | If provided on creation. |
| `remarks` | `str \| None` | If provided on creation. |
| `currency` | `str \| None` | If returned by the API. |
| `created_at` | `str \| None` | ISO 8601, if returned. |
| `updated_at` | `str \| None` | ISO 8601, if returned. |
| `raw` | `dict` | Full `data` dict as received. |

### `WebhookPayload`

Returned by `WebhookHandler.parse` / `.verify_and_parse` / `verify_webhook`.

| Field | Type |
|---|---|
| `event` | `"collection.success" \| "collection.failed"` |
| `data` | `CollectionWebhookData` |

### `CollectionWebhookData`

The nested `data` object inside a `WebhookPayload`.

| Field | Type |
|---|---|
| `reference` | `str` |
| `uuid` | `str` |
| `status` | `"success" \| "failed"` |
| `amount` | `float` |
| `currency` | `str` |
| `external_id` | `str` |
| `failure_reason` | `str \| None` — only on some `collection.failed` deliveries |
| `selcom_reference` | `str \| None` |
| `raw` | `dict` |

### Type aliases (`dalipay.types`)

```python
Provider = Literal["Tigo", "Airtel", "Halopesa", "Azampesa", "Mpesa"]
CollectionStatus = Literal["processing", "success", "failed"]
DisbursementStatus = Literal["awaiting_approval", "success", "failed", "rejected"]
Currency = str  # only "TZS" is documented today
WebhookEvent = Literal["collection.success", "collection.failed"]
```

---

## 11. Raw HTTP API reference

Use this section to integrate from any language/system without the Python
SDK. All requests need the two auth headers from §2. Base path below is
`{base_url}` = your gateway's own URL, e.g.
`https://your-gateway-domain/api/v1`.

### `POST {base_url}/collections`

Request body:

| Field | Type | Required | Description |
|---|---|---|---|
| `account_number` | string | Yes | Customer's mobile money number, e.g. `"0712345678"`. |
| `amount` | number | Yes | Amount to collect (whole units, e.g. TZS). |
| `currency` | string | No | Defaults to `"TZS"`. |
| `provider` | string | Yes | `Tigo`, `Airtel`, `Halopesa`, `Azampesa`, or `Mpesa` — must match the customer's actual network. |
| `external_id` | string | Yes | Your unique reference for this payment (max 30 chars). |
| `customer_name` | string | No | For your records/receipts. |

```bash
curl -X POST https://your-gateway-domain/api/v1/collections \
  -H "X-Public-Key: gw_pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "X-Secret-Key: gw_sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "account_number": "0712345678",
    "amount": 1000,
    "currency": "TZS",
    "provider": "Tigo",
    "external_id": "INV-00123",
    "customer_name": "Asha Mwakasege"
  }'
```

Response — `201 Created`:

```json
{
  "success": true,
  "message": "Checkout request sent to customer (test mode - simulated)",
  "data": {
    "uuid": "c4497523-a565-4766-a03d-441b045dc1e8",
    "reference": "col_vg5mOoA4QIJoxJK9MfhTLQ",
    "status": "processing",
    "amount": 1000,
    "currency": "TZS",
    "provider": "Tigo",
    "external_id": "INV-00123"
  }
}
```

### `GET {base_url}/collections/{uuid}/status`

```bash
curl -X GET "https://your-gateway-domain/api/v1/collections/c4497523-a565-4766-a03d-441b045dc1e8/status" \
  -H "X-Public-Key: gw_pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "X-Secret-Key: gw_sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Response — `200 OK`:

```json
{
  "success": true,
  "data": {
    "uuid": "c4497523-a565-4766-a03d-441b045dc1e8",
    "reference": "col_vg5mOoA4QIJoxJK9MfhTLQ",
    "status": "success",
    "amount": 1000,
    "currency": "TZS",
    "provider": "Tigo",
    "external_id": "INV-00123",
    "failure_reason": null,
    "selcom_reference": null,
    "created_at": "2026-06-13T22:31:35Z",
    "updated_at": "2026-06-13T22:31:42Z"
  }
}
```

A failed collection has `"status": "failed"` and `failure_reason` set, e.g.
`"Failed-Insuffient Balance"` (the gateway's spelling).

### `POST {base_url}/disbursements`

Request body:

| Field | Type | Required | Description |
|---|---|---|---|
| `account_number` | string | Yes | Recipient's mobile money number. |
| `amount` | number | Yes | Between 1 and 5,000,000. |
| `provider` | string | Yes | `Airtel`, `Tigo`, `Azampesa`, `Halopesa`, or `Mpesa`. |
| `external_id` | string | Yes | Your unique reference (max 30 chars). |
| `recipient_name` | string | No | Name on the receiving account. |
| `remarks` | string | No | Free-text note. |

```bash
curl -X POST https://your-gateway-domain/api/v1/disbursements \
  -H "X-Public-Key: gw_pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "X-Secret-Key: gw_sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "account_number": "0712345678",
    "amount": 5000,
    "provider": "Tigo",
    "external_id": "PAYOUT-00045",
    "recipient_name": "Juma Hassan",
    "remarks": "Agent commission"
  }'
```

Response — test mode, instant (`200`/`201`):

```json
{
  "success": true,
  "message": "Disbursement processed (test mode - simulated)",
  "data": {
    "uuid": "2d669155-b63e-4461-97c5-c2cb2431a8e8",
    "reference": "dsb_Oty4AbTnH1AprpsIHQAJA",
    "status": "success",
    "amount": 5000,
    "provider": "Tigo",
    "external_id": "PAYOUT-00045"
  }
}
```

Response — production, held for approval (`202 Accepted`):

```json
{
  "success": true,
  "message": "Disbursement request received and is awaiting approval.",
  "data": {
    "uuid": "acbd3bd7-22f8-491c-81b3-41dd3cd902dd",
    "reference": "dsb_6LEnBEbXjVZ58BqS6QaDPw",
    "status": "awaiting_approval",
    "amount": 5000,
    "provider": "Tigo",
    "external_id": "PAYOUT-00045"
  }
}
```

### `GET {base_url}/disbursements/{reference}/status`

Same auth/shape as collection status, keyed by `reference` (not `uuid`).

### Error response shape (all endpoints)

```json
{
  "success": false,
  "message": "Insufficient balance"
}
```

| HTTP status | Meaning | Common causes |
|---|---|---|
| 200 / 201 / 202 | Success | 202 = disbursement queued for approval. |
| 400 | Bad request | Missing/invalid field, invalid phone number, unsupported provider, `external_id` too long, malformed JSON. |
| 401 | Unauthorized | Missing or invalid `X-Public-Key` / `X-Secret-Key`. |
| 402 | Payment required | Insufficient balance for a disbursement/settlement. |
| 403 | Forbidden | Request IP not in your IP whitelist, or KYC required for a production settlement. |
| 404 | Not found | Unknown collection/disbursement uuid/reference for this merchant. |
| 405 | Method not allowed | Wrong HTTP verb for the endpoint. |
| 500 | Server error | Unexpected internal error — retry, contact support if it persists. |

---

## 12. End-to-end example (Flask + webhook)

A complete backend flow: create a collection, return immediately to the
caller, and rely on a webhook to confirm payment (with polling available
as a manual fallback).

```python
import os
from flask import Flask, request, jsonify

from dalipay import (
    Dalipay,
    WebhookHandler,
    WebhookVerificationError,
    DalipayError,
)

app = Flask(__name__)

client = Dalipay(
    public_key=os.environ["DALIPAY_PUBLIC_KEY"],
    secret_key=os.environ["DALIPAY_SECRET_KEY"],
    base_url=os.environ["DALIPAY_BASE_URL"],
)
webhook_handler = WebhookHandler(os.environ["DALIPAY_CALLBACK_SECRET"])


@app.post("/checkout")
def checkout():
    order_id = request.json["order_id"]
    try:
        collection = client.create_collection(
            account_number=request.json["phone_number"],
            amount=request.json["amount"],
            external_id=f"ORDER-{order_id}",
            customer_name=request.json.get("customer_name"),
        )
    except ValueError as e:
        # provider couldn't be guessed — ask the caller to supply it
        return jsonify({"error": str(e)}), 400
    except DalipayError as e:
        return jsonify({"error": e.message}), 502

    # Persist collection.uuid against order_id here, then return.
    return jsonify({"uuid": collection.uuid, "status": collection.status})


@app.post("/webhooks/dalipay")
def dalipay_webhook():
    try:
        payload = webhook_handler.verify_and_parse(
            body=request.get_data(as_text=True),  # RAW body, before Flask parses it
            signature=request.headers.get("X-Signature", ""),
        )
    except WebhookVerificationError:
        return jsonify({"error": "invalid signature"}), 401

    if payload.event == "collection.success":
        # Look up the order by payload.data.external_id and mark it paid.
        pass
    elif payload.event == "collection.failed":
        # Mark the order's payment as failed/cancelled.
        pass

    return jsonify({"received": True}), 200
```

---

## 13. Integration rules / gotchas

- **`base_url` is per-merchant.** Never hardcode a shared host — always
  source it from configuration per deployment.
- **Never expose `secret_key` (or `public_key`) to a client.** Both live
  only on your backend.
- **`external_id` must be ≤30 chars and unique per attempt.** Reusing one
  across a retry after a `failed` collection is not how you retry —
  generate a new `external_id` for each `create_collection` call.
- **`provider` auto-guessing is best-effort.** Tanzanian numbers can be
  ported between carriers; pass `provider` explicitly whenever you
  actually know it (e.g. customer-selected at checkout) instead of
  trusting `guess_provider`. 073/TTCL numbers have no valid provider on
  this API at all.
- **Collections use `uuid` to poll status; disbursements use
  `reference`.** Store the right identifier for each.
- **Webhooks aren't retried by the gateway.** Respond `2xx` fast, and
  still poll for critical flows as a backstop — don't build a system that
  only works if the webhook arrives.
- **Always verify `X-Signature` with a constant-time comparison** before
  trusting a webhook body (`hmac.compare_digest` / `hash_equals`, never
  `==`/`===`).
- **Verify the raw, unparsed request body** for webhook signature
  checking — re-serializing JSON before hashing will not match the
  signature the gateway computed.
- **Test vs. production is determined only by which key pair you use** —
  there's no separate `test_mode` flag to set. Double- and triple-check
  which key pair is loaded before any code path that can reach a real
  phone number.
- **Disbursements in production hold `amount + fee` immediately** and
  require admin approval (`awaiting_approval`) — don't assume `success`
  synchronously in production the way test mode returns it.
- **`is_healthy()` is side-effect-free** (a `GET` on a random,
  virtually-guaranteed-nonexistent uuid) — safe to call in a startup
  check or liveness probe; it never creates a collection/disbursement or
  contacts a phone number.
