import odoo
from datetime import date
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'alumni')
class UniCoreAlumniTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        cls.faculty = cls.env['unicore.faculty'].create({
            'name': 'Test Faculty of Alumni',
            'code': 'TFA',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['unicore.department'].create({
            'name': 'Test Alumni Office',
            'code': 'TALM',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['unicore.program'].create({
            'name': 'Test B.A. Alumni',
            'code': 'TEST-BA-ALUM',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Arts',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 120,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['unicore.campus'].create({
            'name': 'Test Alumni Campus',
            'code': 'TALCAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['unicore.academic.year'].create({
            'name': 'Test AY 2024-25',
            'code': 'TAY2425',
            'date_start': '2024-07-01',
            'date_end': '2025-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['unicore.semester'].create({
            'name': 'Test ODD 2024-25',
            'code': 'TODD-2425',
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2024-07-15',
            'date_end': '2024-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })
        cls.student = cls.env['unicore.student'].create({
            'name': 'John Alumni',
            'last_name': 'Doe',
            'gender': 'male',
            'date_of_birth': '2000-06-15',
            'email': 'john.alumni@example.com',
            'mobile': '+911111111111',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2023,
            'admission_date': '2020-07-01',
        })

    # -------------------- MAILING LIST --------------------

    def test_01_alumni_mailing_list_contact(self):
        """Alumni student should be linked to the alumni mailing list."""
        mailing_list = self.env.ref(
            'unicore_alumni.mass_mailing_list_alumni')
        self.student.alumni_mailing_list_ids = [
            (4, mailing_list.id)]
        self.assertIn(
            mailing_list, self.student.alumni_mailing_list_ids)

    def test_02_mailing_list_alumni_flag(self):
        """The alumni mailing list should have the alumni flag set."""
        mailing_list = self.env.ref(
            'unicore_alumni.mass_mailing_list_alumni')
        self.assertTrue(mailing_list.unicore_alumni_list)

    # -------------------- EVENT REGISTRATION --------------------

    def test_03_alumni_event_registration(self):
        """Alumni student should be linkable to alumni events."""
        event = self.env['event.event'].create({
            'name': 'Test Alumni Reunion',
            'date_begin': date.today(),
            'date_end': date.today(),
            'unicore_alumni_event': True,
            'company_id': self.company.id,
        })
        self.student.alumni_event_ids = [(4, event.id)]
        self.assertIn(event, self.student.alumni_event_ids)

    def test_04_event_alumni_flag(self):
        """The alumni event should have the alumni flag set."""
        event = self.env['event.event'].create({
            'name': 'Test Alumni Event Flag',
            'date_begin': date.today(),
            'date_end': date.today(),
            'unicore_alumni_event': True,
            'company_id': self.company.id,
        })
        self.assertTrue(event.unicore_alumni_event)

    # -------------------- SMART BUTTONS --------------------

    def test_05_view_mailing_lists_action(self):
        """Smart button action opens mailing lists."""
        mailing_list = self.env.ref(
            'unicore_alumni.mass_mailing_list_alumni')
        self.student.alumni_mailing_list_ids = [
            (4, mailing_list.id)]
        action = self.student.action_view_alumni_mailing_lists()
        self.assertEqual(action['res_model'], 'mass_mailing.mailing.list')
        self.assertEqual(action['view_mode'], 'tree,form')

    def test_06_view_alumni_events_action(self):
        """Smart button action opens alumni events."""
        event = self.env['event.event'].create({
            'name': 'Test Alumni Event Action',
            'date_begin': date.today(),
            'date_end': date.today(),
            'unicore_alumni_event': True,
            'company_id': self.company.id,
        })
        self.student.alumni_event_ids = [(4, event.id)]
        action = self.student.action_view_alumni_events()
        self.assertEqual(action['res_model'], 'event.event')
        self.assertEqual(action['view_mode'], 'tree,form')

    # -------------------- COUNTS --------------------

    def test_07_registration_count(self):
        """alumni_registration_count reflects linked events."""
        event = self.env['event.event'].create({
            'name': 'Test Alumni Count Event',
            'date_begin': date.today(),
            'date_end': date.today(),
            'unicore_alumni_event': True,
            'company_id': self.company.id,
        })
        self.student.alumni_event_ids = [(4, event.id)]
        self.assertEqual(self.student.alumni_registration_count, 1)