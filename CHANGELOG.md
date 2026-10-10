# Changelog

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
