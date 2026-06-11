# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.payment.tests.common import PaymentCommon


class PayFIPCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Keep the customer number to 'dummy' so the `_check_payfip_customer_number` constraint does
        # not reach the real PayFIP SOAP web service during the test setup.
        cls.payfip = cls._prepare_provider('payfip', update_values={
            'payfip_customer_number': 'dummy',
            'payfip_base_url': 'https://www.payfip.gouv.fr/tpa/paiementws.web',
            'payfip_notification_url': '/payment/payfip/ipn',
            'payfip_redirect_url': '/payment/payfip/dpn',
        })

        # Override default values.
        cls.provider = cls.payfip
        cls.currency = cls.currency_euro
