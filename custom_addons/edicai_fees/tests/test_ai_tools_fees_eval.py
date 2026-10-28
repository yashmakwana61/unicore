"""Eval harness: Fee Explainer Copilot safety properties.

Cases:
  1. payment_link_draft creates nothing: payment-link wizards,
     payment transactions, GL moves and payments are identical in
     count before and after the call.
  2. A restricted (portal student) caller reading another student's
     invoice is denied with AccessError (own-student scope).
"""

from datetime import date, timedelta

import odoo
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('edicai', 'unit')
class EdicaiFeeCopilotEvalTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        cls.faculty = cls.env['edicai.faculty'].create({
            'name': 'Eval Faculty of Business',
            'code': 'EVFFB',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['edicai.department'].create({
            'name': 'Eval Commerce',
            'code': 'EVFCOM',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['edicai.program'].create({
            'name': 'Eval B.Com',
            'code': 'EVF-BCOM',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Commerce',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 120,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['edicai.campus'].create({
            'name': 'Eval Business Campus',
            'code': 'EVFBCAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['edicai.academic.year'].create({
            'name': 'Eval AY 2025-26',
            'code': 'EVFAY2526',
            'date_start': '2025-07-01',
            'date_end': '2026-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        # Same term-mode note as test_fee_workflow: the default company
        # calendar only accepts term semesters in a term-type year.
        cls.semester = cls.env['edicai.semester'].create({
            'name': 'Eval First Term 2025-26',
            'code': 'EVFT1-2526',
            'semester_type': 'term_1',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2025-07-15',
            'date_end': '2025-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })
        cls.student_a = cls.env['edicai.student'].create({
            'name': 'EvalFee',
            'last_name': 'Student A',
            'gender': 'male',
            'date_of_birth': '2000-06-15',
            'email': 'evalfee.studentA@example.com',
            'mobile': '+915555555551',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })
        cls.student_b = cls.env['edicai.student'].create({
            'name': 'EvalFee',
            'last_name': 'Student B',
            'gender': 'female',
            'date_of_birth': '2001-03-20',
            'email': 'evalfee.studentB@example.com',
            'mobile': '+915555555552',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })
        cls.invoice_a = cls._create_invoice(cls.student_a)
        cls.invoice_b = cls._create_invoice(cls.student_b)

        # Restricted portal-style user linked ONLY to student A
        # (via partner -> user_ids, the same link the record rules use).
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Eval Fee Portal Student',
            'login': 'evalfee.portal.student@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('edicai_base.group_edicai_student').id,
            ])],
        })
        cls.student_a.write(
            {'partner_id': cls.portal_user.partner_id.id})

    @classmethod
    def _create_invoice(cls, student):
        return cls.env['edicai.fee.invoice'].create({
            'student_id': student.id,
            'company_id': cls.company.id,
            'academic_year_id': cls.academic_year.id,
            'semester_id': cls.semester.id,
            'invoice_date': date.today(),
            'due_date': date.today() + timedelta(days=30),
            'currency_id': cls.currency.id,
            'line_ids': [
                (0, 0, {
                    'fee_type': 'tuition',
                    'name': 'Tuition Fee',
                    'amount': 25000.0,
                }),
                (0, 0, {
                    'fee_type': 'library',
                    'name': 'Library Fee',
                    'amount': 5000.0,
                }),
            ],
        })

    def _payment_counts(self):
        counts = {
            'payment.transaction': self.env['payment.transaction'].search_count([]),
            'account.move': self.env['account.move'].search_count([]),
            'account.payment': self.env['account.payment'].search_count([]),
        }
        if 'payment.link.wizard' in self.env:
            counts['payment.link.wizard'] = self.env[
                'payment.link.wizard'].search_count([])
        return counts

    def test_01_payment_link_draft_creates_nothing(self):
        copilot = self.env['edicai.fee.copilot']
        before = self._payment_counts()
        result = copilot.payment_link_draft(self.invoice_a.id)
        self.assertEqual(result['type'], 'payment_link_draft')
        self.assertTrue(result['requires_human_approval'])
        self.assertEqual(self._payment_counts(), before)

    def test_02_cross_student_invoice_raises(self):
        copilot = self.env['edicai.fee.copilot'].with_user(self.portal_user)
        # Positive control: the caller's own invoice is readable.
        own = copilot.invoice_breakdown(invoice_id=self.invoice_a.id)
        self.assertEqual(own['invoice_id'], self.invoice_a.id)
        # Another student's invoice / scope is denied.
        with self.assertRaises(AccessError):
            copilot.invoice_breakdown(invoice_id=self.invoice_b.id)
        with self.assertRaises(AccessError):
            copilot.dues_summary(student_id=self.student_b.id)
        with self.assertRaises(AccessError):
            copilot.payment_link_draft(self.invoice_b.id)
