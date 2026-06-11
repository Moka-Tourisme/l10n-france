{
    'name': "Intermédiaire de paiement PayFIP",
    'version': '19.0.1.0.0',
    'summary': """Intermédiaire de paiement : Implémentation de PayFIP""",
    'author': "MokaTourisme",
    'website': "http://www.mokatourisme.fr/",
    'license': "AGPL-3",
    'category': 'Accounting',
    'depends': [
        'payment',
        # Bridge payment <-> account: provides `account.payment.method` and the
        # `_get_payment_method_information` mechanism this module extends.
        'account_payment',
        'l10n_fr',
    ],
    'data': [
        # Views must be loaded before data to avoid loading issues.
        'views/payment_payfip_templates.xml',
        'views/payment_views.xml',
        'data/payment_provider_data.xml',
        'data/payment_transaction.xml',
    ],
    'demo': [
    ],
    'application': False,
    'auto_install': False,
    'installable': True,
}
