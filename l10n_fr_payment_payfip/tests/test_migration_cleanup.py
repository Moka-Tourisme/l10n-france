import importlib.util
from datetime import timedelta
from glob import glob
from os.path import dirname, join
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


_PROVIDER_PATH = 'odoo.addons.l10n_fr_payment_payfip.models.payment_provider.PayFIPProvider'


@tagged('post_install', '-at_install')
class PayFIPCleanupMigrationTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A 'dummy' customer number keeps the constraint from calling the real PayFIP web service.
        cls.provider = cls.env['payment.provider'].create({
            'name': 'PayFIP',
            'code': 'payfip',
            'state': 'test',
            'payfip_customer_number': 'dummy',
            'payfip_base_url': 'https://www.payfip.gouv.fr/tpa/paiementws.web',
            'payfip_notification_url': '/payment/payfip/ipn',
            'payfip_redirect_url': '/payment/payfip/dpn',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Test PayFIP', 'email': 'payfip@example.com'})

    def _create_tx(self, state, age_hours):
        with patch(f'{_PROVIDER_PATH}.payfip_get_id_op_from_web_service', return_value='fake-idop'):
            tx = self.env['payment.transaction'].create({
                'provider_id': self.provider.id,
                'reference': 'PAYFIP-%s-%s' % (state, age_hours),
                'amount': 10.0,
                'currency_id': self.env.company.currency_id.id,
                'partner_id': self.partner.id,
                'payment_method_id': self.env.ref('payment.payment_method_unknown').id,
                'operation': 'online_redirect',
            })
        tx.state = state
        self.env.cr.execute(
            "UPDATE payment_transaction SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(hours=age_hours), tx.id),
        )
        return tx

    def _run_migration(self):
        path = glob(join(dirname(__file__), '..', 'migrations', '*', 'post-migration.py'))[0]
        spec = importlib.util.spec_from_file_location('payfip_post_migration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, None)
        self.env.invalidate_all()

    def test_unfinished_transactions_older_than_48h_are_cancelled(self):
        stale_draft = self._create_tx('draft', 72)
        stale_pending = self._create_tx('pending', 72)
        recent_pending = self._create_tx('pending', 2)
        old_done = self._create_tx('done', 72)
        old_error = self._create_tx('error', 72)

        self._run_migration()

        self.assertEqual(stale_draft.state, 'cancel')
        self.assertEqual(stale_pending.state, 'cancel')
        self.assertEqual(recent_pending.state, 'pending')
        self.assertEqual(old_done.state, 'done')
        self.assertEqual(old_error.state, 'error')

    def test_scheduled_action_is_removed(self):
        cron = self.env['ir.cron'].create({
            'name': 'Check PayFIP Transaction Status',
            'model_id': self.env.ref('payment.model_payment_transaction').id,
            'state': 'code',
            'code': 'pass',
            'interval_number': 2,
            'interval_type': 'minutes',
        })
        self.env['ir.model.data'].create({
            'module': 'l10n_fr_payment_payfip',
            'name': 'ir_cron_check_payfip_transaction_status',
            'model': 'ir.cron',
            'res_id': cron.id,
        })

        self._run_migration()

        self.assertFalse(self.env.ref(
            'l10n_fr_payment_payfip.ir_cron_check_payfip_transaction_status',
            raise_if_not_found=False))
