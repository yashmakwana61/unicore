from datetime import date

import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'convocation')
class OacisConvocationTest(TransactionCase):

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
        cls.semester = cls.env['oacis.semester'].create({
            'name': 'Test ODD 2024-25',
            'code': 'TODD-2425C',
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2024-07-15',
            'date_end': '2024-11-30',
            'semester_state': 'ongoing',
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

        cls.convocation_event = cls.env['event.event'].create({
            'name': 'Test Convocation 2025',
            'date_begin': date.today(),
            'date_end': date.today(),
            'oacis_convocation_event': True,
            'company_id': cls.company.id,
        })

    # -------------------- AUTO-CREATE --------------------

    def test_01_auto_register_graduate(self):
        """A graduated student should be auto-registered for the convocation event."""
        self.assertTrue(
            self.graduate.convocation_event_id,
            'Graduate should be linked to a convocation event')

    def test_02_convocation_event_flag(self):
        """The convocation event should have the flag set."""
        self.assertTrue(self.convocation_event.oacis_convocation_event)

    # -------------------- SMART BUTTONS --------------------

    def test_03_view_convocation_event_action(self):
        """Smart button action opens the convocation event."""
        action = self.graduate.action_view_convocation_event()
        self.assertEqual(action['res_model'], 'event.event')
        self.assertEqual(
            action['res_id'], self.graduate.convocation_event_id.id)
        self.assertEqual(action['view_mode'], 'form')

    def test_04_register_convocation_action(self):
        """action_register_convocation creates a registration."""
        student_no_event = self.env['oacis.student'].create({
            'name': 'New Graduate',
            'last_name': 'Doe',
            'gender': 'male',
            'date_of_birth': '2000-06-15',
            'email': 'new.graduate@example.com',
            'mobile': '+911111111112',
            'company_id': self.company.id,
            'campus_id': self.campus.id,
            'program_id': self.program.id,
            'batch_year': 2023,
            'admission_date': '2020-07-01',
            'student_state': 'graduated',
            'actual_graduation_date': date.today(),
        })
        student_no_event.action_register_convocation()
        self.assertTrue(student_no_event.convocation_event_id)

    # -------------------- COUNTS --------------------

    def test_05_registration_count(self):
        """convocation_registration_count reflects linked event."""
        self.assertEqual(self.graduate.convocation_registration_count, 1)
