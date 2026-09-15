
import re

import odoo
from odoo.tests import HttpCase


@odoo.tests.tagged('oacis', 'website')
class OacisAdmissionsWebsiteTest(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        cls.faculty = cls.env['oacis.faculty'].create({
            'name': 'Test Faculty of Admissions Portal',
            'code': 'TFAP',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['oacis.department'].create({
            'name': 'Test Admissions Portal Office',
            'code': 'TAPO',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['oacis.program'].create({
            'name': 'Test B.Sc. Portal',
            'code': 'TEST-BSC-PORTAL',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Science',
            'credit_system': 'credit_hours',
            'duration_years': 4,
            'total_credits': 128,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Test Portal Campus',
            'code': 'TPCAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': 'Test AY 2026-27 Portal',
            'code': 'TAY2627P',
            'date_start': '2026-07-01',
            'date_end': '2027-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.cycle = cls.env['oacis.admission.cycle'].create({
            'name': 'Test Admissions Cycle Portal',
            'code': 'TAC-PORTAL',
            'campus_id': cls.campus.id,
            'academic_year_id': cls.academic_year.id,
            'start_date': '2026-07-15',
            'end_date': '2026-09-15',
            'state': 'active',
            'company_id': cls.company.id,
        })
        cls.seat = cls.env['oacis.admission.cycle.seat'].create({
            'cycle_id': cls.cycle.id,
            'program_id': cls.program.id,
            'total_seats': 10,
        })

    def test_01_programs_page_lists_open_cycle(self):
        response = self.url_open('/admissions/programs')
        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn('Test B.Sc. Portal', body)
        self.assertIn('Test Admissions Cycle Portal', body)
        self.assertIn('/admissions/apply', body)

    def test_02_apply_page_renders_form(self):
        response = self.url_open('/admissions/apply')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Apply for Admission', response.text)
        self.assertIn('Test B.Sc. Portal', response.text)

    def _csrf_token(self):
        response = self.url_open('/admissions/apply')
        match = re.search(
            r'name="csrf_token"\s+value="([^"]+)"', response.text)
        self.assertTrue(match, 'CSRF token not found in the form')
        return match.group(1)

    def test_03_valid_application_creates_applicant(self):
        token = self._csrf_token()
        response = self.url_open('/admissions/apply', data={
            'csrf_token': token,
            'name': 'Portal Applicant',
            'email': 'applicant@example.com',
            'mobile': '+92-300-0000000',
            'gender': 'male',
            'date_of_birth': '2000-01-15',
            'cycle_id': str(self.cycle.id),
            'program_id': str(self.program.id),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Application Submitted', response.text)
        applicant = self.env['oacis.admission.applicant'].search([
            ('email', '=', 'applicant@example.com'),
        ], limit=1)
        self.assertTrue(applicant)
        self.assertEqual(applicant.state, 'inquiry')
        self.assertEqual(applicant.cycle_id, self.cycle)
        self.assertEqual(applicant.program_id, self.program)
        self.assertEqual(applicant.campus_id, self.cycle.campus_id)
        self.assertEqual(applicant.company_id, self.company)
        self.assertTrue(applicant.application_number)

    def test_04_invalid_application_shows_errors(self):
        token = self._csrf_token()
        response = self.url_open('/admissions/apply', data={
            'csrf_token': token,
            'name': '',
            'email': '',
            'mobile': '',
            'gender': '',
            'date_of_birth': '',
            'cycle_id': str(self.cycle.id),
            'program_id': str(self.program.id),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Please enter your full name', response.text)
        self.assertIn('Please enter your email address', response.text)
        self.assertIn('Please select your gender', response.text)

    def test_05_draft_cycle_not_listed(self):
        draft_cycle = self.env['oacis.admission.cycle'].create({
            'name': 'Test Draft Cycle Portal',
            'code': 'TDC-PORTAL',
            'campus_id': self.campus.id,
            'academic_year_id': self.academic_year.id,
            'start_date': '2027-01-15',
            'end_date': '2027-03-15',
            'state': 'draft',
            'company_id': self.company.id,
        })
        self.env['oacis.admission.cycle.seat'].create({
            'cycle_id': draft_cycle.id,
            'program_id': self.program.id,
            'total_seats': 10,
        })
        response = self.url_open('/admissions/programs')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Test Draft Cycle Portal', response.text)