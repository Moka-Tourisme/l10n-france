# Copyright 2024 Moka - Horvat Damien
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    'name': 'Account Late Penalty Payment',
    'summary': 'generates late payment penalties for customers who are late in paying their invoices',
    'version': '16.0.0.0.1',
    'category': 'Accounting',
    "author": "Moka",
    "website": "https://www.mokatourisme.fr",
    'depends': ['account', 'base', 'account_invoice_overdue_reminder', 'base_setup', 'product', 'uom', 'l10n_fr'],
    'data': [
        'security/ir.model.access.csv',
        'security/penalty_rules.xml',
        'data/product_data.xml',
        'data/penalty_configuration_data.xml',
        'views/res_config_settings_views.xml',
        'views/account_move.xml',
        'data/ir_cron_data.xml',
        'views/penalty_configuration_views.xml',
        'views/penalty_line_views.xml',
        'data/overdue_invoice_reminder_mail_template.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'AGPL-3',
}
