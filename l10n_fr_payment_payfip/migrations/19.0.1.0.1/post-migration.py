import logging
from datetime import timedelta

from odoo import SUPERUSER_ID, api, fields

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Stop polling PayFIP and close the transactions that polling left open.

    The scheduled action asked PayFIP for the result of every unfinished transaction every
    two minutes, forever. PayFIP notifies the result on its own, so it is removed.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref('l10n_fr_payment_payfip.ir_cron_check_payfip_transaction_status', raise_if_not_found=False)
    if cron:
        cron.unlink()

    # Still unfinished after two days: the customer left PayFIP without paying.
    stale = env['payment.transaction'].search([
        ('provider_code', '=', 'payfip'),
        ('state', 'in', ('draft', 'pending')),
        ('create_date', '<', fields.Datetime.now() - timedelta(hours=48)),
    ])
    stale.write({
        'state': 'cancel',
        'state_message': "No result received from PayFIP within 48 hours.",
        'last_state_change': fields.Datetime.now(),
    })
    _logger.info("l10n_fr_payment_payfip: %s stale PayFIP transaction(s) cancelled", len(stale))
