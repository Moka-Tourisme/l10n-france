from unittest.mock import patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import PayFIPCommon
from ..controllers.main import PayFIPController

_PROVIDER_PATH = 'odoo.addons.l10n_fr_payment_payfip.models.payment_provider.PayFIPProvider'


@tagged('post_install', '-at_install')
class PayFIPTest(PayFIPCommon):

    def _create_payfip_transaction(self, flow='redirect', idop='fake-idop'):
        """ Create a PayFIP transaction without reaching the real PayFIP web service.

        The `create` override reserves an operation identifier through a SOAP call; it is mocked
        here so the test stays offline.
        """
        with patch(
            f'{_PROVIDER_PATH}.payfip_get_id_op_from_web_service', return_value=idop
        ):
            return self._create_transaction(flow=flow)

    def test_redirect_form_values(self):
        """ The redirect form must expose the values expected by PayFIP. """
        tx = self._create_payfip_transaction()

        processing_values = tx._get_processing_values()
        form_info = self._extract_values_from_html_form(processing_values['redirect_form_html'])

        self.assertEqual(form_info['action'], PayFIPController._payment_url)
        inputs = form_info['inputs']
        self.assertEqual(inputs['numcli'], self.provider.payfip_customer_number)
        self.assertEqual(inputs['exer'], str(fields.Datetime.now().year))
        self.assertEqual(inputs['objet'], self.reference)
        self.assertEqual(inputs['refdet'], tx.provider_reference)
        self.assertEqual(inputs['saisie'], 'T')  # 'test' state -> 'T'.
        self.assertEqual(inputs['mel'], tx.partner_email)

    def test_search_by_reference_raises_when_unknown(self):
        """ An unknown idOp must raise a ValidationError. """
        with self.assertRaises(ValidationError):
            self.env['payment.transaction']._search_by_reference(
                'payfip', {'idop': 'unknown-idop'})

    def test_apply_updates_sets_done(self):
        """ A 'P'/'V' result from the web service marks the transaction as done. """
        tx = self._create_payfip_transaction(idop='idop-done')
        webservice_result = {
            'resultrans': 'P',
            'refdet': '088655675121650',
            'montant': '111111',
        }
        with patch(
            f'{_PROVIDER_PATH}.payfip_get_result_from_web_service',
            return_value=webservice_result,
        ):
            self.env['payment.transaction']._process('payfip', {'idop': 'idop-done'})

        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, '088655675121650')
        self.assertEqual(tx.payfip_state, 'P')
        self.assertEqual(tx.payfip_amount, 1111.11)

    def test_apply_updates_sets_canceled(self):
        """ An 'A' result from the web service marks the transaction as canceled. """
        tx = self._create_payfip_transaction(idop='idop-cancel')
        webservice_result = {'resultrans': 'A', 'refdet': '088655675121651', 'montant': '111111'}
        with patch(
            f'{_PROVIDER_PATH}.payfip_get_result_from_web_service',
            return_value=webservice_result,
        ):
            self.env['payment.transaction']._process('payfip', {'idop': 'idop-cancel'})

        self.assertEqual(tx.state, 'cancel')
        self.assertEqual(tx.payfip_state, 'A')
