# Copyright 2026 Moka (https://moka.cloud).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models

# VAT exemption reasons of the margin schemes, with the wording art. 242 nonies A
# of annex II of the CGI requires on the invoice. Kept in French on purpose: the
# law prescribes these exact words, whatever the language of the customer.
MARGIN_VATEX_LEGAL_MENTIONS = {
    "VATEX-EU-D": "Régime particulier – Agences de voyages",
    "VATEX-EU-F": "Régime particulier – Biens d'occasion",
    "VATEX-EU-I": "Régime particulier – Objets d'art",
    "VATEX-EU-J": "Régime particulier – Objets de collection et d'antiquités",
}


class AccountTax(models.Model):
    _inherit = "account.tax"

    def _is_en16931_margin_tax(self):
        """Whether the tax is a VAT on margin, declared exempt in EN16931.

        Under a margin scheme the invoice shows no VAT, and the customer cannot
        deduct any, so the e-invoice declares the sale in category E at a nil
        rate, whatever rate the margin itself bears.

        The flag is what the tax engine of l10n_fr_vat_on_margin reads to tax
        the margin, so it is the only criterion; the check below refuses a tax
        whose computation disagrees with it.
        """
        self.ensure_one()
        return self.vat_on_margin

    def _en16931_margin_legal_mention(self):
        self.ensure_one()
        return MARGIN_VATEX_LEGAL_MENTIONS[self.unece_vatex_code]

    def _en16931_check_sale_tax(self):
        self.ensure_one()
        is_margin_computation = self.amount_type == "margin_percentage"
        if not (self.vat_on_margin or is_margin_computation):
            return super()._en16931_check_sale_tax()
        if self.vat_on_margin != is_margin_computation:
            return [
                _(
                    "Tax '%(tax)s' must have both the 'VAT on Margin' option and "
                    "the 'Margin Percentage' computation, or neither.",
                    tax=self.display_name,
                )
            ]
        if self.unece_type_code != "VAT":
            return super()._en16931_check_sale_tax()
        # The generic check demands a 'percent' computation and a nil rate in
        # category E, which a margin tax can never satisfy.
        if (
            self.unece_categ_code != "E"
            or self.unece_vatex_code not in MARGIN_VATEX_LEGAL_MENTIONS
        ):
            return [
                _(
                    "VAT on margin tax '%(tax)s' must have the UNECE Tax Category "
                    "'E' and the VAT Exemption Reason of its margin scheme: "
                    "%(reasons)s.",
                    tax=self.display_name,
                    reasons=", ".join(MARGIN_VATEX_LEGAL_MENTIONS),
                )
            ]
        return []
