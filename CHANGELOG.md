# Changelog

## 0.1.2

### Fixed
- `Collection` now keeps **`failure_reason`** - the network/aggregator's own
  wording for why a collection failed (e.g. `"Failed-Insuffient Balance"`,
  `"The balance of customer is not enough for the payment9009"`). The status
  API has always returned it, but `from_dict()` dropped it, so callers could
  only ever see `status="failed"`.
- `CollectionWebhookData` keeps `failure_reason` too. Only some
  `collection.failed` deliveries include it; when it's `None`, call
  `get_collection_status(uuid)`, which does.

### Added
- `selcom_reference` on `Collection` and `CollectionWebhookData` (returned by
  the API, previously dropped).
- `raw` on `Collection`, `Disbursement` and `CollectionWebhookData`: the full
  `data` dict as received, so a field the SDK doesn't model yet is never lost.
  Excluded from `repr` and `==`.
- `tests/test_models.py`, built from real production response shapes.

## 0.1.1

### Fixed
- `guess_provider` / provider auto-detection now covers the prefixes it was
  missing: **063** -> Halopesa, **066** -> Airtel, **070** -> Tigo (Mixx by Yas),
  **072** -> Mpesa. Before this, `create_collection()` / `create_disbursement()`
  without an explicit `provider` raised `ValueError` for every such customer,
  so the request was never sent. Networks were checked against real
  payer-network lookups.

### Added
- `tests/test_providers.py`: prefix table, number formats, the `provider`
  sent in the request body, explicit `provider` overriding the guess, and
  073/TTCL raising before any request is made.

- **077** -> Tigo (was `Azampesa`). 077 is the former Zantel range, now
  Mixx by Yas.

## 0.1.0

- Initial release.
