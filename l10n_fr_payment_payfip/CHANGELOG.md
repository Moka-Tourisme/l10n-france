# Changelog
All notable changes to this project will be documented in this file.

## [18.0.18.0.1] 2026-10-29
### Removed
- The scheduled action "Check PayFIP Transaction Status", which asked PayFIP for the result of every unfinished transaction every 2 minutes. PayFIP notifies us (IPN and return of the customer).
- Unfinished transactions older than 48 hours are cancelled at update.

## [16.0.1] 2024-03-06
### Initialisation of the module.

