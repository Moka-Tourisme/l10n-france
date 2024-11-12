from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    penalty_active = fields.Boolean(
        string="Pénalités actives",
        default=lambda self: self.env['ir.config_parameter'].search(
            [('key', '=', 'account_late_penalty_payment.penalty_active')]).value,
        help="Indique si cette facture est éligible au calcul des pénalités de retard."
    )
    penalty_line_ids = fields.One2many(
        'penalty.line',
        'move_id',
        string="Lignes de pénalités",
        help="Lignes détaillant les pénalités appliquées à cette facture."
    )
    penalty_invoice_ids = fields.Many2many(
        'account.move',
        'penalty_invoice_rel',
        'move_id',
        'invoice_id',
        string="Factures de pénalités",
        help="Association des lignes de pénalités à leurs factures respectives"
    )

    penalty_invoice_count = fields.Integer(
        compute='_compute_penalty_invoice_count',
        string="Nombre de factures de pénalités",
        help="Invoice(s) ",
        store=True,
    )

    has_penalty_lines_billable = fields.Boolean(
        compute='_compute_has_penalty_lines_billable',
        string="Pénalités facturables",
        help="Indique si une facture contient des lignes de pénalité facturables.",
        store=True,
    )

    penalty_lines_ids_count = fields.Integer(
        compute='_compute_penalty_lines_ids_count',
        string="Nombre de lignes de pénalités",
        help="Nombre de lignes de pénalités créées pour cette facture.",
        store=True,
    )

    @api.depends('penalty_invoice_ids')
    def _compute_penalty_invoice_count(self):
        for record in self:
            record.penalty_invoice_count = len(record.penalty_invoice_ids)

    @api.onchange('payment_ids', 'amount_residual')
    def calculate_penalty(self):
        for record in self:
            if record.penalty_active:
                today = fields.Date.today()
                reconciled_partials = record._get_all_reconciled_invoice_partials()
                # Filter out reconciled partials that are after record.invoice_date_due
                if len(record.penalty_line_ids) == 0 and record.amount_residual > 0:
                    # Get all date of previous payments
                    penalty_config_ids = self.env['penalty.configuration'].search_read([
                        '|',
                        ('date_from', '<', record.invoice_date_due),
                        ('date_from', '<=', today),
                        ('date_to', '>=', record.invoice_date_due),
                    ], order='date_from asc')
                    print("penalty_config_ids", penalty_config_ids)
                    config_list_ids = [config['id'] for config in penalty_config_ids]
                    if len(penalty_config_ids) == 1:
                        penalty_config = self.env['penalty.configuration'].browse(penalty_config_ids[0]['id'])
                        # Check if there is a paiement between record.invoice_date_due and penalty_config_ids[0]['date_to'] in reconciled_partials:
                        reconciled_partials_during = [partial for partial in reconciled_partials if
                                                      record.invoice_date_due <= partial['aml'].date <=
                                                      penalty_config_ids[0]['date_to']]
                        if len(reconciled_partials_during) > 0:
                            # Create a line from record.invoice_date_due to the date of the first payment and so on
                            for i in range(len(reconciled_partials_during)):
                                if i == 0:
                                    print("if == 0")
                                    record.penalty_line_ids = [(0, 0, {
                                        'date_period_from': record.invoice_date_due + timedelta(days=1),
                                        'date_period_to': reconciled_partials_during[i]['aml'].date,
                                        'rate': penalty_config.legal_rate,
                                        'coefficient': penalty_config.coefficient,
                                        'fixed_fee': penalty_config.fixed_fee,
                                        'penalty_line_config_id': penalty_config.id,
                                    })]
                                else:
                                    print("else == 0")
                                    record.penalty_line_ids = [(0, 0, {
                                        'date_period_from': reconciled_partials_during[i - 1]['aml'].date + timedelta(
                                            days=1),
                                        'date_period_to': reconciled_partials_during[i]['aml'].date,
                                        'rate': penalty_config.legal_rate,
                                        'coefficient': penalty_config.coefficient,
                                        'fixed_fee': penalty_config.fixed_fee,
                                        'penalty_line_config_id': penalty_config.id,
                                    })]
                        else:
                            print("1")
                            record.penalty_line_ids = [(0, 0, {
                                'date_period_from': record.invoice_date_due + timedelta(days=1),
                                'date_period_to': penalty_config_ids[0]['date_to'] if today < penalty_config_ids[0][
                                    'date_to'] else today,
                                'rate': penalty_config.legal_rate,
                                'coefficient': penalty_config.coefficient,
                                'fixed_fee': penalty_config.fixed_fee,
                                'penalty_line_config_id': penalty_config.id,
                            })]
                    elif len(penalty_config_ids) > 1:
                        # Create a new penalty line for each configuration where days is date_period_from - penalty_config_ids[i+1].date
                        for i in range(len(penalty_config_ids)):
                            penalty_config = self.env['penalty.configuration'].browse(penalty_config_ids[i]['id'])
                            penalty_line_config_id = penalty_config.id
                            # Check if there is a paiement between penalty_config_ids[i]['date_from'] and penalty_config_ids[i]['date_to'] in reconciled_partials:
                            reconciled_partials_during = [partial for partial in reconciled_partials if
                                                          penalty_config_ids[i]['date_from'] <= partial['aml'].date <=
                                                          penalty_config_ids[i]['date_to']]
                            if len(reconciled_partials_during) > 0:
                                for j in range(len(reconciled_partials_during)):
                                    # Check if there is an existing penalty_line_ids where payment_id = reconciled_partials_during[j]['aml_id']
                                    print("reconciled_partials_during[j]", reconciled_partials_during[j])
                                    if not any(line.payment_id.id == reconciled_partials_during[j]['aml_id'] for line in record.penalty_line_ids):
                                        print("j", j)
                                        if j == 0:
                                            print("j == 0")
                                            record.penalty_line_ids = [(0, 0, {
                                                'date_period_from': penalty_config_ids[i]['date_from'],
                                                'date_period_to': reconciled_partials_during[j]['aml'].date,
                                                'rate': penalty_config.legal_rate,
                                                'coefficient': penalty_config.coefficient,
                                                'fixed_fee': penalty_config.fixed_fee,
                                                'penalty_line_config_id': penalty_line_config_id,
                                            })]
                                            if j < len(reconciled_partials_during) - 1:
                                                print("j < len(reconciled_partials_during) - 1")
                                                # And create another line from the date of the paiement to the end of the period or to the next paiement if there is one
                                                record.penalty_line_ids = [(0, 0, {
                                                    'amount_paid': reconciled_partials_during[j]['amount'],
                                                    'payment_id': reconciled_partials_during[j]['aml_id'],
                                                    'date_period_from': reconciled_partials_during[j][
                                                                            'aml'].date + timedelta(
                                                        days=1),
                                                    'date_period_to': reconciled_partials_during[j + 1]['aml'].date,
                                                    'rate': penalty_config.legal_rate,
                                                    'coefficient': penalty_config.coefficient,
                                                    'fixed_fee': penalty_config.fixed_fee,
                                                    'penalty_line_config_id': penalty_line_config_id,
                                                })]
                                            else:
                                                print("2")
                                                # And create another line from the date of the paiement to the end of the period or to the next paiement if there is one
                                                record.penalty_line_ids = [(0, 0, {
                                                    'date_period_from': reconciled_partials_during[j][
                                                                            'aml'].date + timedelta(
                                                        days=1),
                                                    'date_period_to': penalty_config_ids[i]['date_to'] if today >
                                                                                                          penalty_config_ids[
                                                                                                              i][
                                                                                                              'date_to'] else today,
                                                    'rate': penalty_config.legal_rate,
                                                    'coefficient': penalty_config.coefficient,
                                                    'fixed_fee': penalty_config.fixed_fee,
                                                    'penalty_line_config_id': penalty_line_config_id,
                                                    'amount_paid': reconciled_partials_during[j]['amount'],
                                                    'payment_id': reconciled_partials_during[j]['aml_id'],
                                                })]
                                        else:
                                            # And create another line from the date of the paiement to the end of the period or to the next paiement if there is one
                                            if j < len(reconciled_partials_during) - 1:
                                                print("j < len(reconciled_partials_during) - 1 2")
                                                record.penalty_line_ids = [(0, 0, {
                                                    'amount_paid': reconciled_partials_during[j]['amount'],
                                                    'payment_id': reconciled_partials_during[j]['aml_id'],
                                                    'date_period_from': reconciled_partials_during[j][
                                                                            'aml'].date + timedelta(days=1),
                                                    'date_period_to': reconciled_partials_during[j+1]['aml'].date,
                                                    'rate': penalty_config.legal_rate,
                                                    'coefficient': penalty_config.coefficient,
                                                    'fixed_fee': penalty_config.fixed_fee,
                                                    'penalty_line_config_id': penalty_line_config_id,
                                                })]
                                            else:
                                                print("3")
                                                record.penalty_line_ids = [(0, 0, {
                                                    'date_period_from': reconciled_partials_during[j]['aml'].date + timedelta(
                                                        days=1),
                                                    'date_period_to': penalty_config_ids[i]['date_to'] if today >
                                                                                                          penalty_config_ids[i][
                                                                                                              'date_to'] else today,
                                                    'rate': penalty_config.legal_rate,
                                                    'coefficient': penalty_config.coefficient,
                                                    'fixed_fee': penalty_config.fixed_fee,
                                                    'penalty_line_config_id': penalty_line_config_id,
                                                    'amount_paid': reconciled_partials_during[j]['amount'],
                                                    'payment_id': reconciled_partials_during[j]['aml_id'],
                                                })]
                            else:
                                print("4")
                                record.penalty_line_ids = [(0, 0, {
                                    'date_period_from': penalty_config_ids[i]['date_from'],
                                    'date_period_to': penalty_config_ids[i]['date_to'] if today > penalty_config_ids[i][
                                        'date_to'] else today,
                                    'rate': penalty_config.legal_rate,
                                    'coefficient': penalty_config.coefficient,
                                    'fixed_fee': penalty_config.fixed_fee,
                                    'penalty_line_config_id': penalty_line_config_id,
                                })]
                elif len(record.penalty_line_ids) > 0 and record.amount_residual > 0:
                    # Get the last paiement date
                    last_payment_date = []
                    if len(reconciled_partials) > 0:
                        last_payment_date = reconciled_partials[-1]['aml'].date
                        if not any(line.payment_id.id == reconciled_partials[-1]['aml_id'] for line in record.penalty_line_ids):
                            # Check if there is a penalty_line_ids with date_period_to < last_payment_date
                            if last_payment_date == today:
                                # Get the penalty_config_ids that correspond to today
                                penalty_config_id = self.env['penalty.configuration'].search_read([
                                    ('date_from', '<=', today),
                                    ('date_to', '>=', today),
                                ], order='date_from asc')
                                # Update the last penalty_line_ids with date_period_to = today
                                record.penalty_line_ids[-1].date_period_to = today
                                # Create a new penalty_line_ids with date_period_from = today and date_period_to = today + timedelta(days=1)
                                print("5")
                                record.penalty_line_ids = [(0, 0, {
                                    'amount_paid': reconciled_partials[-1]['amount'],
                                    'payment_id': reconciled_partials[-1]['aml_id'],
                                    'date_period_from': today + timedelta(days=1),
                                    'date_period_to': today + timedelta(days=1),
                                    'rate': penalty_config_id[0]['legal_rate'],
                                    'coefficient': penalty_config_id[0]['coefficient'],
                                    'fixed_fee': penalty_config_id[0]['fixed_fee'],
                                    'penalty_line_config_id': penalty_config_id[0]['id'],
                                })]
                            # If last_payment_date is prior to today then check if there is a penalty_line_ids that have a date_period_to < last_payment_date and update it and for penalty_line_ids that have the closest date_period_to to last_payment_date create a new line with date_period_from = last_payment_date + timedelta(days=1) and date_period_to = today
                            elif last_payment_date < today:
                                # Get the penalty_line_ids where last_payment_date is between date_period_from and date_period_to
                                penalty_lines = record.penalty_line_ids.filtered(
                                    lambda line: line.date_period_from <= last_payment_date <= line.date_period_to)
                                penalty_config_id = self.env['penalty.configuration'].search_read([
                                    ('date_from', '<=', reconciled_partials[-1]['aml'].date),
                                    ('date_to', '>=', reconciled_partials[-1]['aml'].date),
                                ], order='date_from asc', limit=1)
                                if len(penalty_lines) > 0:
                                    penalty_lines.update({
                                        'date_period_to': last_payment_date,
                                    })
                                    print("6")
                                    print("reconciled_partials[-1]", reconciled_partials[-1])
                                    # Create a new line with date_period_from = last_payment_date + timedelta(days=1) and date_period_to = today
                                    record.penalty_line_ids = [(0, 0, {
                                        'date_period_from': last_payment_date + timedelta(days=1),
                                        'date_period_to': record.penalty_line_ids.filtered(
                                            lambda line: line.date_period_from > last_payment_date)[0].date_period_from - timedelta(days=1) if len(record.penalty_line_ids.filtered(
                                            lambda line: line.date_period_from > last_payment_date)) > 0 else penalty_config_id[0]['date_to'] if today > penalty_config_id[0]['date_to'] else today,
                                        'rate': penalty_config_id[0]['legal_rate'],
                                        'coefficient': penalty_config_id[0]['coefficient'],
                                        'fixed_fee': penalty_config_id[0]['fixed_fee'],
                                        'penalty_line_config_id': penalty_config_id[0]['id'],
                                        'amount_paid': reconciled_partials[-1]['amount'],
                                        'payment_id': reconciled_partials[-1]['aml_id'],
                                    })]




    @api.model
    def _cron_calculate_penalties(self):
        today = fields.Date.today()
        _logger.info("Calcul des pénalités pour le %s", today)

        overdue_moves = self.search([
            ('invoice_date_due', '<', today),
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0),
            ('penalty_active', '=', True)
        ])

        _logger.info("Factures en retard trouvées: %s", len(overdue_moves))

        for move in overdue_moves:
            move.calculate_penalty()

    def create_penalty_invoice(self):
        if not self.penalty_active:
            raise UserError("Les pénalités ne sont pas actives pour cette facture.")

        penalty_lines = self.penalty_line_ids.filtered(
            lambda line: not line.penalty_interest_invoiced
        )

        if not penalty_lines:
            raise UserError("Aucune ligne de pénalité non facturée disponible pour la facturation.")

        # Create an invoice with the sum of the penalty lines
        invoice_lines = [(0, 0, {
            'product_id': self.env.ref('account_late_penalty_payment.product_penalty').id,
            'quantity': 1,
            'price_unit': sum(penalty_line.penalty for penalty_line in penalty_lines),
            'name': f"Intérêts pour la facture {self.name}",
        })]
        invoice_lines.append((0, 0, {
            'product_id': self.env.ref('account_late_penalty_payment.product_fixed_fee').id,
            'quantity': 1,
            'price_unit': sum(penalty_line.fixed_fee for penalty_line in penalty_lines),
            'name': f"Forfait de pénalité pour la facture {self.name}",
        }))

        invoice_vals = {
            'partner_id': self.partner_id.id,
        }
        invoice_vals['invoice_line_ids'] = invoice_lines

        penalty_invoice = self.env['account.move'].create(invoice_vals)
        penalty_lines.write({'penalty_interest_invoiced': True})

        self.penalty_invoice_ids = [(4, penalty_invoice.id)]

        return {
            'name': "Facture de pénalité",
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': penalty_invoice.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    @api.depends('payment_ids', 'amount_residual', 'overdue_reminder_counter')
    def _compute_penalty_lines_ids_count(self):
        for record in self:
            record.calculate_penalty()
            record.penalty_lines_ids_count = len(record.penalty_line_ids)

    def view_penalty_invoice(self):
        return {
            'name': "Factures de pénalités",
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'domain': [('id', 'in', self.penalty_invoice_ids.ids)],
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    @api.depends('penalty_line_ids')
    def _compute_has_penalty_lines_billable(self):
        for record in self:
            record.has_penalty_lines_billable = any(
                penalty_line.penalty_interest_invoiced for penalty_line in record.penalty_line_ids)

    def update_penalty_lines(self):
        for record in self:
            record.calculate_penalty()
