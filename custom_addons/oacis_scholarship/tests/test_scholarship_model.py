from datetime import date, timedelta

import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'financial')
class OacisScholarshipTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        cls.faculty = cls.env['oacis.faculty'].create({
            'name': 'Test Faculty of Science',
            'code': 'TFS',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['oacis.department'].create({
            'name': 'Test Physics',
            'code': 'TPHY',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['oacis.program'].create({
            'name': 'Test B.Sc. Physics',
            'code': 'TEST-BSC-PHY',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Science',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 120,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Test Science Campus',
            'code': 'TSCICAMP2',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': 'Test AY 2025-26 SCH',
            'code': 'TAY2526SCH',
            'date_start': '2025-07-01',
            'date_end': '2026-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['oacis.semester'].create({
            'name': 'Test ODD 2025-26 SCH',
            'code': 'TODD-2526-SCH',
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2025-07-15',
            'date_end': '2025-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })

        cls.scholarship_program = cls.env['oacis.scholarship.program'].create({
            'name': 'Test Merit Scholarship',
            'code': 'MERIT-TEST',
            'company_id': cls.company.id,
            'academic_year_id': cls.academic_year.id,
            'scholarship_type': 'merit',
            'funding_source': 'institutional',
            'award_type': 'fee_waiver',
            'min_cgpa': 8.0,
            'award_amount': 5000.0,
            'currency_id': cls.currency.id,
            'total_quota': 10,
            'application_deadline': '2027-03-31',
        })
        cls.scholarship_program.action_open()

        cls.eligible_student = cls.env['oacis.student'].create({
            'name': 'Scholar',
            'last_name': 'Eligible',
            'gender': 'male',
            'date_of_birth': '2000-06-15',
            'email': 'scholar.eligible@example.com',
            'mobile': '+911111111111',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
            'cgpa': 9.0,
        })

        cls.ineligible_student = cls.env['oacis.student'].create({
            'name': 'Scholar',
            'last_name': 'Ineligible',
            'gender': 'female',
            'date_of_birth': '2001-03-20',
            'email': 'scholar.ineligible@example.com',
            'mobile': '+912222222222',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
            'cgpa': 6.0,
        })

    def test_01_scholarship_program_create(self):
        """Scholarship program must be created and opened."""
        self.assertTrue(self.scholarship_program.id > 0)
        self.assertEqual(self.scholarship_program.min_cgpa, 8.0)
        self.assertEqual(self.scholarship_program.award_amount, 5000.0)
        self.assertEqual(self.scholarship_program.program_state, 'open')

    def test_02_scholarship_application_eligibility(self):
        """Eligible student must get is_eligible = True after submission."""
        application = self.env['oacis.scholarship.application'].create({
            'scholarship_program_id': self.scholarship_program.id,
            'student_id': self.eligible_student.id,
        })
        application.action_submit()
        self.assertTrue(application.is_eligible)

    def test_03_ineligible_student(self):
        """Ineligible student must get is_eligible = False after submission."""
        application = self.env['oacis.scholarship.application'].create({
            'scholarship_program_id': self.scholarship_program.id,
            'student_id': self.ineligible_student.id,
        })
        application.action_submit()
        self.assertFalse(application.is_eligible)

    def test_04_scholarship_award_adjusts_fees(self):
        """Scholarship award disbursement must reduce invoice outstanding."""
        invoice = self.env['oacis.fee.invoice'].create({
            'student_id': self.eligible_student.id,
            'company_id': self.company.id,
            'academic_year_id': self.academic_year.id,
            'semester_id': self.semester.id,
            'invoice_date': date.today(),
            'due_date': date.today() + timedelta(days=30),
            'currency_id': self.currency.id,
            'line_ids': [
                (0, 0, {
                    'fee_type': 'tuition',
                    'name': 'Tuition Fee',
                    'amount': 30000.0,
                }),
            ],
        })
        self.assertEqual(invoice.total_amount, 30000.0)
        self.assertEqual(invoice.discount_amount, 0.0)

        application = self.env['oacis.scholarship.application'].create({
            'scholarship_program_id': self.scholarship_program.id,
            'student_id': self.eligible_student.id,
        })
        application.action_submit()
        application.action_start_review()
        application.action_shortlist()
        application.action_approve()

        award = self.env['oacis.scholarship.award'].create({
            'application_id': application.id,
            'semester_id': self.semester.id,
            'award_amount': 5000.0,
            'currency_id': self.currency.id,
            'disbursement_method': 'fee_adjustment',
            'fee_invoice_id': invoice.id,
        })
        award.action_approve_award()
        award.action_disburse()

        self.assertTrue(award.fee_adjustment_applied)
        self.assertEqual(invoice.discount_amount, 5000.0)
        self.assertEqual(invoice.total_amount, 25000.0)
