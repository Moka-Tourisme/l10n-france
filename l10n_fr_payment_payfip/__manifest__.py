{
    'name': "Intermédiaire de paiement PayFIP",
    'version': '15.0.1',
    'summary': """Intermédiaire de paiement : Implémentation de PayFIP""",
    'author': "MokaTourisme",
    'website': "http://www.mokatourisme.fr/",
    'license': "AGPL-3",
    'category': 'Accounting',

    'depends': [
        'payment',
        'l10n_fr'
    ],
    'qweb': [],
    'init_xml': [],
    'update_xml': [],
    'data': [
        # Views must be before data to avoid loading issues
        'views/payment_payfip_templates.xml',
        'views/payment_views.xml',
        'data/payment_acquirer.xml',
    ],
    'demo': [
    ],
    'application': False,
    'auto_install': False,
    'installable': True,
}
