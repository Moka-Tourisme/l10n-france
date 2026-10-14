# Copyright 2026 Moka (https://moka.cloud).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestEinvoicingMargin(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref="l10n_fr.l10n_fr_pcg_chart_template"):
        super().setUpClass(chart_template_ref=chart_template_ref)
        company = cls.company_data["company"]
        fr = cls.env.ref("base.fr")
        company.write(
            {
                "country_id": fr.id,
                "street": "1 rue du Château",
                "zip": "67000",
                "city": "Strasbourg",
                "vat": "FR23334175221",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Office de Tourisme de Colmar",
                "is_company": True,
                "country_id": fr.id,
                "street": "32 cours Sainte-Anne",
                "zip": "68000",
                "city": "Colmar",
                "vat": "FR40303265045",
            }
        )
        ref = cls.env.ref
        cls.vat_type = ref("account_tax_unece.tax_type_vat")
        cls.categ_s = ref("account_tax_unece.tax_categ_s")
        cls.categ_e = ref("account_tax_unece.tax_categ_e")
        cls.vatex_d = ref("account_tax_unece.tax_vatex_eu_d")
        cls.vatex_132 = ref("account_tax_unece.tax_vatex_eu_132")
        # Give every sale tax of the company a valid EN16931 setup, so that the
        # company-wide check only judges the margin taxes.
        sale_taxes = cls.env["account.tax"].search(
            [("company_id", "=", company.id), ("type_tax_use", "=", "sale")]
        )
        # The common test data adds a group of taxes, which EN16931 refuses.
        groups = sale_taxes.filtered(lambda t: t.amount_type == "group")
        groups.active = False
        sale_taxes -= groups
        cls.margin_taxes = sale_taxes.filtered("vat_on_margin")
        for tax in sale_taxes - cls.margin_taxes:
            vals = {"unece_type_id": cls.vat_type.id}
            if tax.amount > 0:
                vals.update({"unece_categ_id": cls.categ_s.id, "unece_vatex_id": False})
            else:
                vals.update(
                    {"unece_categ_id": cls.categ_e.id, "unece_vatex_id": cls.vatex_132.id}
                )
            tax.write(vals)
        cls.margin_taxes.write(
            {
                "unece_type_id": cls.vat_type.id,
                "unece_categ_id": cls.categ_e.id,
                "unece_vatex_id": cls.vatex_d.id,
            }
        )
        cls.margin_tax = cls.margin_taxes.filtered(lambda t: t.amount == 20)
        cls.vat_20 = (sale_taxes - cls.margin_taxes).filtered(
            lambda t: t.amount == 20
            and t.amount_type == "percent"
            and not t.price_include
        )[:1]
        cls.exempt_tax = (sale_taxes - cls.margin_taxes).filtered(
            lambda t: t.unece_categ_id == cls.categ_e
        )[:1]
        assert cls.margin_tax and cls.vat_20 and cls.exempt_tax
        cls.trip = cls.env["product.product"].create(
            {"name": "Séjour découverte Alsace", "detailed_type": "service"}
        )
        cls.guide = cls.env["product.product"].create(
            {"name": "Guide papier Route des vins", "detailed_type": "consu"}
        )

    def _invoice(self, lines, move_type="out_invoice"):
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "invoice_date": "2026-10-01",
                "invoice_line_ids": [Command.create(vals) for vals in lines],
            }
        )

    def _trip_line(self, purchase_price=900.0, price_unit=1200.0, quantity=2):
        return {
            "product_id": self.trip.id,
            "quantity": quantity,
            "price_unit": price_unit,
            "purchase_price": purchase_price,
            "tax_ids": [Command.set(self.margin_tax.ids)],
        }

    def _guide_line(self):
        return {
            "product_id": self.guide.id,
            "quantity": 3,
            "price_unit": 24.0,
            "tax_ids": [Command.set(self.vat_20.ids)],
        }

    def _assert_totals_consistent(self, invoice, vals):
        """BR-CO-10 to BR-CO-16: lines add up, net plus VAT is the total."""
        lines = sum(float(line["BT-131"]) for line in vals["BG-25"])
        allowances = sum(float(a["BT-92"]) for a in vals["BG-20"])
        self.assertAlmostEqual(float(vals["BT-106"]), lines, places=2)
        self.assertAlmostEqual(
            float(vals["BT-109"]), float(vals["BT-106"]) - allowances, places=2
        )
        self.assertAlmostEqual(
            float(vals["BT-110"]),
            sum(float(b["BT-117"]) for b in vals["BG-23"]),
            places=2,
        )
        self.assertAlmostEqual(
            float(vals["BT-109"]) + float(vals["BT-110"]),
            float(vals["BT-112"]),
            places=2,
        )
        self.assertEqual(
            vals["BT-112"], invoice.currency_id._en16931_format(invoice.amount_total)
        )
        self.assertAlmostEqual(
            float(vals["BT-109"]),
            sum(float(b["BT-116"]) for b in vals["BG-23"]),
            places=2,
        )
        # BR-S-08, and BR-FREXT-E-08rev for the exempt category: each breakdown
        # base is the sum of the lines of its category, rate and exemption
        # reason.
        bases = {}
        for line in vals["BG-25"]:
            key = (line["BT-151"], line["BT-152"], line["EXT-FR-FE-179"] or None)
            bases[key] = bases.get(key, 0.0) + float(line["BT-131"])
        for allowance in vals["BG-20"]:
            key = (allowance["BT-95"], allowance["BT-96"], allowance["BT-174"] or None)
            bases[key] = bases.get(key, 0.0) - float(allowance["BT-92"])
        self.assertEqual(len(bases), len(vals["BG-23"]))
        for breakdown in vals["BG-23"]:
            key = (breakdown["BT-118"], breakdown["BT-119"], breakdown["BT-121"] or None)
            self.assertAlmostEqual(float(breakdown["BT-116"]), bases[key], places=2)

    def _margin_breakdown(self, vals):
        return [b for b in vals["BG-23"] if b["BT-118"] == "E"]

    # Configuration check

    def test_check_passes_with_margin_tax_exempt(self):
        self.assertTrue(self.margin_taxes.filtered("active"))
        self.company_data["company"]._en16931_checks()

    def test_check_refuses_margin_tax_standard_category(self):
        self.margin_tax.unece_categ_id = self.categ_s
        self.margin_tax.unece_vatex_id = False
        with self.assertRaisesRegex(UserError, "VATEX-EU-D"):
            self.company_data["company"]._en16931_checks()

    def test_check_refuses_margin_tax_without_reason(self):
        self.margin_tax.unece_vatex_id = False
        with self.assertRaisesRegex(UserError, "VATEX-EU-D"):
            self.company_data["company"]._en16931_checks()

    def test_check_refuses_margin_tax_other_reason(self):
        self.margin_tax.unece_vatex_id = self.vatex_132
        with self.assertRaisesRegex(UserError, "VATEX-EU-D"):
            self.company_data["company"]._en16931_checks()

    def test_check_keeps_other_taxes_strict(self):
        self.vat_20.unece_vatex_id = self.vatex_132
        with self.assertRaises(UserError):
            self.company_data["company"]._en16931_checks()

    # XML content

    def test_margin_only_invoice(self):
        invoice = self._invoice([self._trip_line()])
        invoice.action_post()
        line = invoice.invoice_line_ids
        self.assertAlmostEqual(line.price_total, 2400.0)
        self.assertAlmostEqual(line.price_subtotal, 2300.0)
        vals = invoice._generate_en16931_dict()
        self.assertEqual(len(vals["BG-23"]), 1)
        breakdown = vals["BG-23"][0]
        self.assertEqual(breakdown["BT-118"], "E")
        self.assertEqual(breakdown["BT-119"], "0.00")
        self.assertEqual(breakdown["BT-117"], "0.00")
        self.assertEqual(breakdown["BT-116"], "2400.00")
        self.assertEqual(breakdown["BT-121"], "VATEX-EU-D")
        self.assertEqual(
            breakdown["BT-120"], "Régime particulier – Agences de voyages"
        )
        bg25 = vals["BG-25"][0]
        self.assertEqual(bg25["BT-131"], "2400.00")
        self.assertEqual(bg25["BT-146"], "1200.00")
        self.assertEqual(bg25["BT-148"], "1200.00")
        self.assertEqual(bg25["BT-151"], "E")
        self.assertEqual(bg25["BT-152"], "0.00")
        self.assertEqual(bg25["EXT-FR-FE-179"], "VATEX-EU-D")
        self.assertEqual(vals["BT-110"], "0.00")
        self._assert_totals_consistent(invoice, vals)

    def test_mixed_invoice(self):
        invoice = self._invoice([self._trip_line(), self._guide_line()])
        invoice.action_post()
        vals = invoice._generate_en16931_dict()
        by_categ = {b["BT-118"]: b for b in vals["BG-23"]}
        self.assertEqual(sorted(by_categ), ["E", "S"])
        self.assertEqual(by_categ["S"]["BT-119"], "20.00")
        self.assertEqual(by_categ["S"]["BT-116"], "72.00")
        self.assertEqual(by_categ["S"]["BT-117"], "14.40")
        self.assertEqual(by_categ["E"]["BT-116"], "2400.00")
        self.assertEqual(by_categ["E"]["BT-117"], "0.00")
        self.assertEqual(vals["BT-110"], "14.40")
        self._assert_totals_consistent(invoice, vals)

    def test_margin_taxes_of_several_rates_share_one_breakdown(self):
        margin_10 = self.margin_taxes.filtered(lambda t: t.amount == 10)
        other = dict(self._trip_line(), tax_ids=[Command.set(margin_10.ids)])
        invoice = self._invoice([self._trip_line(), other])
        invoice.action_post()
        vals = invoice._generate_en16931_dict()
        breakdown = self._margin_breakdown(vals)
        self.assertEqual(len(breakdown), 1)
        self.assertEqual(breakdown[0]["BT-116"], "4800.00")
        self._assert_totals_consistent(invoice, vals)

    def test_nil_and_negative_margin(self):
        for purchase_price in (1200.0, 1300.0):
            invoice = self._invoice([self._trip_line(purchase_price=purchase_price)])
            invoice.action_post()
            self.assertAlmostEqual(invoice.amount_total, 2400.0)
            vals = invoice._generate_en16931_dict()
            breakdown = self._margin_breakdown(vals)
            self.assertEqual(len(breakdown), 1)
            self.assertEqual(breakdown[0]["BT-116"], "2400.00")
            self.assertEqual(vals["BG-25"][0]["BT-131"], "2400.00")
            self._assert_totals_consistent(invoice, vals)

    def test_refund(self):
        refund = self._invoice(
            [self._trip_line(), self._guide_line()], move_type="out_refund"
        )
        refund.action_post()
        vals = refund._generate_en16931_dict()
        by_categ = {b["BT-118"]: b for b in vals["BG-23"]}
        self.assertEqual(by_categ["E"]["BT-116"], "2400.00")
        self.assertEqual(by_categ["S"]["BT-117"], "14.40")
        self.assertEqual(vals["BT-112"], "2486.40")
        self._assert_totals_consistent(refund, vals)

    def test_negative_margin_line_is_an_allowance(self):
        discount = self._trip_line(purchase_price=0.0, price_unit=-100.0, quantity=1)
        invoice = self._invoice([self._trip_line(), discount, self._guide_line()])
        invoice.action_post()
        vals = invoice._generate_en16931_dict()
        self.assertEqual(vals["BG-20"][0]["BT-92"], "100.00")
        self.assertEqual(vals["BG-20"][0]["BT-95"], "E")
        self.assertEqual(vals["BG-20"][0]["BT-96"], "0.00")
        self.assertEqual(self._margin_breakdown(vals)[0]["BT-116"], "2300.00")
        self._assert_totals_consistent(invoice, vals)

    def test_invoice_without_margin_is_unchanged(self):
        invoice = self._invoice([self._guide_line()])
        invoice.action_post()
        vals = invoice._generate_en16931_dict()
        self.assertEqual(len(vals["BG-23"]), 1)
        self.assertEqual(vals["BG-23"][0]["BT-118"], "S")
        self.assertEqual(vals["BG-23"][0]["BT-117"], "14.40")
        self.assertEqual(vals["BG-25"][0]["BT-131"], "72.00")
        self.assertEqual(vals["BT-110"], "14.40")
        self.assertFalse(
            [n for n in vals["BG-1"] if "Régime particulier" in (n["BT-22"] or "")]
        )

    def test_legal_note(self):
        invoice = self._invoice([self._trip_line(), self._guide_line()])
        invoice.action_post()
        vals = invoice._generate_en16931_dict()
        notes = [n["BT-22"] for n in vals["BG-1"] if n["BT-21"] == "TXD"]
        self.assertEqual(notes, ["Régime particulier – Agences de voyages"])

    def test_margin_and_exempt_lines_keep_their_reasons(self):
        insurance = {
            "name": "Assurance annulation",
            "quantity": 1,
            "price_unit": 50.0,
            "tax_ids": [Command.set(self.exempt_tax.ids)],
        }
        invoice = self._invoice([self._trip_line(), insurance])
        invoice.action_post()
        vals = invoice._generate_en16931_dict()
        by_reason = {b["BT-121"]: b for b in self._margin_breakdown(vals)}
        self.assertEqual(sorted(by_reason), ["VATEX-EU-132", "VATEX-EU-D"])
        self.assertEqual(by_reason["VATEX-EU-D"]["BT-116"], "2400.00")
        self.assertEqual(by_reason["VATEX-EU-132"]["BT-116"], "50.00")
        self._assert_totals_consistent(invoice, vals)

    def test_two_margin_schemes(self):
        margin_10 = self.margin_taxes.filtered(lambda t: t.amount == 10)
        margin_10.unece_vatex_id = self.env.ref("account_tax_unece.tax_vatex_eu_f")
        second_hand = dict(
            self._trip_line(purchase_price=300.0, price_unit=500.0, quantity=1),
            tax_ids=[Command.set(margin_10.ids)],
        )
        invoice = self._invoice([self._trip_line(), second_hand])
        invoice.action_post()
        vals = invoice._generate_en16931_dict()
        by_reason = {b["BT-121"]: b for b in self._margin_breakdown(vals)}
        self.assertEqual(by_reason["VATEX-EU-D"]["BT-116"], "2400.00")
        self.assertEqual(by_reason["VATEX-EU-F"]["BT-116"], "500.00")
        self.assertEqual(
            by_reason["VATEX-EU-F"]["BT-120"], "Régime particulier – Biens d'occasion"
        )
        notes = [n["BT-22"] for n in vals["BG-1"] if n["BT-21"] == "TXD"]
        self.assertEqual(len(notes), 1)
        self.assertIn("Agences de voyages", notes[0])
        self.assertIn("Biens d'occasion", notes[0])
        self._assert_totals_consistent(invoice, vals)

    def test_check_refuses_inconsistent_margin_flags(self):
        # The tax engine taxes the margin on vat_on_margin alone: a tax where
        # the flag and the computation disagree is declared one way and posted
        # the other.
        self.margin_tax.vat_on_margin = False
        self.assertTrue(self.margin_tax._en16931_check_sale_tax())
        self.margin_tax.write({"vat_on_margin": True, "amount_type": "percent"})
        self.assertTrue(self.margin_tax._en16931_check_sale_tax())

    def test_discount_on_margin_line(self):
        invoice = self._invoice([dict(self._trip_line(), discount=10.0)])
        invoice.action_post()
        self.assertAlmostEqual(invoice.invoice_line_ids.price_total, 2160.0)
        vals = invoice._generate_en16931_dict()
        line = vals["BG-25"][0]
        self.assertEqual(line["BT-131"], "2160.00")
        self.assertEqual(line["BT-148"], "1200.00")
        self.assertEqual(line["BT-146"], "1080.00")
        self.assertEqual(line["BT-147"], "120.00")
        self._assert_totals_consistent(invoice, vals)

    def test_misconfigured_archived_margin_tax_is_refused(self):
        # An archived tax escapes the company check, but an older invoice may
        # still carry it.
        invoice = self._invoice([self._trip_line()])
        invoice.action_post()
        self.margin_tax.write(
            {"unece_categ_id": self.categ_s.id, "unece_vatex_id": False, "active": False}
        )
        with self.assertRaises(UserError):
            invoice._generate_en16931_dict()
