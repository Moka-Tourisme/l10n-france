from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class PenaltyConfiguration(models.Model):
    _name = 'penalty.configuration'
    _description = "Configuration des pénalités"
    _rec_name = 'display_name'
    _order = 'date_from desc'

    display_name = fields.Char(string="Nom affiché", compute='_compute_display_name', store=True)
    # Voir pour ajouter un champ date qui compte year et month. Le problème c'est que le jour doit être exclu et il n'existe pas de widget pour ça.
    date_from = fields.Date(string="Date", store=True, help="Date de début d'application de la nouvelle règle d'intérêt de retard", required=True)
    date_to = fields.Date(string="Date", store=True, help="Date de fin d'application de la nouvelle règle d'intérêt de retard", required=True)

    legal_rate = fields.Float(string="Taux d'intérêt légal", required=True, help="Le taux d'intérêt légal est fixé par l'État. Veuillez vous renseigner auprès des organismes concernés.")
    coefficient = fields.Float(string="Coefficient sur le taux", required=True, default=3.0, help="Coefficient appliqué au taux d'intérêt légal. Ce coefficient ne peux pas être inférieur à 3.")
    fixed_fee = fields.Float(string="Indemnité forfaitaire", required=True, default=40.0, help="L'indemnité forfaitaire pour frais de recouvrement est fixée par l'Etat. Veuillez vous renseigner auprès des organismes concernés.")

    @api.depends('date_from', 'date_to')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.date_from} / {record.date_to}"

    @api.constrains('coefficient')
    def _check_coefficient(self):
        if self.coefficient < 3:
            raise ValidationError("The coefficient must be at least 3.")

    @api.model
    def get_configuration(self):
        config = self.search([], limit=1)
        if not config:
            config = self.create({
                'name': 'Configuration par défaut',
                'year': 2024,
                'month': 10,
                'legal_rate': 4.92,
                'coefficient': 3.0,
                'fixed_fee': 40.0,
            })

        return config

    @api.constrains('month')
    def _check_month(self):
        for record in self:
            if record.month < 1 or record.month > 12:
                raise UserError("Le mois doit être compris entre 1 et 12.")

    #Check if date_from is before date_to is not overlapping with another configuration
    @api.constrains('date_from', 'date_to')
    def _check_dates_overlap(self):
        for record in self:
            overlapping_configurations = self.search([
                ('id', '!=', record.id),
                ('date_from', '<=', record.date_to),
                ('date_to', '>=', record.date_from),
            ])
            if overlapping_configurations:
                raise ValidationError("Les dates de configuration ne doivent pas se chevaucher.")
