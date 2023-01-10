# Copyright 20212Romain Duciel
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import pytest
from odoo.addons.payment.tests.common import PaymentCommon
from odoo.tests import HttpCase

from odoo.addons.payment_payfip.controllers.main import PayFIPController


class PayFIPCommon(PaymentCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.payfip = cls._prepare_acquirer(
            "payfip",
            update_values={
                "payfip_customer_number": "006382",
                "payfip_form_action_url": "https://www.tipi-client.budget.gouv.fr/tpa/paiementws.web",
            },
        )

        # Override defaults
        cls.acquirer = cls.payfip
        cls.currency = cls.currency_euro


@pytest.mark.skip(
    reason=(
        "No way of currently testing this with pytest-odoo because:\n"
        "* that require an open odoo port\n"
        "* the open port should use the same pgsql transaction\n"
        "* payment.transaction class must be mocked\n\n"
        "Please use odoo --test-enable to launch those test"
    )
)
class PayFIPHttpTest(PayFIPCommon, HttpCase):
    @classmethod
    def setUpClass(cls):
        @classmethod
        def base_url(cls):
            """PayFIPCommon depends on PaymentCommon > PaymentTestUtils
            which define base_url as string method
            """
            return cls.env["ir.config_parameter"].get_param("web.base.url")

        cls.base_url = base_url
        super().setUpClass()

    def setUp(self):
        super().setUp()
        self.PaymentTransaction = self.env["payment.transaction"]
        # _handle_feedback_data is tested in ComNPayTest class test case
        # here we have to ensure end points (return and notify)
        # properly call this method parent method
        # _handle_feedback_data
        # ├── _get_tx_from_feedback_data
        # ├── _process_feedback_data
        # └── _execute_callback
        self.calls = 0

        def handle_feedback_data(_, provider, data):
            self.assertEqual(provider, "payfip")
            self.assertEqual(data, {"idop": "b008a85d-9dc9-49a1-a68d-473c4f76f958"})
            self.calls += 1
            return self.PaymentTransaction.new({"reference": "ABC"})

        self.PaymentTransaction._patch_method(
            "_handle_feedback_data", handle_feedback_data
        )
        self.addCleanup(self.PaymentTransaction._revert_method, "_handle_feedback_data")

    def test_return_get(self):
        url = self._build_url(PayFIPController._return_url)
        response = self.opener.get(url + "?idop=b008a85d-9dc9-49a1-a68d-473c4f76f958")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.calls, 1)
        response = self.opener.post(url, data={"idop": "b008a85d-9dc9-49a1-a68d-473c4f76f958"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.calls, 2)

    def test_notify_post(self):
        url = self._build_url(PayFIPController._notify_url)
        response = self.opener.post(url, data={"idop": "b008a85d-9dc9-49a1-a68d-473c4f76f958"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.calls, 1)


