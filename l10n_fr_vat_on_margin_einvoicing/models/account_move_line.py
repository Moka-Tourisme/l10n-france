# Copyright 2026 Moka (https://moka.cloud).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero, float_round


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _en16931_margin_tax(self):
        """The margin VAT of the line, if any."""
        self.ensure_one()
        return self._en16931_get_vat_taxes().filtered(
            lambda tax: tax._is_en16931_margin_tax()
        )

    def _check_en16931(self, speedy):
        vat_dict, non_vat_taxes = super()._check_en16931(speedy)
        margin_tax = not speedy["company_no_vat_taxes"] and self._en16931_margin_tax()
        if margin_tax:
            # An archived tax escapes the company check, while an older invoice
            # may still carry it: a wrong setup must not reach the XML.
            errors = margin_tax._en16931_check_sale_tax()
            if errors:
                raise UserError(
                    _(
                        "On invoice '%(inv)s', invoice line '%(inv_line)s': "
                        "%(errors)s",
                        inv=self.move_id.display_name,
                        inv_line=self.display_name,
                        errors=" ".join(errors),
                    )
                )
            vat_dict.update(
                {
                    "vat_rate": 0.0,
                    "vatex_label": margin_tax._en16931_margin_legal_mention(),
                }
            )
        return vat_dict, non_vat_taxes

    def _en16931_margin_line_total(self, non_vat_taxes):
        """Amount of the line under the generic rule, and under the margin one.

        The generic rule takes price_subtotal, which the margin module nets of
        the margin VAT. That VAT is not declared, so the line is worth what the
        customer pays for it.
        """
        generic = self.price_subtotal + sum(x["tax_amount"] for x in non_vat_taxes)
        return generic, self.price_total

    def _prepare_bg25_single_line(self, line_number, totals, speedy):
        vals = super()._prepare_bg25_single_line(line_number, totals, speedy)
        if speedy["company_no_vat_taxes"] or not self._en16931_margin_tax():
            return vals
        non_vat_taxes = self._check_en16931(speedy)[1]
        generic, line_total = self._en16931_margin_line_total(non_vat_taxes)
        totals["BT-106"] += line_total - generic
        # Nothing of the margin tax is declared, so the price excludes the
        # other taxes only, as the generic rule does for every line.
        other_taxes = self.tax_ids - self._en16931_margin_tax()
        gross_price = self.price_unit
        if other_taxes:
            gross_price = other_taxes.compute_all(self.price_unit)["total_excluded"]
        gross_price = float_round(gross_price, precision_digits=speedy["price_prec"])
        if float_is_zero(self.quantity, precision_digits=speedy["qty_prec"]):
            net_price = gross_price * (1 - self.discount / 100.0)
        else:
            net_price = (
                line_total - sum(x["tax_amount"] for x in non_vat_taxes)
            ) / self.quantity
        net_price = float_round(net_price, precision_digits=speedy["price_prec"])
        vals.update(
            {
                "BT-131": self.currency_id._en16931_format(line_total),
                "BT-146": speedy["price_fmt"] % net_price,
                "BT-148": speedy["price_fmt"] % gross_price,
            }
        )
        if (
            float_compare(self.discount, 0, precision_digits=speedy["disc_prec"])
            > 0
        ):
            diff_price = float_round(
                gross_price - net_price, precision_digits=speedy["price_prec"]
            )
            vals["BT-147"] = speedy["price_fmt"] % diff_price
        return vals

    def _prepare_bg20_single_line(self, totals, speedy):
        res = super()._prepare_bg20_single_line(totals, speedy)
        if speedy["company_no_vat_taxes"] or not self._en16931_margin_tax():
            return res
        # The first allowance is the line itself, the next ones its non VAT
        # taxes: those are already in price_total and must not count twice.
        non_vat_taxes = self._check_en16931(speedy)[1]
        bt92 = (self.price_total - sum(x["tax_amount"] for x in non_vat_taxes)) * -1
        totals["BT-107"] += bt92 - self.price_subtotal * -1
        res[0]["BT-92"] = self.currency_id._en16931_format(bt92)
        return res
