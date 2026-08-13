"""Gap-5: convocation cohort grouping.

Verifies the convocation "Graduates by Cohort" action on the event and the
same-cohort "Cohort Mates" action on the graduated student.
"""

from datetime import date

import odoo
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'convocation')
class OacisConvocationCohortTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.faculty = cls.env['oacis.faculty'].create({
            'name': 'Test Faculty of Convocation',
            'code': 'TFC',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['oacis.department'].create({
            'name': 'Test Convocation Office',
            'code': 'TCONV',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['oacis.program'].create({
            'name': 'Test B.A. Convocation',
            'code': 'TEST-BA-CONV',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Arts',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 120,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Test Convocation Campus',
            'code': 'TCCAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': 'Test AY 2024-25',
            'code': 'TAY2425C',
            'date_start': '2024-07-01',
            'date_end': '2025-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.convocation_event = cls.env['event.event'].create({
            'name': 'Test Convocation 2025',
            'date_begin': date.today(),
            'date_end': date.today(),
            'oacis_convocation_event': True,
            'company_id': cls.company.id,
        })
        cls.graduate = cls.env['oacis.student'].create({
            'name': 'Jane Graduate',
            'last_name': 'Smith',
            'gender': 'female',
            'date_of_birth': '2000-06-15',
            'email': 'jane.graduate@example.com',
            'mobile': '+911111111111',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2023,
            'admission_date': '2020-07-01',
            'student_state': 'graduated',
            'actual_graduation_date': date.today(),
        })

    def _graduated_student(self, name, email, mobile):
        return self.env['oacis.student'].create({
            'name': name,
            'last_name': 'Grad',
            'gender': 'female',
            'date_of_birth': '2000-06-15',
            'email': email,
            'mobile': mobile,
            'company_id': self.company.id,
            'campus_id': self.campus.id,
            'program_id': self.program.id,
            'batch_year': 2023,
            'admission_date': '2020-07-01',
            'student_state': 'graduated',
            'actual_graduation_date': date.today(),
        })

    def test_01_graduates_by_cohort_action(self):
        """The event action opens graduates grouped by cohort kind."""
        action = self.convocation_event.action_view_convocation_graduates()
        self.assertEqual(action['res_model'], 'oacis.student')
        self.assertIn(
            ('convocation_event_id', '=', self.convocation_event.id),
            action['domain'])
        self.assertEqual(
            action['context'].get('search_default_group_cohort_kind'), 1)

    def test_02_cohort_mates_same_convocation(self):
        """Cohort mates share the same convocation and batch cohort."""
        mate = self._graduated_student(
            'Mate Graduate', 'mate.graduate@example.com', '+911111111113')
        self.assertTrue(self.graduate.convocation_event_id)
        self.assertTrue(mate.convocation_event_id)
        self.assertEqual(
            mate.convocation_event_id, self.graduate.convocation_event_id)

        action = self.graduate.action_view_convocation_cohort_mates()
        self.assertEqual(action['res_model'], 'oacis.student')
        self.assertIn(('batch_year', '=', 2023), action['domain'])
        self.assertIn(
            ('convocation_event_id', '=', self.graduate.convocation_event_id.id),
            action['domain'])
        # the mate matches the cohort-mates domain
        self.assertIn(mate.id, self.env['oacis.student'].search(
            action['domain']).ids)

    def test_03_cohort_mates_no_event_raises(self):
        """A student not linked to a convocation cannot view cohort mates."""
        student = self.env['oacis.student'].create({
            'name': 'Not Grad',
            'last_name': 'NG',
            'gender': 'male',
            'date_of_birth': '2000-06-15',
            'email': 'not.grad@example.com',
            'mobile': '+911111111114',
            'company_id': self.company.id,
            'campus_id': self.campus.id,
            'program_id': self.program.id,
            'batch_year': 2023,
            'admission_date': '2020-07-01',
            'student_state': 'enrolled',
        })
        self.assertFalse(student.convocation_event_id)
        with self.assertRaises(UserError):
            student.action_view_convocation_cohort_mates()
