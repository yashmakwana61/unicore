from datetime import date, timedelta

import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'financial')
class UniCoreFeeWorkflowTest(TransactionCase):

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
        # The default company uses a term-mode calendar (institution profile),
        # which forces academic years to ``year_type == 'term'``; such years may
        # only contain term semesters.
        cls.semester = cls.env['unicore.semester'].create({
            'name': 'Test First Term 2025-26',
            'code': 'TT1-2526',
            'semester_type': 'term_1',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2025-07-15',
            'date_end': '2025-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })

        cls.fee_structure = cls.env['unicore.fee.structure'].create({
            'name': 'Test B.Com Fee Structure',
            'company_id': cls.company.id,
            'academic_year_id': cls.academic_year.id,
            'semester_id': cls.semester.id,
            'program_id': cls.program.id,
            'campus_id': cls.campus.id,
            'currency_id': cls.currency.id,
            'line_ids': [
                (0, 0, {
                    'fee_type': 'tuition',
                    'name': 'Tuition Fee',
                    'amount': 25000.0,
                    'is_mandatory': True,
                }),
                (0, 0, {
                    'fee_type': 'library',
                    'name': 'Library Fee',
                    'amount': 5000.0,
                    'is_mandatory': True,
                }),
            ],
        })
        cls.fee_structure.action_activate()

        cls.student1 = cls.env['unicore.student'].create({
            'name': 'Fee',
            'last_name': 'Student One',
            'gender': 'male',
            'date_of_birth': '2000-06-15',
            'email': 'fee.student1@example.com',
            'mobile': '+911111111111',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })
        cls.student2 = cls.env['unicore.student'].create({
            'name': 'Fee',
            'last_name': 'Student Two',
            'gender': 'female',
            'date_of_birth': '2001-03-20',
            'email': 'fee.student2@example.com',
            'mobile': '+912222222222',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })
        cls.student3 = cls.env['unicore.student'].create({
            'name': 'Fee',
            'last_name': 'Student Three',
            'gender': 'male',
            'date_of_birth': '2002-11-10',
            'email': 'fee.student3@example.com',
            'mobile': '+913333333333',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })

        cls._setup_accounting()

    @classmethod
    def _setup_accounting(cls):
        """Resolve the company chart and (re)use the fee accounting config."""
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

        # Only one active config is allowed per company; reuse an existing one.
        cls.config = cls.env['unicore.fee.accounting.config'].search([
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
            cls.config = cls.env['unicore.fee.accounting.config'].create({
                'company_id': company.id,
                'journal_id': sale_journal.id,
                'revenue_account_id': revenue.id,
                'receivable_account_id': receivable.id,
                'auto_post_invoice': True,
                'is_active': True,
            })

    def _create_invoice(self, student, amount_lines=None, discount=0.0):
        if amount_lines is None:
            amount_lines = [('Tuition Fee', 25000.0), ('Library Fee', 5000.0)]
        lines = []
        for name, amt in amount_lines:
            lines.append((0, 0, {
                'fee_type': 'tuition' if 'Tuition' in name else 'library',
                'name': name,
                'amount': amt,
            }))
        invoice = self.env['unicore.fee.invoice'].create({
            'student_id': student.id,
            'company_id': self.company.id,
            'academic_year_id': self.academic_year.id,
            'semester_id': self.semester.id,
            'invoice_date': date.today(),
            'due_date': date.today() + timedelta(days=30),
            'currency_id': self.currency.id,
            'discount_amount': discount,
            'line_ids': lines,
        })
        return invoice

    def _create_payment(self, invoice, amount, confirm=True):
        # NOTE: `unicore.fee.payment` is archived; invoice amounts only update
        # through the GL flow (`_record_gl_payment`). This helper is kept only
        # to verify the legacy receipt-number sequence (test_07).
        payment = self.env['unicore.fee.payment'].create({
            'invoice_id': invoice.id,
            'amount': amount,
            'payment_date': date.today(),
            'payment_method': 'cash',
        })
        self.assertTrue(payment.id > 0)
        if confirm:
            payment.action_confirm()
        return payment

    def _record_gl_payment(self, invoice, amount):
        """Send the fee invoice to the GL (if needed) and record a payment."""
        if not invoice.account_move_id:
            invoice.action_send()
        move = invoice.account_move_id
        self.assertTrue(move, 'GL invoice must be created on send')
        self.assertEqual(move.state, 'posted', 'GL invoice must be auto-posted')

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
        # A partial payment legitimately stays 'in_process' until the invoice
        # is fully paid.
        self.assertIn(
            payment.state, ('paid', 'in_process'),
            'Payment must be posted',
        )
        return payment

    def test_01_fee_structure_create(self):
        """Fee structure total_amount must match sum of lines."""
        total = sum(line.amount for line in self.fee_structure.line_ids)
        self.assertEqual(self.fee_structure.total_amount, total)
        self.assertEqual(self.fee_structure.total_amount, 30000.0)
        self.assertEqual(self.fee_structure.structure_state, 'active')

    def test_02_fee_invoice_create(self):
        """Fee invoice must be created as draft with correct amounts."""
        invoice = self._create_invoice(self.student1)
        self.assertEqual(invoice.invoice_state, 'draft')
        self.assertEqual(invoice.total_amount, 30000.0)
        self.assertEqual(invoice.amount_outstanding, 30000.0)
        self.assertEqual(invoice.amount_paid, 0.0)
        self.assertEqual(len(invoice.line_ids), 2)

    def test_03_fee_invoice_number_generated(self):
        """Invoice number must be auto-generated."""
        invoice = self._create_invoice(self.student1)
        self.assertTrue(invoice.invoice_number, 'Invoice number must not be empty')
        self.assertNotEqual(invoice.invoice_number, '/')
        self.assertTrue(invoice.invoice_number.startswith('INV/'))

    def test_04_partial_payment(self):
        """Partial payment must update amounts and state."""
        invoice = self._create_invoice(self.student2)
        self.assertEqual(invoice.total_amount, 30000.0)
        self._record_gl_payment(invoice, 15000.0)
        invoice.invalidate_recordset()
        self.assertEqual(invoice.amount_paid, 15000.0)
        self.assertEqual(invoice.amount_outstanding, 15000.0)
        self.assertEqual(invoice.invoice_state, 'partial')

    def test_05_full_payment_marks_invoice_paid(self):
        """Full payment must close the invoice."""
        invoice = self._create_invoice(self.student2, [('Tuition Fee', 10000.0)])
        self.assertEqual(invoice.total_amount, 10000.0)
        self._record_gl_payment(invoice, 10000.0)
        invoice.invalidate_recordset()
        self.assertEqual(invoice.amount_paid, 10000.0)
        self.assertEqual(invoice.amount_outstanding, 0.0)
        self.assertEqual(invoice.invoice_state, 'paid')

    def test_06_overpayment_handled_as_advance(self):
        """Overpayment reconciles up to the invoice, leaving an advance."""
        invoice = self._create_invoice(self.student3, [('Tuition Fee', 10000.0)])
        self._record_gl_payment(invoice, 15000.0)
        invoice.invalidate_recordset()
        self.assertEqual(invoice.amount_paid, 10000.0)
        self.assertEqual(invoice.amount_outstanding, 0.0)
        self.assertEqual(invoice.invoice_state, 'paid')

    def test_07_payment_number_sequence(self):
        """Each payment must receive a unique receipt number."""
        invoice1 = self._create_invoice(self.student1, [('Tuition Fee', 5000.0)])
        invoice2 = self._create_invoice(self.student2, [('Tuition Fee', 5000.0)])
        p1 = self._create_payment(invoice1, 5000.0)
        p2 = self._create_payment(invoice2, 5000.0)
        self.assertNotEqual(p1.receipt_number, p2.receipt_number,
                            'Each payment must have a unique receipt number')
        self.assertTrue(p1.receipt_number.startswith('RCP/'))
        self.assertTrue(p2.receipt_number.startswith('RCP/'))

    def test_08_cancelled_invoice_payment(self):
        """A cancelled invoice drops out of the fees-due summary."""
        invoice = self._create_invoice(self.student1, [('Tuition Fee', 5000.0)])
        invoice.action_send()
        self.assertEqual(invoice.invoice_state, 'sent')
        invoice.action_cancel()
        self.assertEqual(invoice.invoice_state, 'cancelled')
        self.student1._compute_fee_summary()
        self.assertEqual(self.student1.total_fees_due, 0.0)
        self.assertFalse(self.student1.has_fee_dues)

    def test_09_fee_summary_computed(self):
        """Student total_fees_due must reflect outstanding across invoices."""
        inv1 = self._create_invoice(self.student1, [('Tuition Fee', 20000.0)])
        inv2 = self._create_invoice(self.student2, [('Tuition Fee', 30000.0)])
        self._record_gl_payment(inv1, 20000.0)
        self._record_gl_payment(inv2, 10000.0)
        inv1.invalidate_recordset()
        inv2.invalidate_recordset()
        self.assertEqual(inv1.invoice_state, 'paid')
        self.assertEqual(inv2.invoice_state, 'partial')
        self.student1._compute_fee_summary()
        self.student2._compute_fee_summary()
        self.assertEqual(self.student1.total_fees_due, 0.0)
        self.assertEqual(self.student2.total_fees_due, 20000.0)
        self.assertFalse(self.student1.has_fee_dues)
        self.assertTrue(self.student2.has_fee_dues)
