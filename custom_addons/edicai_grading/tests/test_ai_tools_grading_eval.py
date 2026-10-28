"""Eval harness: Grade Copilot safety properties.

Cases:
  1. Unknown action (action_verify) is rejected by the dispatcher.
  2. gradebook_preview writes nothing: grade-entry states/marks and the
     entry count are identical before and after the call.
  3. Cross-company offering access raises (company isolation).
"""

import odoo
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('edicai', 'unit')
class EdicaiGradingCopilotEvalTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        cls.faculty = cls.env['edicai.faculty'].create({
            'name': 'Eval Faculty of Arts',
            'code': 'EVGFA',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['edicai.department'].create({
            'name': 'Eval English',
            'code': 'EVGDENG',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['edicai.program'].create({
            'name': 'Eval B.A. English',
            'code': 'EVG-BA-ENG',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Arts',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 90,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['edicai.campus'].create({
            'name': 'Eval Arts Campus',
            'code': 'EVGARTSCAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['edicai.academic.year'].create({
            'name': 'Eval AY 2027-28',
            'code': 'EVGAY2728',
            'date_start': '2027-07-01',
            'date_end': '2028-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['edicai.semester'].create({
            'name': 'Eval ODD 2027-28',
            'code': 'EVGODD-2728',
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2027-07-15',
            'date_end': '2027-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })
        cls.course = cls.env['edicai.course'].create({
            'name': 'Eval English Literature',
            'code': 'EVGEL401',
            'credit_hours': 4.0,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.offering = cls.env['edicai.course.offering'].create({
            'course_id': cls.course.id,
            'semester_id': cls.semester.id,
            'academic_year_id': cls.academic_year.id,
            'program_id': cls.program.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'company_id': cls.company.id,
        })
        cls.student = cls.env['edicai.student'].create({
            'name': 'EvalGrading',
            'last_name': 'Copilot Student',
            'gender': 'female',
            'date_of_birth': '2001-09-10',
            'email': 'eval.grading.copilot@example.com',
            'mobile': '+914444444444',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })
        cls.other_company = cls.env['res.company'].create({
            'name': 'Eval Grading Other Institution',
        })

    def setUp(self):
        super().setUp()
        self.student.action_enroll()
        self.enrollment = self.env['edicai.enrollment'].create({
            'student_id': self.student.id,
            'course_offering_id': self.offering.id,
        })
        self.copilot = self.env['grading.ai.copilot']

    def _snapshot_entries(self):
        entries = self.env['edicai.grade.entry'].search([
            ('course_offering_id', '=', self.offering.id),
        ])
        return {
            entry.id: (
                entry.internal_marks,
                entry.external_marks,
                entry.entry_state,
            )
            for entry in entries
        }

    def test_01_unknown_action_rejected(self):
        with self.assertRaises(UserError):
            self.copilot.run_tool('action_verify')

    def test_02_gradebook_preview_writes_nothing(self):
        grade = self.env['edicai.grade.entry'].create({
            'enrollment_id': self.enrollment.id,
            'internal_marks': 30.0,
            'external_marks': 50.0,
        })
        self.assertEqual(grade.entry_state, 'draft')
        before = self._snapshot_entries()
        result = self.copilot.run_tool(
            'gradebook_preview', offering_id=self.offering.id)
        self.assertIn('rows', result)
        after = self._snapshot_entries()
        self.assertEqual(before, after)

    def test_03_cross_company_offering_raises(self):
        other_copilot = self.env['grading.ai.copilot'].with_company(
            self.other_company)
        with self.assertRaises(UserError):
            other_copilot.run_tool(
                'gradebook_preview', offering_id=self.offering.id)
