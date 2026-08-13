from datetime import date, timedelta

import odoo
from odoo.fields import Command
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'financial')
class OacisFeeGLPaymentSyncTest(TransactionCase):
    """Regression tests for the fee-invoice <-> GL payment sync.

    Recording a payment against the fee invoice's GL invoice (via the native
    `account.payment.register` wizard) must propagate back to the Fees module:
    `amount_paid`, `amount_outstanding` and `invoice_state` must all update,
    and the student's `total_fees_due` must drop to zero once fully paid.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        cls.faculty = cls.env['oacis.faculty'].create({
            'name': 'Test Faculty of Business',
            'code': 'TFB',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['oacis.department'].create({
            'name': 'Test Commerce',
            'code': 'TCOM',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['oacis.program'].create({
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
        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Test Business Campus',
            'code': 'TBCAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': 'Test AY 2025-26',
            'code': 'TAY2526',
            'date_start': '2025-07-01',
            'date_end': '2026-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        # The default company uses a term-mode calendar (institution profile),
        # which forces academic years to ``year_type == 'term'``; such years may
        # only contain term semesters.
        cls.semester = cls.env['oacis.semester'].create({
            'name': 'Test First Term 2025-26',
            'code': 'TT1-2526',
            'semester_type': 'term_1',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2025-07-15',
            'date_end': '2025-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })

        cls.student = cls.env['oacis.student'].create({
            'name': 'Fee',
            'last_name': 'GL Student',
            'gender': 'male',
            'date_of_birth': '2000-06-15',
            'email': 'fee.gl@example.com',
            'mobile': '+911111111111',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })

        cls._setup_accounting()

    @classmethod
    def _setup_accounting(cls):
        """Resolve the company chart and build the fee accounting config."""
        company = cls.env.company
        receivable = cls.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('reconcile', '=', True),
        ], limit=1)
        revenue = cls.env['account.account'].search([
            ('account_type', '=', 'income'),
        ], limit=1)
        sale_journal = cls.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', company.id),
        ], limit=1)
        cls.bank_journal = cls.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not (receivable and revenue and sale_journal and cls.bank_journal):
            cls.skipTest('The company chart of accounts is incomplete')

        cls.student.partner_id.with_company(company).write({
            'property_account_receivable_id': receivable.id,
        })
        # Only one active config is allowed per company. Reuse an existing one
        # (pointing its journal/accounts at the test chart) or create a fresh
        # one when none exists yet.
        cls.config = cls.env['oacis.fee.accounting.config'].search([
            ('company_id', '=', company.id),
        ], limit=1)
        if cls.config:
            cls.config.write({
                'journal_id': sale_journal.id,
                'revenue_account_id': revenue.id,
                'receivable_account_id': receivable.id,
                'auto_post_invoice': True,
                'is_active': True,
            })
        else:
            cls.config = cls.env['oacis.fee.accounting.config'].create({
                'company_id': company.id,
                'journal_id': sale_journal.id,
                'revenue_account_id': revenue.id,
                'receivable_account_id': receivable.id,
                'auto_post_invoice': True,
                'is_active': True,
            })

    def _create_invoice(self, amount=30000.0):
        return self.env['oacis.fee.invoice'].create({
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

    def _posted_gl_invoice(self, amount=30000.0):
        invoice = self._create_invoice(amount)
        invoice.action_send()
        move = invoice.account_move_id
        self.assertTrue(move, 'GL invoice must be created on send')
        self.assertEqual(move.state, 'posted', 'GL invoice must be auto-posted')
        return invoice, move

    def _record_payment(self, move, amount):
        """Record a payment against the GL invoice through the native wizard."""
        inbound_line = self.bank_journal.inbound_payment_method_line_ids[:1]
        self.assertTrue(inbound_line, 'Bank journal must have an inbound method')
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
        # A partial payment legitimately stays 'in_process' in Odoo: it only
        # becomes 'paid' once every reconciled invoice is fully paid.
        self.assertIn(
            payment.state, ('paid', 'in_process'),
            'Payment must be posted',
        )
        return payment

    def test_01_full_payment_marks_invoice_paid(self):
        """Recording a full payment clears the fee invoice outstanding."""
        invoice, move = self._posted_gl_invoice(30000.0)
        self.assertEqual(invoice.invoice_state, 'sent')
        self.assertEqual(invoice.amount_outstanding, 30000.0)

        self._record_payment(move, 30000.0)

        invoice.invalidate_recordset()
        self.assertEqual(invoice.amount_paid, 30000.0)
        self.assertEqual(invoice.amount_outstanding, 0.0)
        self.assertEqual(invoice.invoice_state, 'paid')

        self.student._compute_fee_summary()
        self.assertEqual(self.student.total_fees_due, 0.0)
        self.assertFalse(self.student.has_fee_dues)

    def test_02_partial_payment_marks_invoice_partial(self):
        """Recording a partial payment updates outstanding and status."""
        invoice, move = self._posted_gl_invoice(30000.0)

        self._record_payment(move, 12000.0)

        invoice.invalidate_recordset()
        self.assertEqual(invoice.amount_paid, 12000.0)
        self.assertEqual(invoice.amount_outstanding, 18000.0)
        self.assertEqual(invoice.invoice_state, 'partial')

    def test_03_unreconcile_restores_outstanding(self):
        """Un-reconciling a payment restores the outstanding amount."""
        invoice, move = self._posted_gl_invoice(30000.0)
        self._record_payment(move, 30000.0)

        invoice.invalidate_recordset()
        self.assertEqual(invoice.invoice_state, 'paid')

        # Undo the reconciliation (the AR line unlink fires the same hook).
        ar_line = move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable',
        )
        ar_line.remove_move_reconcile()

        invoice.invalidate_recordset()
        self.assertEqual(invoice.amount_paid, 0.0)
        self.assertEqual(invoice.amount_outstanding, 30000.0)
        self.assertEqual(invoice.invoice_state, 'sent')
