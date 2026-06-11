# Changelog
All notable changes to this project will be documented in this file.

## [19.0.1.0.0] 2026-06-11
### Migration to Odoo 19.0
- Adapted to the refactored `payment` framework:
  - `_get_tx_from_notification_data` → `_search_by_reference` + `_extract_reference`
  - `_process_notification_data` → `_apply_updates` (+ `_extract_amount_data` opting out
    of the generic amount validation)
  - controller now calls `_process('payfip', payment_data)`
  - `get_next_reference` → `_compute_reference`
- `create` reworked as `@api.model_create_multi`.
- `_get_compatible_providers` rewritten on top of `super()` (no more `osv.expression`).
- Dependencies: removed `website_sale` and the unused `openupgradelib` external
  dependency, and added `account_payment`. In v19 neither `payment` nor `l10n_fr`
  pull `account` anymore, so `account_payment` is now required to provide the
  `account.payment.method` model this module extends. Also dropped dead manifest keys.
- Cleaned dead imports and rewrote the test suite against the v19 payment test helpers.

## [16.0.1] 2024-03-06
### Initialisation of the module.
