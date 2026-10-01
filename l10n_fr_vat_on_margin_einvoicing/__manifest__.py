# Copyright 2026 Moka (https://moka.cloud).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "France - VAT on Margin in E-invoices",
    "summary": "Declare margin scheme sales in EN16931 e-invoices",
    "version": "16.0.1.0.0",
    "author": "Moka",
    "website": "https://moka.cloud",
    "license": "AGPL-3",
    "category": "Accounting",
    "depends": [
        "l10n_fr_vat_on_margin",
        "account_invoice_en16931",
    ],
    "installable": True,
    "auto_install": False,
}
