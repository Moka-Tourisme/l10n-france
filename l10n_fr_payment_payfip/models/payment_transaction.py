import logging
import uuid

from odoo import _, api, fields, models
from odoo.tools import float_round
from odoo.exceptions import ValidationError

from ..controllers.main import PayFIPController

_logger = logging.getLogger(__name__)


class PayFIPTransaction(models.Model):
    _inherit = 'payment.transaction'

    # region Fields declaration
    payfip_operation_identifier = fields.Char(
        string='Operation identifier',
        help='Reference of the request of TX as stored in the provider database',
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

    @api.model_create_multi
    def create(self, vals_list):
        txs = super().create(vals_list)
        for tx in txs:
            if tx.provider_id.code != 'payfip':
                continue
            # Reserve a PayFIP operation identifier (idOp) as soon as the transaction is created.
            prec = self.env['decimal.precision'].precision_get('Product Price')
            email = tx.partner_email
            amount = int(float_round(tx.amount * 100.0, prec))
            reference = tx.reference.replace('-', '').replace('/', '').replace('\\', '').strip()
            provider_reference = '%.15d' % int(uuid.uuid4().int % 899999999999999)
            tx.provider_reference = provider_reference
            idop = tx.provider_id.payfip_get_id_op_from_web_service(
                email, amount, reference, provider_reference)
            tx.payfip_operation_identifier = idop
        return txs

    def _get_specific_rendering_values(self, processing_values):
        """ Override of `payment` to return the PayFIP-specific rendering values. """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'payfip':
            return res

        if self.provider_id.state == 'enabled':
            saisie_value = 'W'
        elif self.provider_id.state == 'activation':
            saisie_value = 'X'
        else:
            saisie_value = 'T'

        return {
            'api_url': PayFIPController._payment_url,
            'numcli': self.provider_id.payfip_customer_number,
            'exer': fields.Datetime.now().year,
            'refdet': self.provider_reference,
            'objet': self.reference,
            'montant': self.amount,
            'mel': self.partner_email,
            'urlnotif': self.provider_id.payfip_notification_url,
            'urlredirect': self.provider_id.payfip_redirect_url,
            'saisie': saisie_value,
        }

    @api.model
    def _extract_reference(self, provider_code, payment_data):
        """ Override of `payment` to extract the PayFIP operation identifier (idOp). """
        if provider_code != 'payfip':
            return super()._extract_reference(provider_code, payment_data)
        return payment_data.get('idop')

    @api.model
    def _search_by_reference(self, provider_code, payment_data):
        """ Override of `payment` to find the transaction from the PayFIP operation identifier.

        :raise ValidationError: If the data match no transaction.
        """
        if provider_code != 'payfip':
            return super()._search_by_reference(provider_code, payment_data)

        idop = self._extract_reference(provider_code, payment_data)
        tx = self.search([
            ('payfip_operation_identifier', '=', idop),
            ('provider_code', '=', 'payfip'),
        ])
        if not tx:
            raise ValidationError(
                "PayFIP: " + _("No transaction found matching reference %s.", idop)
            )
        return tx

    def _extract_amount_data(self, payment_data):
        """ Override of `payment` to skip the generic amount validation for PayFIP.

        The paid amount is retrieved from the PayFIP web service inside `_apply_updates` and stored
        on `payfip_amount`. Returning `None` opts out of the framework amount check.
        """
        if self.provider_code != 'payfip':
            return super()._extract_amount_data(payment_data)
        return None

    def _apply_updates(self, payment_data):
        """ Override of `payment` to update the transaction from the PayFIP web service result. """
        if self.provider_code != 'payfip':
            return super()._apply_updates(payment_data)

        idop = payment_data.get('idop')
        data = self.provider_id.payfip_get_result_from_web_service(idop)
        self.provider_reference = data.get('refdet', False)
        result = data.get('resultrans', False)
        payfip_amount = int(data.get('montant', 0)) / 100

        if result in ('P', 'V'):
            self.write({'payfip_state': result, 'payfip_amount': payfip_amount})
            self._set_done()
        elif result == 'A':
            _logger.info(
                "Received notification for PayFIP payment %s: set as canceled", self.reference)
            self.write({'payfip_state': result, 'payfip_amount': payfip_amount})
            self._set_canceled()
        elif result in ('R', 'Z'):
            message = "Received notification for PayFIP payment %s: set as error" % self.reference
            _logger.info(message)
            self.write({'payfip_state': result, 'payfip_amount': payfip_amount})
            self._set_error(message)

    def _cron_check_payfip_transaction_status(self):
        """ Poll PayFIP for the status of transactions that are not in a final state yet. """
        transactions = self.search([
            ('state', 'not in', ['done', 'cancel']),
            ('provider_code', '=', 'payfip'),
        ])
        for transaction in transactions:
            transaction._process(
                'payfip', {'idop': transaction.payfip_operation_identifier})
        return True
