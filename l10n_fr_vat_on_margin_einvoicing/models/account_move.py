# Copyright 2026 Moka (https://moka.cloud).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _en16931_margin_lines(self):
        self.ensure_one()
        return self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product" and line._en16931_margin_tax()
        )

    def _prepare_bg23(self, speedy):
        """Declare margin scheme sales as one exempt breakdown per scheme.

        The tax details hold the margin VAT at its own rate, on the margin as a
        base. Neither may appear: the generic breakdown is computed without
        them, and margin sales are added in category E at a nil rate, on the
        amount the customer pays, as their invoice lines declare it.

        Exempt breakdowns are kept apart by exemption reason, as the generic
        code does: the French extended profiles (BR-FREXT-E-01, E-08rev) match
        each one with the lines of the same reason. A margin sale joins the
        breakdown of an ordinary exempt tax only when they share the reason.
        """
        self.ensure_one()
        if speedy["company_no_vat_taxes"]:
            return super()._prepare_bg23(speedy)
        margin_lines = self._en16931_margin_lines()
        if not margin_lines:
            return super()._prepare_bg23(speedy)
        tax_details = speedy["tax_details"]
        generic_speedy = dict(
            speedy,
            tax_details=dict(
                tax_details,
                tax_details={
                    key: values
                    for key, values in tax_details["tax_details"].items()
                    if not self._en16931_is_margin_tax_group(values)
                },
            ),
        )
        bg23, bt110, bt111 = super()._prepare_bg23(generic_speedy)
        base_by_scheme = defaultdict(float)
        for line in margin_lines:
            tax = line._en16931_margin_tax()
            scheme = (tax.unece_vatex_code, tax._en16931_margin_legal_mention())
            base_by_scheme[scheme] += line.price_total
        currency = self.currency_id
        for (vatex_code, vatex_label), base in base_by_scheme.items():
            existing = [
                b for b in bg23 if b["BT-118"] == "E" and b["BT-121"] == vatex_code
            ]
            if existing:
                existing[0]["BT-116"] = currency._en16931_format(
                    float(existing[0]["BT-116"]) + base
                )
                continue
            bg23.append(
                {
                    "BT-116": currency._en16931_format(base),
                    "BT-116-1": currency.name,
                    "BT-117": currency._en16931_format(0),
                    "BT-117-1": currency.name,
                    "BT-118": "E",
                    "BT-119": "%.2f" % 0,
                    "BT-120": vatex_label,
                    "BT-121": vatex_code,
                }
            )
        return bg23, bt110, bt111

    def _en16931_is_margin_tax_group(self, tax_values):
        tax_id = tax_values["group_tax_details"][0]["id"]
        return self.env["account.tax"].browse(tax_id)._is_en16931_margin_tax()

    def _prepare_bg1(self, speedy):
        """State the margin schemes the invoice uses, in one tax mention.

        BR-FR-06 allows a single note with the subject code TXD.
        """
        res = super()._prepare_bg1(speedy)
        mentions = []
        for line in self._en16931_margin_lines():
            mention = line._en16931_margin_tax()._en16931_margin_legal_mention()
            if mention not in mentions:
                mentions.append(mention)
        if mentions:
            res.append({"BT-21": "TXD", "BT-22": " ; ".join(mentions)})
        return res
