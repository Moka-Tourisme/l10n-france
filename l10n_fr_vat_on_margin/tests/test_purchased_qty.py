from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestMarginPurchasedQty(AccountTestInvoicingCommon):
    """The margin counts what the supplier bills, not what the customer buys.

    35 people sold, 33 billed by the supplier: the purchase side of the margin
    is 33 times the cost. It used to be 35, which understated the margin and
    therefore the VAT due on it.
    """

    @classmethod
    def setUpClass(cls, chart_template_ref="l10n_fr.l10n_fr_pcg_chart_template"):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.env = cls.env(user=cls.env.ref("base.user_root"))
        cls.margin_tax = cls.env["account.tax"].search(
            [
                ("name", "=", "TVA sur marge 20% TTC - Vente"),
                ("company_id", "=", cls.env.company.id),
            ],
            limit=1,
        )
        seller = cls.env["res.partner"].create({"name": "Seller"})
        product = cls.env["product.product"].create(
            {
                "name": "Guided tour",
                "type": "service",
                "service_to_purchase": True,
                "vat_on_margin": True,
                "seller_ids": [(0, 0, {"partner_id": seller.id, "price": 110})],
            }
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.env.ref("base.partner_admin").id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 35,
                            "price_unit": 150,
                            "purchase_price": 110,
                            "tax_id": [(6, 0, cls.margin_tax.ids)],
                        }
                    )
                ],
            }
        )
        cls.line = cls.order.order_line

    def assertMarginBuys(self, bought):
        """Sold price is tax-included: the TTC is 150 per unit sold.

        The sale quantity itself may move with the purchase when another
        module aligns them; what this module decides is the purchase side.
        """
        self.assertAlmostEqual(
            self.line.margin_amount_untaxed,
            150 * self.line.product_uom_qty - 110 * bought,
        )

    def test_margin_follows_purchase_quantity(self):
        self.order.action_confirm()
        # Invoiced first: the sale stays at 35 whatever else is installed, and
        # only the purchase side of the margin can move.
        self.order._create_invoices().action_post()
        purchase_line = self.line.purchase_line_ids
        self.assertEqual(purchase_line.product_qty, 35)
        # Nothing corrected yet: bought what was sold.
        self.assertMarginBuys(35)

        purchase_line.product_qty = 33

        self.assertEqual(self.line.product_uom_qty, 35)
        self.assertMarginBuys(33)
        # The stored VAT follows, not only the totals widget: the margin
        # 150 x 35 - 110 x 33 = 1620 is tax-included, so 1620 x 20 / 120.
        self.assertAlmostEqual(self.order.amount_tax, 270.0)
        # The margin shown on the order says the same: one margin, not two.
        self.assertAlmostEqual(self.line.margin, self.line.price_subtotal - 110 * 33)

    def test_margin_without_purchase_uses_sold_quantity(self):
        self.assertFalse(self.line.purchase_line_ids)
        self.assertAlmostEqual(self.line.margin_amount_untaxed, 150 * 35 - 110 * 35)

    def test_cancelled_purchase_is_not_bought(self):
        self.order.action_confirm()
        self.line.purchase_line_ids.product_qty = 33
        self.line.purchase_line_ids.order_id.button_cancel()
        # Nothing is bought any more: back to what was sold.
        self.assertMarginBuys(self.line.product_uom_qty)

    def test_several_purchase_lines_use_sold_quantity(self):
        self.order.action_confirm()
        self.line.purchase_line_ids.order_id.button_confirm()
        # sale_purchase buys the increase on a second line, then writes the
        # whole sold quantity on it: summing them would buy 75 for 40 sold.
        # The price goes with it: a new quantity reprices from the pricelist.
        self.line.write({"product_uom_qty": 40, "price_unit": 150})
        self.assertEqual(len(self.line.purchase_line_ids), 2)
        self.assertMarginBuys(40)
