from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'


    penalty_active_default = fields.Boolean(
        string="Pénalités actives par défaut", 
        default=False,
        help="Permet de déterminer l'option des pénalités de retard par défaut sur toutes les factures clients.",
        config_parameter='account_late_penalty_payment.penalty_active'
    )