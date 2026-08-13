from datetime import date, timedelta

import odoo
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'financial')
class UniCoreOnlinePaymentTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        cls.faculty = cls.env['unicore.faculty'].create({
            'name': 'Test Faculty of Business',
            'code': 'TFB',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['unicore.department'].create({
            'name': 'Test Commerce',
            'code': 'TCOM',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['unicore.program'].create({
            'name': 'Test B.Com',
            'code': 'TEST-BCOM',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Commerce',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 120,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['unicore.campus'].create({
            'name': 'Test Business Campus',
            'code': 'TBCAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['unicore.academic.year'].create({
            'name': 'Test AY 2025-26',
            'code': 'TAY2526',
            'date_start': '2025-07-01',
            'date_end': '2026-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['unicore.semester'].create({
            'name': 'Test ODD 2025-26',
            'code': 'TODD-2526',
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2025-07-15',
            'date_end': '2025-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })
        cls.student = cls.env['unicore.student'].create({
            'name': 'Fee',
            'last_name': 'Online Student',
            'gender': 'male',
            'date_of_birth': '2000-06-15',
            'email': 'fee.online@example.com',
            'mobile': '+911111111111',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })
        cls.config = None

    def _create_invoice(self, amount=10000.0):
        return self.env['unicore.fee.invoice'].create({
            'student_id': self.student.id,
            'company_id': self.company.id,
            'academic_year_id': self.academic_year.id,
            'semester_id': self.semester.id,
            'invoice_date': date.today(),
            'due_date': date.today() + timedelta(days=30),
            'currency_id': self.currency.id,
            'line_ids': [(0, 0, {
                'fee_type': 'tuition',
                'name': 'Tuition Fee',
                'amount': amount,
            })],
        })

    def _setup_accounting(self):
        """Look up the company chart and build the fee accounting config or skip."""
        if self.config:
            return self.config
        try:
            company = self.env.company
            receivable = self.env['account.account'].search([
                ('account_type', '=', 'asset_receivable'),
                ('reconcile', '=', True),
            ], limit=1)
            revenue = self.env['account.account'].search([
                ('account_type', '=', 'income'),
            ], limit=1)
            sale_journal = self.env['account.journal'].search([
                ('type', '=', 'sale'),
                ('company_id', '=', company.id),
            ], limit=1)
            self.bank_journal = self.env['account.journal'].search([
                ('type', '=', 'bank'),
                ('company_id', '=', company.id),
            ], limit=1)
            if not (receivable and revenue and sale_journal and self.bank_journal):
                self.skipTest('The company chart of accounts is incomplete')
            self.student.partner_id.with_company(company).write({
                'property_account_receivable_id': receivable.id,
            })
            self.config = self.env['unicore.fee.accounting.config'].create({
                'company_id': company.id,
                'journal_id': sale_journal.id,
                'revenue_account_id': revenue.id,
                'receivable_account_id': receivable.id,
                'auto_post_invoice': True,
                'is_active': True,
            })
        except Exception as exc:  # pragma: no cover - environment dependent
            self.skipTest('Accounting setup unavailable: %s' % exc)
        return self.config

    def _posted_gl_invoice(self):
        invoice = self._create_invoice()
        self._setup_accounting()
        invoice.action_send()
        move = invoice.account_move_id
        self.assertTrue(move, 'GL invoice must be created on send')
        self.assertEqual(move.state, 'posted', 'GL invoice must be auto-posted')
        return invoice, move

    # -------------------- HELPERS WITHOUT GL --------------------

    def test_01_helpers_without_gl_invoice(self):
        """Without a GL invoice the fee invoice is not payable online."""
        invoice = self._create_invoice()
        self.assertFalse(invoice._is_payable_online())
        self.assertFalse(invoice.get_online_payment_portal_url())
        self.assertEqual(invoice.payment_tx_count, 0)
        self.assertTrue(invoice._get_online_payment_error())
        with self.assertRaises(UserError):
            invoice.action_generate_payment_link()

    def test_02_view_online_payments_action(self):
        """The online payments action always returns a valid window action."""
        invoice = self._create_invoice()
        action = invoice.action_view_online_payments()
        self.assertEqual(action['res_model'], 'payment.transaction')
        self.assertEqual(action['view_mode'], 'list,form')

    # -------------------- WITH GL --------------------

    def test_03_payable_flag_and_payment_link(self):
        """Once the GL invoice is posted, the fee invoice becomes payable."""
        invoice, move = self._posted_gl_invoice()
        self.assertTrue(invoice._is_payable_online())

        url = invoice.get_online_payment_portal_url()
        self.assertTrue(url, 'Portal URL must be generated')
        self.assertIn('/my/invoices/%s' % move.id, url)
        self.assertIn('access_token=', url)

        action = invoice.action_generate_payment_link()
        self.assertEqual(action['res_model'], 'payment.link.wizard')
        self.assertEqual(action['context']['active_model'], 'account.move')
        self.assertEqual(action['context']['active_id'], move.id)

    def test_04_transaction_post_process_sync(self):
        """A confirmed transaction reconciles the GL invoice and syncs the fee invoice."""
        invoice, move = self._posted_gl_invoice()
        self.assertEqual(invoice.amount_outstanding, invoice.total_amount)
        self.assertFalse(invoice.payment_tx_count)

        # Record a payment against the GL invoice through the native wizard.
        amount = invoice.total_amount
        inbound_line = self.bank_journal.inbound_payment_method_line_ids[:1]
        self.assertTrue(inbound_line, 'Bank journal must have an inbound payment method')
        register = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids, active_id=move.id,
        ).create({
            'journal_id': self.bank_journal.id,
            'amount': amount,
            'payment_date': date.today(),
            'payment_method_line_id': inbound_line.id,
        })
        payments = register._create_payments()
        payment = payments[:1]
        self.assertTrue(payment, 'Payment must be created')
        self.assertEqual(payment.state, 'paid', 'Payment must be posted')

        # Simulate an online transaction that produced this payment.
        provider = self.env['payment.provider'].create({
            'name': 'Test Provider',
            'code': 'none',
            'company_id': self.company.id,
            'state': 'test',
            'is_published': True,
        })
        payment_method = self.env['payment.method'].create({
            'code': 'test_manual',
            'name': 'Test Manual Method',
        })
        tx = self.env['payment.transaction'].create({
            'provider_id': provider.id,
            'payment_method_id': payment_method.id,
            'payment_id': payment.id,
            'reference': 'TEST-ONLINE-TX',
            'amount': amount,
            'currency_id': self.currency.id,
            'partner_id': self.student.partner_id.id,
            'operation': 'online_redirect',
            'state': 'done',
            'landing_route': '/payment/confirmation',
            'invoice_ids': [Command.set([move.id])],
        })

        # Refresh the fee invoice stats, then run the post-processing hook.
        self.assertTrue(move in tx.invoice_ids, 'Tx must be linked to the GL invoice')
        invoice.invalidate_recordset()
        tx._post_process()

        fee_invoice_found = self.env['unicore.fee.invoice'].sudo().search([
            ('account_move_id', '=', move.id)])
        self.assertTrue(fee_invoice_found, 'Fee invoice must be found via GL invoice')

        ar_lines = move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable')
        self.assertEqual(invoice.invoice_state, 'paid',
                         'Fee invoice must be paid after reconciliation '
                         '(gl_state=%s payment_state=%s ar_lines=%s)'
                         % (move.state, move.payment_state,
                            [(l.id, l.reconciled) for l in ar_lines]))
        self.assertTrue(invoice.payment_tx_count >= 1)
        self.assertTrue(
            any('Online payment confirmed' in (msg.body or '') for msg in invoice.message_ids),
            'Fee invoice chatter must record the online payment confirmation',
        )
