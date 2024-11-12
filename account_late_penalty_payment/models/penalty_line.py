from odoo import models, fields, api


class PenaltyLine(models.Model):
    _name = 'penalty.line'
    _description = "Ligne de pénalité"

    move_id = fields.Many2one('account.move', string="Facture associée")
    residual_base = fields.Float(string="Base de calcul", compute="_compute_residual_base", store=True)
    date_period_from = fields.Date(string="Date de début de la période d'intérêt", required=True)
    date_period_to = fields.Date(string="Date de fin de la période d'intérêt", required=True)
    days = fields.Integer(string="Nombre de jours de retard", required=True, compute="_compute_days")
    rate = fields.Float(string="Taux d'intérêt (%)", required=True)
    coefficient = fields.Float(string="Coefficient appliqué", required=True)
    penalty = fields.Float(string="Montant de la pénalité", compute="_compute_penalty")
    fixed_fee = fields.Float(string='Intérêts fixes')
    penalty_line_config_id = fields.Many2one('penalty.configuration', string="Configuration de pénalité")
    currency_id = fields.Many2one('res.currency', string='Devise', related='move_id.currency_id')
    amount_paid = fields.Float(string='Montant payé', default=0.0)
    payment_id = fields.Many2one('account.move.line')

    penalty_interest_invoiced = fields.Boolean(
        string="Intérêts facturés",
        default=False,
        help="Indique si les intérêts de retard ont été facturés.")

    @api.depends('residual_base', 'rate', 'days', 'coefficient')
    def _compute_penalty(self):
        for line in self:
            line.penalty = (line.residual_base * (line.rate * 100) * line.days * line.coefficient) / (365 * 100)

    @api.depends('date_period_from', 'date_period_to')
    def _compute_days(self):
        for line in self:
            line.days = (line.date_period_to - line.date_period_from).days

    @api.depends('move_id.penalty_line_ids', 'residual_base', 'amount_paid')
    def _compute_residual_base(self):
        for line in self.sorted(key=lambda r: r.date_period_from):
            # If its first line residual_base is equal to the amount_total of the move
            # If its not first line, residual_base is equal to the residual_base of the previous line
            penalty_lines = line.move_id.penalty_line_ids.sorted(key=lambda r: r.date_period_from)
            if line.id == self.ids[0]:
                line.residual_base = line.move_id.amount_total
            elif len(line.move_id.penalty_line_ids) > 0:
                # Get the previous ids from the current line
                penalty_line = self.env['penalty.line'].browse(penalty_lines.ids[penalty_lines.ids.index(line.id) - 1])
                line.residual_base = penalty_line.residual_base - line.amount_paid
            else:
                line.residual_base = 0.0
