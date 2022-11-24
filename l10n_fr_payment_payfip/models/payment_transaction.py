from datetime import datetime, timedelta
import logging
import pytz
import uuid
from werkzeug import urls

from odoo import api, fields, models, _
from odoo.tools import float_round

from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.addons.payment_payfip.controllers.main import PayFIPController
from odoo.addons.payment_payfip.models.inherited_payment_acquirer import PayFIPAcquirer

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

    # region Fields method
    # endregion

    # region Constrains and Onchange
    # endregion
    # region CRUD (overrides)
    def create(self, vals):
        res = super(PayFIPTransaction, self).create(vals)
        if res.acquirer_id.provider == 'payfip':
            prec = self.env['decimal.precision'].precision_get('Product Price')
            email = res.partner_email
            amount = int(float_round(res.amount * 100.0, prec))
            reference = res.reference.replace('-', ' ')
            acquirer_reference = '%.15d' % int(uuid.uuid4().int % 899999999999999)
            res.acquirer_reference = acquirer_reference
            idop = res.acquirer_id.payfip_get_id_op_from_web_service(email, amount, reference, acquirer_reference)
            res.payfip_operation_identifier = idop

        return res

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider != 'payfip':
            return res

        base_url = self.acquirer_id.get_base_url()
        return {
            'api_url': PayFIPController._payment_url,
            'numcli': self.acquirer_id.payfip_customer_number,
            'exer': fields.Datetime.now().year,
            'refdet': self.acquirer_reference,
            'objet': self.reference,
            'montant': self.amount,
            'mel': self.partner_email,
            'urlnotif': urls.url_join("https://tchai.mokatourisme.dev", PayFIPController._notification_url),
            'urlredirect': urls.url_join("https://tchai.mokatourisme.dev", PayFIPController._return_url),
            'saisie': 'W' if self.acquirer_id.state == 'prod' else 'T',
        }

    def _payfip_form_get_tx_from_data(self, idop):
        if not idop:
            error_msg = _('PayFIP: received data with missing idop!')
            _logger.error(error_msg)
            raise ValidationError(error_msg)

        # find tx -> @TDENOTE use txn_id ?
        txs = self.env['payment.transaction'].sudo().search([('payfip_operation_identifier', '=', idop)])

        if not txs or len(txs) > 1:
            error_msg = 'PayFIP: received data for idop %s' % idop
            if not txs:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.error(error_msg)
            raise ValidationError(error_msg)
        return txs[0]

    def _process_feedback_data(self, idop=False):
        data = self.acquirer_id.payfip_get_result_from_web_service(idop)

        if not data:
            return False

        self.ensure_one()

        result = data.get('resultrans', False)
        if not result:
            return False

        payfip_amount = int(data.get('montant', 0)) / 100

        if result in ['P', 'V']:
            message = 'Validated PayFIP payment for tx %s: set as done' % self.reference
            _logger.info(message)

            date_validate = fields.Datetime.now()
            payfip_date = str(data.get('dattrans', ''))
            payfip_datetime = str(data.get('heurtrans', ''))
            if payfip_date and payfip_datetime and len(payfip_date) == 8 and len(payfip_datetime) == 4:
                # Add a minute to validation datetime cause we don't get seconds from webservice and don't want to be
                # in trouble with creation datetime
                day = int(payfip_date[0:2])
                month = int(payfip_date[2:4])
                year = int(payfip_date[4:8])
                hour = int(payfip_datetime[0:2])
                minute = int(payfip_datetime[2:4])
                payfip_tz = pytz.timezone('Europe/Paris')
                td_minute = timedelta(minutes=1)
                date_validate = fields.Datetime.to_string(
                    datetime(year, month, day, hour=hour, minute=minute, tzinfo=payfip_tz) + td_minute
                )

            self.write({
                'state': 'done',
                'amount': payfip_amount,
                'payfip_state': result,
                'payfip_amount': payfip_amount,
            })
            return True
        elif result in ['A']:
            message = 'Received notification for PayFIP payment %s: set as canceled' % self.reference
            _logger.info(message)
            self.write({
                'state': 'cancel',
                'amount': payfip_amount,
                'payfip_state': result,
                'payfip_amount': payfip_amount,
            })
            return True
        elif result in ['R', 'Z']:
            message = 'Received notification for PayFIP payment %s: set as error' % self.reference
            _logger.info(message)
            self.write({
                'state': 'error',
                'amount': payfip_amount,
                'payfip_state': result,
                'state_message': message,
                'payfip_amount': payfip_amount,
            })
            return True
        else:
            message = 'Received unrecognized status for PayFIP payment %s: %s, set as error' % (
                self.reference,
                result
            )
            _logger.error(message)
            self.write({
                'state': 'error',
                'payfip_state': 'U',
                'state_message': message,
            })
            return False

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
        tx = self.sudo().search([('payfip_operation_identifier', '=', reference), ('provider', '=', 'payfip')])
        if not tx:
            raise ValidationError(
                "PayFIP: " + _("No transaction found matching reference %s.", reference)
            )
        return tx
