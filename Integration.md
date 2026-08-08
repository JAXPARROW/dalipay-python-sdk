Integration
Overview & authentication
The Collections & Disbursements API lets your backend trigger mobile money checkout prompts (Tigo Pesa, Airtel Money, HaloPesa, AzamPesa) and send payouts, then track their status — either by polling or via webhooks.

Authentication headers
Every request to /api/v1/collections and /api/v1/disbursements must include the API key pair from API keys:

Headers
 Copy
X-Public-Key: gw_pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
X-Secret-Key: gw_sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Content-Type: application/json
Call this API only from your backend — never from a browser, mobile app, or any client the public can inspect. If a key pair is exposed, revoke it immediately from API keys and generate a new one.


Integration
Test vs. production
Every API key pair is tied to one environment. The environment is determined entirely by which key pair you send — there's no separate flag.

gw_pk_test_... / gw_sk_test_...
Collections & settlements are simulated instantly — no real USSD prompt, no real money. Perfect for development and demos.
gw_pk_production_... / gw_sk_production_...
Real money. Triggers an actual USSD prompt on the customer's phone and real AzamPay settlement.
Double-check which key pair you're using before testing against /api/v1/collections with a real phone number — production keys will send a live payment prompt.

Integration
Create a collection
Triggers a mobile money checkout prompt on the customer's phone. The customer confirms or cancels on their device; the final result arrives asynchronously (see Webhooks and status polling).

POST
/api/v1/collections
X-Public-Key / X-Secret-Key
Request body
Field	Type		Description
account_number	string	Required	Customer's mobile money number, e.g. 0712345678.
amount	number	Required	Amount to collect (whole units, e.g. TZS).
currency	string	Optional	Defaults to TZS.
provider	string	Required	Tigo, Airtel, Halopesa, Azampesa, or Mpesa — must match the customer's network.
external_id	string	Required	Your own unique reference for this payment (max 30 chars). Used to reconcile against your records.
customer_name	string	Optional	Customer's name, for your records and receipts.
Example request
bash — cURL
 Copy
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
PHP — cURL
 Copy
$ch = curl_init('https://your-gateway-domain/api/v1/collections');
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        'X-Public-Key: gw_pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
        'X-Secret-Key: gw_sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
        'Content-Type: application/json',
    ],
    CURLOPT_POSTFIELDS => json_encode([
        'account_number' => '0712345678',
        'amount'         => 1000,
        'currency'       => 'TZS',
        'provider'       => 'Tigo',
        'external_id'    => 'INV-00123',
        'customer_name'  => 'Asha Mwakasege',
    ]),
]);

$response = json_decode(curl_exec($ch), true);
curl_close($ch);

// Save $response['data']['uuid'] - you'll need it to check status.
Example response — 201 Created
json
 Copy
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
uuid — the gateway's internal identifier. Store this to poll status.
reference — a human-friendly gateway reference (also shown in the dashboard ledger).
status — always processing immediately after creation; the customer hasn't responded yet.
Integration
Check collection status
Poll this endpoint to find out whether the customer confirmed or cancelled the prompt. For most integrations, webhooks are faster — use polling as a fallback or for an on-demand "refresh" button.

GET
/api/v1/collections/{uuid}/status
X-Public-Key / X-Secret-Key
Example request
bash — cURL
 Copy
curl -X GET "https://your-gateway-domain/api/v1/collections/c4497523-a565-4766-a03d-441b045dc1e8/status" \
  -H "X-Public-Key: gw_pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "X-Secret-Key: gw_sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
Example response — 200 OK
json
 Copy
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
    "created_at": "2026-06-13T22:31:35Z",
    "updated_at": "2026-06-13T22:31:42Z"
  }
}
Possible status values
processing
Awaiting customer response
success
Payment confirmed & balance credited
failed
Cancelled, declined, or expired
A collection can stay processing for up to a few minutes if the customer hasn't actioned the prompt. If your integration needs a hard cutoff, treat anything still processing after ~5 minutes as likely abandoned, while still honoring a late success if it arrives.
Integration
Disbursements API
Send a payout from your gateway balance to a mobile money account — the API equivalent of the dashboard's "Toa Pesa" settlement flow.

POST
/api/v1/disbursements
X-Public-Key / X-Secret-Key
Request body
Field	Type		Description
account_number	string	Required	Recipient's mobile money number.
amount	number	Required	Between 1 and 5,000,000.
provider	string	Required	Airtel, Tigo, Azampesa, Halopesa, or Mpesa.
external_id	string	Required	Your unique reference (max 30 chars).
recipient_name	string	Optional	Name on the receiving account.
remarks	string	Optional	Free-text note.
Example request
bash — cURL
 Copy
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
Example response
json — test mode (instant)
 Copy
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
json — production (202 Accepted)
 Copy
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
In production, the amount + fee is held from your balance immediately and the request waits for platform admin approval — see Settlement & disbursement approvals. Poll status the same way as collections, via GET /api/v1/disbursements/{reference}/status.
Check disbursement status
GET
/api/v1/disbursements/{reference}/status
X-Public-Key / X-Secret-Key
awaiting_approval
Held, queued for admin review
success
Sent to recipient
failed
Send failed, balance refunded
rejected
Declined by admin, balance refunded
Integration
Webhooks
If you configure a webhook URL in Settings, the gateway sends a signed POST request to it whenever a collection resolves — this is the fastest way to know a payment succeeded, without polling.

Setup
In your merchant Settings, set your Webhook URL — an HTTPS endpoint on your server that accepts POST requests.
Note your callback secret, shown alongside the webhook URL — you'll use it to verify the signature on every delivery.
Payload
json — collection.success
 Copy
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
A failed collection sends event: "collection.failed" with data.status: "failed", using the same shape.

Verifying the signature
Every delivery includes an X-Signature header — an HMAC-SHA256 of the raw request body, signed with your callback secret. Always verify it before trusting the payload.

PHP
 Copy
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
Respond with a 2xx status quickly (ideally under a few seconds). If your endpoint is slow or unreachable, the gateway logs the delivery attempt but does not currently retry — use status polling as a backstop for critical flows.
Integration
Status & error codes
Every response includes a top-level success boolean and a human-readable message. Errors follow the same shape:

json — error shape
 Copy
{
  "success": false,
  "message": "Insufficient balance"
}
HTTP status	Meaning	Common causes
200 / 201 / 202	Success	Request accepted & processed (202 = queued for approval).
400	Bad request	Missing/invalid field — e.g. invalid phone number, unsupported provider, external_id too long, malformed JSON.
401	Unauthorized	Missing or invalid X-Public-Key / X-Secret-Key.
402	Payment required	Insufficient balance for a disbursement / settlement.
403	Forbidden	Request IP not in your IP whitelist, or KYC required for a production settlement.
404	Not found	Unknown collection/disbursement UUID for this merchant.
405	Method not allowed	Wrong HTTP verb for the endpoint.
500	Server error	Unexpected internal error — retry, and contact support if it persists.
Validation messages you may see
"external_id is required" / "external_id must be 30 characters or fewer"
"amount must be between 1 and 5,000,000"
"provider must be one of: Airtel, Tigo, Azampesa, Halopesa, Mpesa" (disbursements)
"account_number must be a valid Tanzanian phone number"
"Insufficient balance"
"Production settlements require KYC verification. Please complete KYC first."
Integration
Test console
Use the Collections API Test Console to send real requests against the gateway from your browser — without writing any code — and see the raw JSON response, status, and timing for each call.

Open the live Collections Test Console
dalipay.co.tz/collection.php
Open the live test console linked above, or run your own copy: open collections_test.php (place it anywhere PHP runs, e.g. php -S 0.0.0.0:8090 collections_test.php).
Enter your gateway's Base URL (e.g. http://your-domain/api/v1) and your X-Public-Key / X-Secret-Key from API keys.
Step 1 — Create a collection: fill in a phone number, amount, and provider, then send. Use a test key pair first to confirm everything is wired up before trying production.
Step 2 — Check status: the UUID from a successful create auto-fills here — click "Check status" to poll the result.
This console runs entirely server-side via cURL, so it works from any server that can reach your gateway. If you run it on a different machine than the gateway, make sure that machine's IP is in your IP whitelist (if configured), and that the gateway's port/domain is reachable from it.
Using production keys in the test console sends a real USSD prompt to the phone number you enter. Double-check the key pair and phone number before clicking "Send collection request" in Live mode.