from datetime import datetime, timedelta
import logging
import uuid
from werkzeug import urls

from odoo import _, api, fields, models
from odoo.tools import float_round
from odoo.exceptions import ValidationError

from ..controllers.main import PayFIPController


_logger = logging.getLogger(__name__)


class PayFIPTransaction(models.Model):
    # region Private attributes
    _inherit = 'payment.transaction'
    # endregion

    # region Default methods
    # endregion

    # region Fields declaration
    payfip_operation_identifier = fields.Char(
        string='Operation identifier',
        help='Reference of the request of TX as stored in the acquirer database',
    )

    payfip_return_url = fields.Char(
        string='Return URL',
    )

    payfip_sent_to_webservice = fields.Boolean(
        string="Sent to PayFIP webservice",
        default=False,
    )

    payfip_state = fields.Selection(
        string="PayFIP state",
        selection=[
            ('P', "Effective payment (P)"),
            ('V', "Effective payment (V)"),
            ('A', "Abandoned payment (A)"),
            ('R', "Other cases (R)"),
            ('Z', "Other cases (Z)"),
            ('U', "Unknown"),
        ]
    )

    payfip_amount = fields.Float(
        string="PayFIP amount",
    )

    # endregion

    def create(self, vals):
        res = super(PayFIPTransaction, self).create(vals)
        if res.acquirer_id.provider == 'payfip':
            prec = self.env['decimal.precision'].precision_get('Product Price')
            email = res.partner_email
            amount = int(float_round(res.amount * 100.0, prec))
            reference = res.reference.replace('-', ' ')
            acquirer_reference = '%.15d' % int(
                uuid.uuid4().int % 899999999999999)
            res.acquirer_reference = acquirer_reference
            idop = res.acquirer_id.payfip_get_id_op_from_web_service(
                email, amount, reference, acquirer_reference)
            res.payfip_operation_identifier = idop

        return res

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider != 'payfip':
            return res

        base_url = self.acquirer_id.get_base_url()
        if self.acquirer_id.state == 'enabled':
            saisie_value = 'W'
        elif self.acquirer_id.state == 'activation':
            saisie_value = 'X'
        else:
            saisie_value = 'T'


        return {
            'api_url': PayFIPController._payment_url,
            'numcli': self.acquirer_id.payfip_customer_number,
            'exer': fields.Datetime.now().year,
            'refdet': self.acquirer_reference,
            'objet': self.reference,
            'montant': self.amount,
            'mel': self.partner_email,
            'urlnotif': self.acquirer_id.payfip_notification_url,
            'urlredirect': self.acquirer_id.payfip_redirect_url,
            'saisie': saisie_value,
        }

    @api.model
    def _get_tx_from_feedback_data(self, provider, data):
        """ Override of payment to find the transaction based on Payfip data.

        param str provider: The provider of the acquirer that handled the transaction
        :param dict data: The feedback data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_feedback_data(provider, data)
        if provider != 'payfip':
            return tx

        reference = data
        tx = self.sudo().search(
            [('payfip_operation_identifier', '=', reference), ('provider', '=', 'payfip')])
        if not tx:
            raise ValidationError(
                "PayFIP: " +
                _("No transaction found matching reference %s.", reference)
            )
        return tx

    def _process_feedback_data(self, feedback_data):
        data = self.acquirer_id.payfip_get_result_from_web_service(
            feedback_data)

        refdet = data.get('refdet', False)
        self.acquirer_reference = refdet

        if data.get('code'):
            self._set_pending()

        self.ensure_one()

        result = data.get('resultrans', False)
        if not result:
            self._set_pending()

        payfip_amount = int(data.get('montant', 0)) / 100
        if result in ['P', 'V']:
            self._set_done()
            self.write({
                'payfip_state': result,
                'payfip_amount': payfip_amount,
            })
            return True
        elif result in ['A']:
            message = 'Received notification for PayFIP payment %s: set as canceled' % self.reference
            _logger.info(message)
            self._set_canceled()
            self.write({
                'payfip_state': result,
                'payfip_amount': payfip_amount,
            })
            return True
        elif result in ['R', 'Z']:
            message = 'Received notification for PayFIP payment %s: set as error' % self.reference
            _logger.info(message)
            self._set_error(
                state_message=message
            )
            self.write({
                'payfip_state': result,
                'payfip_amount': payfip_amount,
            })
            return True
