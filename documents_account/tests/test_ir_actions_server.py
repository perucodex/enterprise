from itertools import product
from unittest.mock import patch

from odoo.addons.documents_account.tests.common import DocumentsAccountTestCommon
from odoo.exceptions import ValidationError
from odoo.tests import RecordCapturer
from odoo.tests.common import tagged


@tagged('post_install', '-at_install', 'test_document_bridge')
class TestIrActionsServer(DocumentsAccountTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal_type_labels = dict(
            cls.env['account.journal'].fields_get(['type'], ['selection'])['type']['selection']
        )

    def _run_action_and_assert_sync(self, action, document, expected_journal=None):
        """Execute action and assert that the document was synced to the correct move/journal."""
        with RecordCapturer(self.env['account.move'], []) as capture:
            action.with_context(active_model='documents.document', active_id=document.id).run()

        account_move = capture.records
        if not expected_journal:
            expected_journal = self.env['account.move']._get_suitable_journal_ids(account_move.move_type)[:1]
        expected_folder = self.journal_type_labels[expected_journal.type]

        self.assertEqual(len(account_move), 1)
        self.assertEqual(document.res_model, account_move._name)
        self.assertEqual(document.res_id, account_move.id)
        self.assertEqual(account_move.message_main_attachment_id, document.attachment_id)
        self.assertEqual(account_move.journal_id, expected_journal)
        self.assertEqual(document.folder_id.name, expected_folder)
        self.assertIn(document.tag_ids.name, expected_journal.name)

    def test_documents_account_record_create(self):
        """Test documents_account_record_create action server type (state)."""
        for move_type, with_journal in product(
                ('in_invoice', 'out_invoice', 'in_refund', 'out_refund', 'entry', 'in_receipt'),
                (False, True)):
            with self.subTest(move_type=move_type, with_journal=with_journal):
                default_journal = self.env['account.move']._get_suitable_journal_ids(move_type)[:1]

                action = self.env['ir.actions.server'].create({
                    'name': f'test {move_type}',
                    'model_id': self.env['ir.model']._get_id('documents.document'),
                    'state': 'documents_account_record_create',
                    'documents_account_create_model': f'account.move.{move_type}',
                    'documents_account_journal_id': default_journal.id if with_journal else False,
                    'usage': 'documents_embedded',
                })

                document = self.document_pdf.copy()
                document.folder_id._embed_action(action.id)
                self._run_action_and_assert_sync(
                    action,
                    document,
                    expected_journal=default_journal if with_journal else None
                )

        journal_id = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)
        for with_journal in (False, True):
            with (self.subTest(with_journal=with_journal),
                  patch.object(self.env.registry["documents.document"],
                               'account_create_account_bank_statement', autospec=True) as mock):
                action = self.env['ir.actions.server'].create({
                    'name': 'account.bank.statement',
                    'model_id': self.env['ir.model']._get_id('documents.document'),
                    'state': 'documents_account_record_create',
                    'documents_account_create_model': 'account.bank.statement',
                    'documents_account_journal_id': journal_id.id if with_journal else False,
                    'usage': 'documents_embedded',
                })
                document = self.document_pdf.copy()
                document.folder_id._embed_action(action.id)
                action.with_context({'active_model': 'documents.document', 'active_id': document.id}).run()

                mock.assert_called_once()
                called_args, called_kwargs = mock.call_args
                self.assertEqual(called_args[0], document)
                self.assertEqual(called_kwargs, {'journal_id': journal_id if with_journal else None})

    def test_documents_account_standard_actions(self):
        """Test the pre-configured financial server actions work as expected."""
        account_actions = self.env['ir.actions.server']._get_documents_account_actions_map()
        finance_folder = self.env.ref("documents.document_finance_folder", raise_if_not_found=True)
        document = self.document_pdf.copy()
        document.folder_id = finance_folder

        for action_id in account_actions:
            action = self.env['ir.actions.server'].browse(action_id)
            if action.name == 'Import Bank Statement':
                # Bank statements will only be synced correctly from 19.1.
                continue

            with self.subTest(action_name=action.name):
                self._run_action_and_assert_sync(action, document.copy())

    def test_documents_account_record_create_on_invalid_model(self):
        """Test that calling a documents_account_record_create action on a non-document record does nothing."""
        partner = self.env['res.partner'].create({'name': 'test'})
        with patch.object(self.env.registry["documents.document"], 'account_create_account_bank_statement') as mock:
            action = self.env['ir.actions.server'].create({
                'name': 'account.bank.statement',
                'model_id': self.env['ir.model']._get_id('documents.document'),
                'state': 'documents_account_record_create',
                'documents_account_create_model': 'account.bank.statement',
            })
            action.with_context({'active_model': 'res.partner', 'active_id': partner.id}).run()
            mock.assert_not_called()

    def test_documents_account_record_create_documents_only(self):
        """Test model enforcement on documents_account_record_create server action (can only be applied on Document)."""
        with self.assertRaises(ValidationError, msg='"New Journal Entry" can only be applied to Document.'):
            self.env['ir.actions.server'].create({
                'name': 'Wrong model',
                'model_id': self.env['ir.model']._get_id('res.partner'),
                'state': 'documents_account_record_create',
                'documents_account_create_model': 'account.move.in_invoice',
            })
